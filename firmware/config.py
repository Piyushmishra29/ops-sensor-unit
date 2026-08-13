"""
OPS sensor unit — configuration.

EVERYTHING a given build needs to differ on lives here: pins, the divider
resistors, the gas curve constants, every interval and every threshold. No
other file in this firmware contains a bare number that a person would want to
change. If you find yourself editing mq135.py or display.py to tune something,
that is a bug in this file.

    ┌──────────────────────────────────────────────────────────────────────┐
    │ THE PIN NUMBERS BELOW ARE A CHOICE, NOT A DISCOVERY.                  │
    │ They are sane ESP32-S3 defaults picked to avoid the strapping pins,   │
    │ the USB pins and the SPI-flash pins - but the firmware cannot see     │
    │ your breadboard. Make these match your wiring, or make your wiring    │
    │ match these. Nothing here is auto-detected except the OLED's I2C      │
    │ address.                                                             │
    └──────────────────────────────────────────────────────────────────────┘

Calibration (R0) is NOT in this file. It is measured per unit, per sensor, in
clean air, and persisted to /data/cal.json - because R0 is a property of the
individual bead you soldered, not of the design. See mq135.calibrate().

MicroPython note: this module is imported very early, so it must not touch
`machine` or any hardware. It is arithmetic and constants only.
"""
import math


# ── identity ───────────────────────────────────────────────────────────────
UNIT = "OPS-0001"
FW = "1.0.0"

DATA_DIR = "/data"


# ══ PINS ═══════════════════════════════════════════════════════════════════
# BOARD: ESP32-WROOM-32D  (classic Xtensa dual-core ESP32, NOT an S3).
# The two parts have completely different pinouts, so these numbers are not
# interchangeable with S3 examples found online.
#
# Pins deliberately avoided on this part, and why:
#   GPIO6..GPIO11    SPI flash. Connecting ANYTHING here stops the board
#                    booting. This is the one mistake that looks like a dead
#                    board rather than a wiring error.
#   GPIO0, 2, 12, 15 strapping pins, sampled at reset. Held wrong, the board
#                    either drops into the bootloader or refuses to start.
#                    GPIO12 in particular sets flash voltage - pulling it high
#                    at boot can brown out the flash.
#   GPIO34..GPIO39   INPUT ONLY. No output driver, no internal pull-ups.
#                    Perfect for an analog input, useless for the DHT11 (which
#                    is bidirectional) and useless for a button that wants a
#                    pull-up.
#
# ADC map, which decides where the gas sensor goes:
#   ADC1 = GPIO32..39   <- usable always
#   ADC2 = GPIO0,2,4,12..15,25..27  <- DEAD whenever WiFi is active

# ── display: 1.3" SH1106 over I2C ──────────────────────────────────────────
# The 1.3" panel is an SH1106 and needs a 2-column offset; the 0.96" is an
# SSD1306 and does not. See firmware/sh1106.py for that and for the
# write-the-frame-before-you-light-it rule this part demands.
OLED = True
OLED_SDA = 21             # classic ESP32 default I2C pair
OLED_SCL = 22
OLED_ADDR = 0x3C          # 0x3D on a few modules; sh1106.attach() scans for this
OLED_FREQ = 400000        # 400 kHz. At 100 kHz a full frame takes ~108 ms, which
                          # turns a 1 Hz refresh into a visible slideshow.
OLED_CONTRAST = 0x95

# ── MQ-135 analog gas sensor ───────────────────────────────────────────────
# MUST be an ADC1 pin (GPIO32..39). ADC2 is shared with the radio: there is no
# WiFi in this firmware so ADC2 would work today, but the moment anyone adds
# networking those reads start returning garbage, and that is a very unpleasant
# bug to meet later. GPIO34 is ADC1_CH6 and is input-only, which is exactly
# what an analog input wants.
MQ135_PIN = 34

# ── DHT11 temperature / humidity ───────────────────────────────────────────
# Any bidirectional GPIO - NOT one of GPIO34..39, which cannot drive the line.
# Needs a 4.7k-10k pull-up to 3V3 on the data line; most 3-pin DHT11 breakout
# boards already have one fitted, bare 4-pin parts do not.
DHT_PIN = 4

# ── screen-cycle button (OPTIONAL) ─────────────────────────────────────────
# Set to None if you did not fit one — the firmware then auto-rotates screens
# on a timer and never touches the pin. A momentary switch to GND; the internal
# pull-up does the rest, so no external resistor.
# The devkit's own BOOT button is GPIO0 and would work, but holding GPIO0 low
# across a reset drops the chip into the bootloader, so it is a poor choice for
# a button people are meant to press casually.
BUTTON_PIN = 25
BUTTON_ACTIVE_LOW = True
BUTTON_DEBOUNCE_MS = 40
BUTTON_CAL_HOLD_S = 3      # hold at boot to start a clean-air calibration


