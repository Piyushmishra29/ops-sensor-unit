"""
OPS Sensor Unit — main loop.

Shape of the thing:

    boot   -> bring up display, gas sensor, DHT11. None of them is allowed to
              be fatal: a unit with a dead screen must still sample, and a unit
              with a dead sensor must still say so on the screen.
    loop   -> poll each sensor on its own interval (the DHT11 cannot be rushed),
              fold the readings into one state dict, hand that to display.py.
    faults -> counted, not raised. A jumper that falls out mid-shift should
              degrade the display, not stop the device.

Timing is interval-based rather than sleep-based so that a slow DHT11 read
(they block for ~25 ms and sometimes much longer) does not drag the display
refresh with it.
"""
import gc
import sys
import time

from machine import Pin

import config
import aq
import display as ui
import mq135
import sh1106


# ── hardware, each optional ────────────────────────────────────────────────
def _init_display():
    try:
        d = sh1106.attach()
        if d:
            d.contrast(config.OLED_CONTRAST)
            d.fill(0)
            d.text("OPS SENSOR", 24, 20)
            d.text(config.FW, 48, 34)
            d.show()
        return d
    except Exception as e:
        print("display init failed:", e)
        return None


def _init_dht():
    """DHT11 on a bidirectional pin. Import guarded because a board without the
    dht module should still run the gas sensor."""
    try:
        import dht
        return dht.DHT11(Pin(config.DHT_PIN))
    except Exception as e:
        print("dht init failed:", e)
        return None


