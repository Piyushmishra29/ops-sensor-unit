"""
MQ-135 — ADC to sensor resistance to an estimated concentration.

WHAT THE PART ACTUALLY IS. A tin-dioxide bead sitting on a small heater inside
a steel mesh. Heat it to a few hundred degrees and oxygen adsorbs onto the
surface, trapping electrons and raising the bead's resistance. Reducing gases
landing on it release those electrons again and the resistance FALLS. That is
the entire measurement: one resistance, going down when there is "something" in
the air.

WHAT IT IS NOT. It is not selective. Alcohol, ammonia, benzene, toluene, smoke,
NOx and CO2 all move the same single number, and there is no way — none, not
with better firmware — to recover which one did it. Every "CO2 ppm" this module
returns is the answer to "what CO2 concentration would produce this resistance
if CO2 were the only thing in the room". Downstream code says "~CO2" with the
tilde for that reason, and aq.py refuses to call any of it AQI.

So this file is written to be honest in three specific ways:

  1. It reports Rs, in ohms, as a first-class value. Rs is the thing actually
     measured. Everything after it is inference and can be checked against it.

  2. It will not pretend to be calibrated. R0 comes from a clean-air
     calibration you performed, persisted to /data/cal.json. With no R0 there
     is no ratio, no ppm, and read() says so rather than substituting a
     plausible default.

  3. It tracks warm-up and refuses to vouch for a reading during it. A cold
     bead reads high and drifts down for minutes, which presents as clean air
     slowly getting worse — indistinguishable from a working sensor unless
     something says otherwise. trust() is that something.

All tunables live in config.py. Nothing here has a number in it that you would
want to change.
"""
import json
import math
import os
import time

from machine import ADC, Pin

import config


# Heater warm-up is measured from POWER-ON, not from object construction. This
# module is imported at boot, so ticks_ms() here is close enough to zero, and —
# more usefully — breaking to the REPL and building a second MQ135 an hour later
# does not restart a warm-up that physically already happened.
# ticks_ms() wraps at 2^30 ms (~12.4 days); _warm latches long before that, so
# the wrap can only ever make an already-warm sensor stay warm.
_T0 = time.ticks_ms()
_warm = False