# ══ MQ-135 ELECTRICAL MODEL ════════════════════════════════════════════════
# The sensor is a heated tin-dioxide bead whose resistance FALLS as reducing
# gases adsorb onto it. The module wires it as the top half of a divider:
#
#      5V ──[ Rs (the bead) ]──┬──[ RL (module load resistor) ]── GND
#                              │
#                             AOUT
#
#   Vout = VCC * RL / (Rs + RL)      =>      Rs = RL * (VCC - Vout) / Vout
#
# ── the 5 V problem ────────────────────────────────────────────────────────
# The heater needs 5 V, so AOUT is referenced to 5 V and can legitimately reach
# it. An ESP32-S3 ADC pin is 3.3 V tolerant and NOT 5 V tolerant. Wiring AOUT
# straight to GPIO4 works right up until the air is clean, Rs is high, AOUT
# climbs past 3.6 V, and the pin's protection diode starts conducting into the
# 3V3 rail. Fit the divider. This is the single most important line in the file.
MQ135_VCC = 5.0

# Module load resistor. 10k is the usual value on the blue breakout boards, but
# 1k and 20k both exist in the wild and the silkscreen rarely says. MEASURE IT
# with the module unpowered, from AOUT to GND. Every ppm number downstream is
# wrong by whatever factor this is wrong by.
MQ135_RL_OHMS = 10000.0

# The external divider you fit between AOUT and the ADC pin:
#
#      AOUT ──[ DIV_TOP ]──┬──[ DIV_BOTTOM ]── GND
#                          │
#                        GPIO4
#
# 10k/15k gives 0.60, so a 5.00 V AOUT lands at 3.00 V — inside the ADC range
# with headroom to spare, and no sag into the pin's protection diodes.
MQ135_DIV_TOP = 10000.0
MQ135_DIV_BOTTOM = 15000.0
MQ135_DIV_RATIO = MQ135_DIV_BOTTOM / (MQ135_DIV_TOP + MQ135_DIV_BOTTOM)   # 0.60

# The divider is not free: it hangs 25k across the module's own RL, so the
# resistance the bead actually sees is the parallel combination. Skipping this
# correction was worth ~40% on Rs, which is worth a factor of ~3 on ppm once
# the power law has had its way with it.
#   10k || 25k = 7143 ohm
MQ135_RL_EFF = 1.0 / (1.0 / MQ135_RL_OHMS +
                      1.0 / (MQ135_DIV_TOP + MQ135_DIV_BOTTOM))

# ── ADC ────────────────────────────────────────────────────────────────────
# The driver prefers ADC.read_uv(), which applies the chip's factory eFuse
# calibration and returns real microvolts. The constants below are only used on
# builds where read_uv() is missing, and are noticeably less accurate: the
# ESP32-S3 ADC is not linear near either rail.
MQ135_ADC_FULL_SCALE_V = 3.1    # nominal top of the 11 dB attenuation range
MQ135_ADC_MAX = 65535           # machine.ADC.read_u16() is always 16-bit-scaled

# One reading is noise. Nine readings, median, is a reading. Median rather than
# mean because ADC noise on this chip is spiky, not gaussian, and one 4095 in
# the set would drag a mean somewhere the air never was.
MQ135_SAMPLES = 9

# Exponential smoothing on Rs. The air genuinely does change in seconds, but the
# bead does not resolve that, so anything faster than this is showing you the
# ADC and not the room. alpha = 0.2 at 1 Hz is a ~5 s time constant.
MQ135_EMA_ALPHA = 0.2


# ══ GAS CURVE ══════════════════════════════════════════════════════════════
# ppm = A * (Rs/R0) ^ B
#
# HOW GOOD ARE THESE NUMBERS? Not very, and you should know exactly how not.
# The MQ-135 datasheet gives one log-log chart of Rs/R0 against concentration
# with a separate line per gas. A and B below are a straight-line fit through
# the CO2 line of that chart, digitised by eye — they are the constants that
# circulate in every MQ-135 Arduino library, and they inherit every bit of that
# provenance. They are:
#   - a fit to a printed chart, not to a calibrated reference gas;
#   - for ONE gas, on a sensor that responds to alcohol, ammonia, benzene,
#     smoke and NOx as well, and cannot tell you which it is smelling;
#   - a typical part, not your part.
# Treat the ppm output as an order of magnitude and a direction of travel. If
# you need a real CO2 number, buy an NDIR sensor (SCD40/MH-Z19); it is a
# genuinely different measurement and no amount of curve fitting closes the gap.
MQ135_PPM_A = 116.6020682
MQ135_PPM_B = -2.769034857

