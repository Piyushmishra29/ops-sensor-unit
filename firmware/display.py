"""
Screens for a 128x64 mono panel.

This module draws and nothing else. Every judgement about the air is made in
aq.py; if a screen needs to decide something, the decision belongs upstream.

Design rules for a panel this small:
  - ONE number is the headline. Everything else is support.
  - Contrast beats decoration. An inverted bar reads across a room; a hairline
    border does not.
  - No pixel is spent on a label the reader can infer. "42" over a bar that is
    two-thirds full needs no "index:" in front of it.
  - The band word is the thing people actually act on, so it gets the inverse
    strip at the top where the eye lands first.

Layout budget, 64 rows:
    0..10   band strip      inverted, the word you act on
    12..39  headline        3x AQ number, temp/humidity column, bar gauge
    41..63  trend           sparkline with its own min/max ticks
"""
import config

W = 128
H = 64


# ── helpers ────────────────────────────────────────────────────────────────
def _fmt(v, dp=0, dash="--"):
    """Numbers that may be None. A missing reading prints as dashes; it never
    prints as 0, which would look like a measurement."""
    if v is None:
        return dash
    try:
        return ("%." + str(dp) + "f") % v
    except Exception:
        return dash


def _uptime(ms):
    s = ms // 1000
    if s < 3600:
        return "%d:%02d" % (s // 60, s % 60)
    if s < 86400:
        return "%dh%02d" % (s // 3600, (s % 3600) // 60)
    return "%dd%02dh" % (s // 86400, (s % 86400) // 3600)


def _inv_bar(d, y, h, text_left, text_right=None):
    """Filled strip with knocked-out text. The only way to get real hierarchy
    out of a 1-bit panel."""
    d.fill_rect(0, y, W, h, 1)
    d.text(text_left, 2, y + (h - 8) // 2, 0)
    if text_right:
        d.text(text_right, W - len(text_right) * 8 - 2, y + (h - 8) // 2, 0)


def _gauge(d, x, y, w, h, frac):
    """Horizontal 0..100 bar. Outline always drawn so an empty gauge still
    reads as 'zero', not as 'nothing here'."""
    d.rect(x, y, w, h, 1)
    if frac is None:
        for i in range(x + 2, x + w - 2, 3):        # dashed = no reading
            d.pixel(i, y + h // 2, 1)
        return
    frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
    fill = int((w - 4) * frac)
    if fill > 0:
        d.fill_rect(x + 2, y + 2, fill, h - 4, 1)
    for q in (0.25, 0.5, 0.75):                      # quarter ticks
        tx = x + 2 + int((w - 4) * q)
        d.pixel(tx, y - 1, 1)


def _spark(d, hist, x, y, w, h):
    """Rolling AQ history.

    Scaled to the data, not to 0..100: a room that never leaves 8..14 would be
    a flat line on an absolute scale and tells you nothing. The min and max are
    printed at the ends so nobody reads absolute height off a floating scale.
    """
    pts = [v for v in hist if v is not None]
    if len(pts) < 2:
        d.text("collecting", x + 12, y + h - 8)
        return
    lo, hi = min(pts), max(pts)
    if hi - lo < 4:                       # do not amplify noise into drama
        mid = (hi + lo) / 2.0
        lo, hi = mid - 2, mid + 2
    n = min(len(hist), w)
    tail = hist[-n:]
    prev = None
    for i, v in enumerate(tail):
        if v is None:
            prev = None
            continue
        f = (v - lo) / float(hi - lo)
        f = 0.0 if f < 0 else (1.0 if f > 1 else f)
        py = y + (h - 1) - int(f * (h - 1))
        if prev is not None:               # join the dots: a line reads as a
            a, b = prev                    # trend, scattered pixels do not
            step = 1 if py >= b else -1
            for yy in range(b, py + step, step):
                d.pixel(x + i, yy, 1)
        d.pixel(x + i, py, 1)
        prev = (x + i, py)


# ── screens ────────────────────────────────────────────────────────────────
def screen_main(d, state):
    """The one people read from across the room."""
    s = state["aq"]
    idx = s.get("index")
    band = s.get("band", "--")

    _inv_bar(d, 0, 11, band, _uptime(state.get("uptime_ms", 0)))

    num = "--" if idx is None else str(idx)
    d.big(num, 2, 15, 3)                                  # 24px headline
    d.text("AQ", 2 + len(num) * 24 + 3, 31)

    # right column: temperature over humidity, 2x so they read at a glance
    t, h = state.get("temp"), state.get("hum")
    d.big(_fmt(t, 0), 78, 15, 2)
    d.text("C", 78 + len(_fmt(t, 0)) * 16, 22)
    d.big(_fmt(h, 0), 78, 31, 2)
    d.text("%", 78 + len(_fmt(h, 0)) * 16, 38)

    _gauge(d, 2, 41, 70, 8, None if idx is None else idx / 100.0)

    trust = s.get("trust")
    if trust:
        d.text(trust[:15], 2, 54)
    else:
        _spark(d, state.get("hist", []), 2, 52, 124, 12)


def screen_detail(d, state):
    """The numbers behind the number - for calibrating and for arguing with."""
    r = state["raw"]
    _inv_bar(d, 0, 11, "DETAIL", _uptime(state.get("uptime_ms", 0)))
    d.text("Rs", 2, 15);    d.text(_fmt(r.get("rs"), 0), 34, 15)
    d.text("R0", 2, 25);    d.text(_fmt(r.get("r0"), 0), 34, 25)
    d.text("ratio", 2, 35); d.text(_fmt(r.get("ratio"), 2), 50, 35)
    d.text("CO2~", 2, 45);  d.text(_fmt(r.get("ppm"), 0) + "ppm", 50, 45)
    d.hline(0, 54, W, 1)
    d.text("%sV %s" % (_fmt(r.get("volts"), 2),
                       "corr" if r.get("corrected") else "raw"), 2, 56)


def screen_warmup(d, state):
    """Shown until the heater is up. Not decoration - a cold MQ-135 reads high
    and falling, and a number shown here would be believed."""
    s = state["aq"]
    left = s.get("warm_left") or 0
    _inv_bar(d, 0, 11, "WARMING UP", _uptime(state.get("uptime_ms", 0)))
    d.big("%d:%02d" % (left // 60, left % 60), 26, 17, 3)

    total = float(config.MQ135_WARMUP_S) or 1.0
    _gauge(d, 2, 45, 124, 9, 1.0 - (left / total))

    t, h = state.get("temp"), state.get("hum")
    line = "%sC  %s%%" % (_fmt(t, 0), _fmt(h, 0))
    if not s.get("cal"):
        line += "  UNCAL"
    d.text(line, 2, 56)


def screen_cal(d, state, secs_left, note=""):
    """Live feedback during a clean-air calibration."""
    d.fill(0)
    _inv_bar(d, 0, 11, "CALIBRATING")
    d.big("%02d" % secs_left, 44, 18, 3)
    d.text("CLEAN AIR ONLY", 8, 46)
    if note:
        d.text(note[:16], 2, 56)


SCREENS = (screen_main, screen_detail)


def render(d, state):
    """Draw whichever screen the state asks for. The caller owns show(), so a
    failed draw never leaves half a frame on the panel."""
    d.fill(0)
    if not state["aq"].get("warm"):
        screen_warmup(d, state)
    else:
        SCREENS[state.get("screen", 0) % len(SCREENS)](d, state)