def _init_button():
    if config.BUTTON_PIN is None:
        return None
    try:
        return Pin(config.BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    except Exception as e:
        print("button init failed:", e)
        return None


def _pressed(btn):
    if btn is None:
        return False
    v = btn.value()
    return (v == 0) if config.BUTTON_ACTIVE_LOW else (v == 1)


# ── calibration entry point ────────────────────────────────────────────────
def _maybe_calibrate(mq, d, btn):
    """Hold the button at boot to re-measure R0 in clean air.

    Deliberately gated behind a hold rather than a tap: calibrating in the
    wrong air bakes a bad baseline into every later reading, and it is the one
    action here that is hard to undo without a serial console.
    """
    if not _pressed(btn):
        return
    t0 = time.ticks_ms()
    while _pressed(btn):
        held = time.ticks_diff(time.ticks_ms(), t0) // 1000
        if d:
            d.fill(0)
            d.text("HOLD TO CAL", 20, 18)
            d.big(str(max(0, config.BUTTON_CAL_HOLD_S - held)), 56, 32, 2)
            d.show()
        if held >= config.BUTTON_CAL_HOLD_S:
            break
        time.sleep_ms(100)
    else:
        return                                  # released early: do nothing

    def progress(i, n, good):
        if d:
            ui.screen_cal(d, None, max(0, n - i), "%d ok" % good)
            d.show()

    try:
        r0, note = mq.calibrate(progress=progress)
        print("calibrated R0=%s (%s)" % (r0, note))
        if d:
            d.fill(0)
            d.text("CALIBRATED", 24, 20)
            d.text("R0 %d" % (r0 or 0), 32, 34)
            d.show()
            time.sleep(2)
    except Exception as e:
        print("calibration failed:", e)
        if d:
            d.fill(0); d.text("CAL FAILED", 24, 24); d.text(str(e)[:16], 0, 40)
            d.show(); time.sleep(3)


# ── main ───────────────────────────────────────────────────────────────────
def main():
    print("OPS Sensor Unit %s  fw %s" % (config.UNIT, config.FW))
    for note in config._self_check():
        print("config:", note)

    d = _init_display()
    mq = mq135.MQ135()
    dht_dev = _init_dht()
    btn = _init_button()
    _maybe_calibrate(mq, d, btn)

    wdt = None
    if config.WDT_ENABLE:
        try:
            from machine import WDT
            wdt = WDT(timeout=config.WDT_TIMEOUT_MS)
        except Exception as e:
            print("wdt unavailable:", e)

    temp = hum = None
    hist = []
    reading = mq.read()
    state = {"aq": aq.summary(reading), "raw": reading, "temp": None,
             "hum": None, "hist": hist, "screen": 0, "uptime_ms": 0}

    t_boot = time.ticks_ms()
    nxt_dht = nxt_mq = nxt_ui = nxt_hist = time.ticks_ms()
    nxt_rot = time.ticks_add(time.ticks_ms(), config.SCREEN_DWELL_S * 1000)
    fail_dht = fail_mq = fail_ui = 0
    btn_was = False

    while True:
        now = time.ticks_ms()

        # ── button: cycle screens, and pause auto-rotation while in use ────
        p = _pressed(btn)
        if p and not btn_was:
            state["screen"] = (state.get("screen", 0) + 1) % len(ui.SCREENS)
            nxt_rot = time.ticks_add(now, config.SCREEN_HOLD_S * 1000)
            nxt_ui = now                        # redraw immediately, feels crisp
        btn_was = p

        if time.ticks_diff(now, nxt_rot) >= 0:
            state["screen"] = (state.get("screen", 0) + 1) % len(ui.SCREENS)
            nxt_rot = time.ticks_add(now, config.SCREEN_DWELL_S * 1000)

        # ── DHT11: slow, fragile, and never allowed to stop the loop ───────
        if time.ticks_diff(now, nxt_dht) >= 0:
            nxt_dht = time.ticks_add(now, config.DHT_INTERVAL_MS)
            if dht_dev:
                try:
                    dht_dev.measure()
                    temp = dht_dev.temperature()
                    hum = dht_dev.humidity()
                    fail_dht = 0
                except Exception:
                    fail_dht += 1
                    if fail_dht >= config.FAIL_LIMIT_SENSOR:
                        temp = hum = None       # stop showing a stale number
            state["temp"], state["hum"] = temp, hum

        # ── MQ-135 ─────────────────────────────────────────────────────────
        if time.ticks_diff(now, nxt_mq) >= 0:
            nxt_mq = time.ticks_add(now, config.MQ_INTERVAL_MS)
            try:
                reading = mq.read(temp, hum)
                state["raw"] = reading
                state["aq"] = aq.summary(reading)
                fail_mq = 0
            except Exception as e:
                fail_mq += 1
                if fail_mq >= config.FAIL_LIMIT_SENSOR:
                    print("mq135 failing:", e)

        # ── history for the sparkline ──────────────────────────────────────
        if time.ticks_diff(now, nxt_hist) >= 0:
            nxt_hist = time.ticks_add(now, config.HISTORY_INTERVAL_S * 1000)
            hist.append(state["aq"].get("index"))
            while len(hist) > config.HISTORY_LEN:
                hist.pop(0)

        # ── draw ───────────────────────────────────────────────────────────
        if d and time.ticks_diff(now, nxt_ui) >= 0:
            nxt_ui = time.ticks_add(now, config.DISPLAY_INTERVAL_MS)
            state["uptime_ms"] = time.ticks_diff(now, t_boot)
            try:
                ui.render(d, state)
                d.show()
                fail_ui = 0
            except Exception as e:
                fail_ui += 1
                if fail_ui >= config.FAIL_LIMIT_DISPLAY:
                    print("display lost:", e)
                    d = None                    # keep sampling without it

        if wdt:
            wdt.feed()
        gc.collect()
        time.sleep_ms(config.LOOP_TICK_MS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("stopped")
    except Exception:
        # Print the traceback and stop rather than reboot-looping: a unit that
        # reboots every 3 s is much harder to diagnose over a serial console
        # than one sitting at a prompt with the reason on screen.
        sys.print_exception(sys.exc_info()[1]) if hasattr(sys, "exc_info") else None
        raise