# What "clean air" is assumed to contain when you run the calibration. Outdoor
# background CO2 was ~421 ppm in 2025 and rises about 2.5 ppm a year. R0 is
# DEFINED as the resistance the bead shows at this concentration - so if this
# number is wrong, R0 is wrong by the same proportion and every subsequent
# reading is shifted, though the trend still works.
MQ135_CLEAN_AIR_PPM = 421.0

# ── temperature / humidity correction ──────────────────────────────────────
# The bead's baseline resistance drifts with both. These seven constants are the
# usual empirical fit to the datasheet's correction chart, normalised so that
# 20 C / 33 %RH gives exactly 1.0 (check it: both branches return 1.000 there).
# Two branches because the chart's shape changes below 20 C.
#
#   t <  20:  A*t^2 - B*t + C - (h - 33)*D
#   t >= 20:  E*t + F*h + G
#
# Corrected Rs = raw Rs / factor.
#
# The correction is coarse by construction and coarser still in practice: a
# DHT11 reports whole degrees and whole percent, ±2 C and ±5 %RH. So this
# removes the gross seasonal drift and nothing finer. It is still worth doing —
# uncorrected, the same room reads noticeably "worse" on a humid afternoon.
MQ135_COR_A = 0.00035
MQ135_COR_B = 0.02718
MQ135_COR_C = 1.39538
MQ135_COR_D = 0.0018
MQ135_COR_E = -0.003333333
MQ135_COR_F = -0.001923077
MQ135_COR_G = 1.130128205

# Correction is only applied inside the range the source chart covered. Outside
# it the polynomial keeps producing numbers, and they are fiction.
MQ135_COR_T_MIN = -10.0
MQ135_COR_T_MAX = 45.0
MQ135_COR_H_MIN = 5.0
MQ135_COR_H_MAX = 95.0

# ── warm-up and burn-in ────────────────────────────────────────────────────
# TWO DIFFERENT WAITS, often confused:
#
# WARM-UP is every power-on. The heater has to reach temperature and the bead
# has to settle. Cold, Rs reads high and falling, so the unit reports
# improbably clean air that slowly gets worse — which looks exactly like a
# working sensor and is not one. 180 s is the conservative floor; watch the
# detail screen and you will see Rs still moving for the first few minutes.
MQ135_WARMUP_S = 180

# BURN-IN is once in the sensor's life. A brand new bead needs 24-48 h
# continuously powered before its baseline stops wandering, and calibrating
# before that gives an R0 that is simply wrong. The firmware CANNOT detect
# this — nothing in the sensor reports its own age — so it is on you: leave the
# unit plugged in for a day or two, then calibrate.
MQ135_BURN_IN_H = 48

# ── calibration ────────────────────────────────────────────────────────────
# Sixty samples at 1 Hz, median. Do it outdoors or by an open window: "clean
# air" means outdoor air, not "a room that smells fine to me".
MQ135_CAL_SECONDS = 60
CAL_PATH = DATA_DIR + "/cal.json"


# ══ AIR-QUALITY INDEX ══════════════════════════════════════════════════════
# Read aq.py before touching these. Short version: this is a VOC/gas index
# derived from Rs/R0, it is NOT an AQI, and it must never be labelled one.
#
# Index runs 0..100 with HIGHER = WORSE, matching the direction people expect
# from an AQI even though the quantity is different.
#
# ── which ratio? ───────────────────────────────────────────────────────────
# There are two floating around and mixing them up is the easiest mistake in
# this file:
#
#   Rs/R0   the datasheet's ratio, what the ppm power law eats. In clean air
#           this is clean_air_ratio() ≈ 0.629, NOT 1.0, because R0 is defined
#           through the curve rather than as "Rs in clean air" (see below).
#
#   NORM    Rs divided by the Rs you actually measured on calibration day,
#           i.e. Rs/R0 / clean_air_ratio(). This is 1.0 in clean air by
#           construction and falls as the air gets worse.
#
# The index is built on NORM, because "the bead reads 60% of its calibration-day
# resistance" is a statement about a measurement, whereas anchoring the index to
# the ppm curve would inherit all of that curve's guesswork on top of its own.
#
# Interpolation between the anchors is logarithmic, because the sensor response
# is a power law — linear interpolation would squash everything interesting
# into the top few points.
AQ_NORM_CLEAN = 1.0      # calibration-day air -> index 0
AQ_NORM_FOUL = 0.15      # Rs at 15% of calibration-day value: roughly a lit
                         # match held at the grille -> index 100