def _median(vals):
    """Median, not mean. ADC noise on this chip is spiky rather than gaussian —
    a single full-scale outlier in the set drags a mean somewhere the air never
    was, and leaves no trace that it did."""
    s = sorted(vals)
    return s[len(s) // 2]


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def correction_factor(t, h):
    """Temperature/humidity correction for the bead's baseline resistance.

    Returns the factor to DIVIDE raw Rs by. 1.0 means no correction applied,
    which is also what you get for a missing or out-of-range reading — the
    polynomial keeps returning numbers outside the chart it was fitted to, and
    those numbers are fiction.

    Both branches return 1.000 at 20 C / 33 %RH; that is the reference point the
    constants were normalised to, and it is worth checking if you ever retune
    them. Fed a DHT11 this is coarse — whole degrees, whole percent, ±2 C and
    ±5 %RH — so it removes gross seasonal drift and nothing finer. Still worth
    having: uncorrected, the same room reads noticeably "worse" on a humid
    afternoon than a dry morning, and that is the sensor, not the air.
    """
    if t is None or h is None:
        return 1.0
    if not (config.MQ135_COR_T_MIN <= t <= config.MQ135_COR_T_MAX):
        return 1.0
    if not (config.MQ135_COR_H_MIN <= h <= config.MQ135_COR_H_MAX):
        return 1.0
    if t < 20.0:
        return (config.MQ135_COR_A * t * t
                - config.MQ135_COR_B * t
                + config.MQ135_COR_C
                - (h - 33.0) * config.MQ135_COR_D)
    return (config.MQ135_COR_E * t
            + config.MQ135_COR_F * h
            + config.MQ135_COR_G)


def ppm_from_ratio(ratio):
    """ppm = A * (Rs/R0)^B, the datasheet's CO2 line.

    See the provenance note in config.py before believing a digit of this. Fed
    the Rs/R0 ratio, NOT the normalised one."""
    if ratio is None or ratio <= 0.0:
        return None
    return config.MQ135_PPM_A * math.pow(ratio, config.MQ135_PPM_B)


def _read_json(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    try:
        os.mkdir(config.DATA_DIR)
    except OSError:
        pass                        # already there
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as fh:
            json.dump(obj, fh)
        # rename is atomic on littlefs, so a power cut mid-write leaves the old
        # calibration intact rather than a half-written file that parses as
        # nothing and silently uncalibrates the unit
        try:
            os.remove(path)
        except OSError:
            pass
        os.rename(tmp, path)
        return True
    except OSError:
        return False


class MQ135:
    def __init__(self, pin=None, rl_ohms=None):
        self.pin = config.MQ135_PIN if pin is None else pin
        self.rl = config.MQ135_RL_EFF if rl_ohms is None else rl_ohms
        self.adc = ADC(Pin(self.pin))
        # 11 dB attenuation puts full scale near 3.1 V, which is what the
        # divider in config.py is sized against. Newer IDF calls this 12 dB and
        # some builds renamed the constant, hence the getattr dance.
        try:
            self.adc.atten(getattr(ADC, "ATTN_11DB", 3))
        except Exception:
            pass                    # some ports set attenuation in the ctor
        self._uv = hasattr(self.adc, "read_uv")

        self.r0 = None              # ohms, from calibration; None = uncalibrated
        self.cal_meta = {}
        self.rs = None              # smoothed, corrected
        self.rs_raw = None          # last unsmoothed, uncorrected
        self.volts = None
        self.corrected = False      # was the last Rs temp/humidity corrected
        self.load()

    # ── raw electrical ─────────────────────────────────────────────────────
    def read_volts(self):
        """Voltage at the module's AOUT pin, with the external divider undone.

        read_uv() applies the chip's factory eFuse calibration and returns real
        microvolts; it is meaningfully better than scaling read_u16() by a
        nominal full scale; the classic ESP32 ADC is not linear near either rail.
        The fallback exists for builds that lack it and is documented as the
        worse path rather than hidden."""
        samples = []
        for _ in range(config.MQ135_SAMPLES):
            if self._uv:
                samples.append(self.adc.read_uv() / 1000000.0)
            else:
                samples.append(self.adc.read_u16()
                               * config.MQ135_ADC_FULL_SCALE_V
                               / config.MQ135_ADC_MAX)
        v_adc = _median(samples)
        self.volts = v_adc / config.MQ135_DIV_RATIO
        return self.volts

    def raw_resistance(self):
        """Rs in ohms from the divider, uncorrected and unsmoothed.

            Vout = VCC * RL/(Rs + RL)   =>   Rs = RL * (VCC - Vout)/Vout

        Returns None at either end of the range instead of a number, because
        both ends mean the wiring is wrong rather than the air being extreme:

          Vout ~ 0     open AOUT, dead heater, or no 5 V on the module
          Vout >= VCC  the sensor bead is shorted, or VCC in config is wrong
        """
        v = self.read_volts()
        if v <= 0.05:
            return None
        if v >= config.MQ135_VCC - 0.02:
            return None
        return self.rl * (config.MQ135_VCC - v) / v

    # ── warm-up ────────────────────────────────────────────────────────────
    def warm_remaining_s(self):
        left = config.MQ135_WARMUP_S - time.ticks_diff(time.ticks_ms(), _T0) / 1000.0
        return left if left > 0 else 0.0

    def is_warm(self):
        """True once the heater has had config.MQ135_WARMUP_S since power-on.

        Latched: once warm, always warm for this power cycle. Nothing here can
        see the heater's actual temperature — there is no sense line — so this
        is a timer that encodes a datasheet figure, not a measurement. It is
        still the difference between a number you can act on and a number that
        is just the bead cooling down in reverse.

        Note what it does NOT cover: burn-in. A sensor out of the bag needs
        24-48 h powered before its baseline settles, and no timer started at
        this boot can know whether that ever happened. See README."""
        global _warm
        if _warm:
            return True
        if self.warm_remaining_s() <= 0.0:
            _warm = True
        return _warm

    def is_calibrated(self):
        return self.r0 is not None and self.r0 > 0.0

    def trust(self):
        """None if the current reading can be reported as a number, otherwise a
        short reason, uppercase, short enough for the panel's rail.

        Every caller that puts a figure in front of a human is expected to check
        this first. It is the whole point of the module: the failure mode of a
        cheap gas sensor is not silence, it is a confident wrong number."""
        if not self.is_warm():
            return "WARMUP"
        if not self.is_calibrated():
            return "UNCAL"
        if self.rs is None:
            return "NO SIG"
        return None

    # ── the reading ────────────────────────────────────────────────────────
    def read(self, t=None, h=None):
        """Sample once and return everything, including why not to believe it.

        t/h are the DHT11's last good reading, or None. Passing None does not
        fail — it just skips the correction and says so in ["corrected"], which
        is better than blocking a gas reading on an unrelated sensor's sulk."""
        raw = self.raw_resistance()
        self.rs_raw = raw

        if raw is None:
            # Do NOT zero self.rs here. One bad sample - a loose jumper, a
            # brownout while the OLED lights - should not wipe a good smoothed
            # value; trust() reports NO SIG only once there has never been one.
            rs = self.rs
            self.corrected = False
        else:
            factor = correction_factor(t, h)
            self.corrected = factor != 1.0
            rs = raw / factor
            if self.rs is None:
                self.rs = rs        # first sample seeds the filter outright,
            else:                   # otherwise it spends 20 s climbing from 0
                a = config.MQ135_EMA_ALPHA
                self.rs = a * rs + (1.0 - a) * self.rs
            rs = self.rs

        ratio = (rs / self.r0) if (rs is not None and self.is_calibrated()) else None
        norm = (ratio / config.clean_air_ratio()) if ratio is not None else None

        return {
            "volts": self.volts,
            "rs_raw": raw,
            "rs": rs,
            "r0": self.r0,
            "ratio": ratio,         # Rs/R0, what the ppm curve eats
            "norm": norm,           # Rs vs calibration-day Rs, what aq.py eats
            "ppm": ppm_from_ratio(ratio),
            "corrected": self.corrected,
            "warm": self.is_warm(),
            "warm_left": self.warm_remaining_s(),
            "cal": self.is_calibrated(),
            "trust": self.trust(),
        }

    # ── calibration ────────────────────────────────────────────────────────
    def calibrate(self, seconds=None, t=None, h=None, progress=None):
        """Measure R0 in clean air and persist it. Returns (r0, note).

        DO THIS OUTDOORS, or at an open window with the window open for a while
        first. "Clean air" here means outdoor background air at
        config.MQ135_CLEAN_AIR_PPM. A room that smells fine to you is not clean
        air to this sensor, and calibrating indoors bakes whatever was in that
        room into the baseline — after which the unit reads that room as
        perfect forever and everywhere else as better than it is.

        Refuses while the heater is cold, because an R0 taken during warm-up is
        high by an unknown amount and every later reading inherits it. It cannot
        refuse on burn-in, because nothing tells it the sensor's age — that one
        is on you.

        Takes the median of a minute of samples rather than one reading: the
        bead wanders by a few percent minute to minute even in still air.
        """
        if not self.is_warm():
            return None, "heater cold - %ds of warm-up left" % int(self.warm_remaining_s())

        seconds = config.MQ135_CAL_SECONDS if seconds is None else seconds
        factor = correction_factor(t, h)
        samples = []
        for i in range(seconds):
            r = self.raw_resistance()
            if r is not None:
                samples.append(r / factor)
            if progress:
                progress(i + 1, seconds, len(samples))
            time.sleep(1)

        # A calibration is not "the samples that worked". If a third of the run
        # produced nothing, the wiring is intermittent and the median of what is
        # left is not a baseline, it is a survivorship artifact.
        if len(samples) < seconds * 0.66:
            return None, "only %d/%d samples read - check wiring" % (len(samples), seconds)

        rs_clean = _median(samples)
        # R0 is defined through the curve, not as "Rs in clean air" - see
        # config.clean_air_ratio() for why, and for what breaks if you change it.
        r0 = rs_clean / config.clean_air_ratio()

        self.r0 = r0
        self.cal_meta = {
            "r0": r0,
            "rs_clean": rs_clean,
            "at_uptime_s": time.ticks_diff(time.ticks_ms(), _T0) // 1000,
            "clean_ppm": config.MQ135_CLEAN_AIR_PPM,
            "t": t,
            "h": h,
            "corrected": factor != 1.0,
            # Stamped so a later boot can notice the electrical model moved. An
            # R0 measured through a 10k load resistor means nothing once you
            # have swapped the divider, and silently keeping it is worse than
            # having none.
            "rl_eff": config.MQ135_RL_EFF,
            "vcc": config.MQ135_VCC,
            "samples": len(samples),
            "fw": config.FW,
        }
        ok = _write_json(config.CAL_PATH, self.cal_meta)
        return r0, ("saved to " + config.CAL_PATH) if ok else "MEASURED BUT NOT SAVED (flash write failed)"

    def load(self):
        """Restore R0 from flash, refusing it if the electrical model has moved.

        Returns a note, or None if there was simply nothing to load."""
        d = _read_json(config.CAL_PATH, None)
        if not isinstance(d, dict) or not d.get("r0"):
            return None
        rl = d.get("rl_eff")
        vcc = d.get("vcc")
        if rl is not None and abs(rl - config.MQ135_RL_EFF) > config.MQ135_RL_EFF * 0.01:
            return "calibration ignored: load resistance changed %.0f -> %.0f ohm" % (
                rl, config.MQ135_RL_EFF)
        if vcc is not None and abs(vcc - config.MQ135_VCC) > 0.05:
            return "calibration ignored: VCC changed %.2f -> %.2f V" % (vcc, config.MQ135_VCC)
        self.r0 = float(d["r0"])
        self.cal_meta = d
        return "R0 = %.0f ohm" % self.r0

    def forget(self):
        """Drop the calibration. Used when a sensor is replaced — the new bead's
        R0 has nothing to do with the old one's."""
        self.r0 = None
        self.cal_meta = {}
        try:
            os.remove(config.CAL_PATH)
        except OSError:
            pass


def calibrate(seconds=None, verbose=True):
    """Convenience entry point for the REPL. See README.

        >>> import mq135
        >>> mq135.calibrate()

    Blocks for a minute and prints as it goes, because a calibration that looks
    like a hung prompt gets Ctrl-C'd halfway through.
    """
    s = MQ135()
    if verbose:
        left = s.warm_remaining_s()
        if left > 0:
            print("waiting %ds for the heater..." % int(left))
    while not s.is_warm():
        time.sleep(1)

    def _p(i, n, good):
        if verbose and i % 10 == 0:
            print("  %d/%d samples (%d good)" % (i, n, good))

    r0, note = s.calibrate(seconds=seconds, progress=_p if verbose else None)
    if verbose:
        if r0 is None:
            print("calibration FAILED:", note)
        else:
            print("R0 = %.0f ohm (%s)" % (r0, note))
            print("reset the board to pick it up in the running firmware")
    return r0, note