# Upper bound of each band, and its label. Four bands because a mono panel can
# show four states clearly and because nobody acts differently on a fifth.
AQ_BANDS = (
    (25, "GOOD"),        # indistinguishable from the air you calibrated in
    (50, "FAIR"),        # something is present; a closed room with people in it
    (75, "POOR"),        # ventilate
    (101, "BAD"),        # solvent, smoke, or the sensor is faulty - check both
)


# ══ TIMING ═════════════════════════════════════════════════════════════════
# A DHT11 CANNOT be read faster than about once a second and is specified for
# 2 s. Ask more often and it returns the previous sample or a checksum error,
# and the errors look like a broken sensor.
DHT_INTERVAL_MS = 2000

# The MQ-135 has no such limit — it is a resistor and an ADC. 1 Hz is chosen to
# match the smoothing above, not because the part needs it.
MQ_INTERVAL_MS = 1000

DISPLAY_INTERVAL_MS = 1000     # a mono panel redrawing faster just burns CPU
LOOP_TICK_MS = 20              # button polling granularity

# ── rolling history for the sparkline ──────────────────────────────────────
# 120 samples at 30 s each = the last hour, one pixel per sample, 120 px wide
# on a 128 px panel. Kept in RAM only: an hour of trend is not worth a flash
# erase cycle every thirty seconds.
HISTORY_INTERVAL_S = 30
HISTORY_LEN = 120

# ── screens ────────────────────────────────────────────────────────────────
SCREEN_DWELL_S = 6             # auto-rotate period when no button is fitted
SCREEN_HOLD_S = 20             # after a button press, stop rotating for this long

# ── failure handling ───────────────────────────────────────────────────────
# Consecutive failures before the loop stops retrying politely and rebuilds the
# thing. The display one matters most: this panel browns out and latches (see
# sh1106.py), so losing it for a few seconds is NORMAL and recovery has to be
# automatic. A display task that can die is worse than no display, because the
# unit looks broken while working perfectly.
FAIL_LIMIT_DISPLAY = 15
FAIL_LIMIT_SENSOR = 10

# ── hardware watchdog ──────────────────────────────────────────────────────
# OFF by default, and that is deliberate. Once armed, a MicroPython WDT cannot
# be stopped short of a reset, so Ctrl-C into the REPL leaves nothing feeding it
# and the board reboots under you every few seconds — which is a miserable way
# to discover the feature. Turn it on when the unit goes in its enclosure and
# stops being something you type at.
WDT_ENABLE = False
WDT_TIMEOUT_MS = 8000

# ── secrets ────────────────────────────────────────────────────────────────
# There are none. v1 has no WiFi, no MQTT, no cloud, nothing that could hold a
# credential — the unit reads the air and draws it on a screen, offline.
#
# If that ever changes: THIS REPOSITORY IS PUBLIC. Credentials go in secrets.py,
# which is gitignored, with a committed secrets_example.py showing the shape.
# Import it defensively so a fresh clone still boots:
#
#     try:
#         from secrets import WIFI
#     except ImportError:
#         WIFI = None
#
# An SSID and password have been committed to one of these repos before. Do not
# make it two.


def _self_check():
    """Cheap sanity on the arithmetic above. Called by main() at boot and
    printed, not raised - a unit with a questionable divider should still come
    up and show you a number you can argue with."""
    notes = []
    v_max = MQ135_VCC * MQ135_DIV_RATIO
    if v_max > 3.30:
        notes.append("divider passes %.2fV at 5V AOUT - ADC pin is 3.3V max" % v_max)
    if v_max < 1.50:
        notes.append("divider wastes range (%.2fV max) - ADC resolution suffers" % v_max)
    if MQ135_RL_EFF < MQ135_RL_OHMS * 0.5:
        notes.append("divider loads RL hard (%.0f -> %.0f ohm); use bigger "
                     "divider resistors" % (MQ135_RL_OHMS, MQ135_RL_EFF))
    return notes


def clean_air_ratio():
    """The Rs/R0 that the curve says corresponds to MQ135_CLEAN_AIR_PPM.

    This is the hinge of the whole calibration. R0 is not "Rs in clean air" —
    it is the resistance that makes the power law return the clean-air
    concentration when fed clean-air Rs:

        ppm = A * (Rs/R0)^B   =>   Rs/R0 = (ppm/A)^(1/B)   =>   R0 = Rs / that

    For A=116.6, B=-2.769, ppm=421 this comes out at 0.629, so R0 lands about
    1.59x above the clean-air Rs. Defining it the other way round (R0 = Rs, so
    ratio 1.0 = clean) would make the index cleaner but push every ppm figure
    out by that same 1.59x, and the two numbers on the detail screen would then
    disagree with each other.
    """
    return math.pow(MQ135_CLEAN_AIR_PPM / MQ135_PPM_A, 1.0 / MQ135_PPM_B)
