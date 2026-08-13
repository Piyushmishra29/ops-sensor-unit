"""
Screens for a 128x64 mono panel.

This module draws and nothing else. Every judgement about the air is made in
aq.py; if a screen needs to decide something, the decision belongs upstream.

Layout budget, because 64 rows disappear fast:

    rows  0..7    status strip   unit name, uptime, trust flag
    rows  9..40   the payload    differs per screen
    rows 42..63   the extras     temp/humidity, or the sparkline

The framebuf font is 8x8 and there is no other. big() blits it at 2x or 3x for
the headline number. Anything smaller than 8px is not available, so the layout
is designed around whole 8px cells rather than fighting for pixels.
"""
import config


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
        return "%dm%02ds" % (s // 60, s % 60)
    if s < 86400:
        return "%dh%02dm" % (s // 3600, (s % 3600) // 60)
    return "%dd%02dh" % (s // 86400, (s % 86400) // 3600)


def _strip(d, state):
    """Top status strip, common to every screen."""
    d.text(config.UNIT, 0, 0)
    up = _uptime(state.get("uptime_ms", 0))
    d.text(up, 128 - len(up) * 8, 0)
    d.hline(0, 8, 128)


def _sparkline(d, hist, x, y, w, h):
    """Rolling AQ history as a column chart.

    Scaled to the data, not to 0..100: a room that never leaves 8..14 would be
    a flat line on an absolute scale and tells you nothing. A floating scale
    shows the shape of the day, which is the only thing a 20-pixel-tall strip
    can usefully convey. The caller labels it so nobody reads absolute height
    off it.
    """
    pts = [v for v in hist if v is not None]
    if len(pts) < 2:
        d.text("...", x, y + h - 8)
        return
    lo, hi = min(pts), max(pts)
    if hi - lo < 4:                 # avoid amplifying sensor noise into a
        mid = (hi + lo) / 2.0       # dramatic mountain range
        lo, hi = mid - 2, mid + 2
    n = min(len(hist), w)
    tail = hist[-n:]
    for i, v in enumerate(tail):
        if v is None:
            continue
        frac = (v - lo) / float(hi - lo)
        if frac < 0:
            frac = 0.0
        elif frac > 1:
            frac = 1.0
        bar = int(frac * (h - 1))
        d.fill_rect(x + i, y + (h - 1 - bar), 1, bar + 1)


# ── screens ────────────────────────────────────────────────────────────────
def screen_main(d, state):
    """The one people actually read: big AQ number, band, temp, humidity."""
    s = state["aq"]
    idx = s.get("index")
    _strip(d, state)

    num = "--" if idx is None else str(idx)
    d.big(num, 0, 12, 3)                       # 24px tall, the headline
    d.text("AQ", len(num) * 24 + 4, 14)
    band = s.get("band", "--")
    d.text(band, len(num) * 24 + 4, 26)

    # right-hand column: temperature and humidity, 8px rows
    t, h = state.get("temp"), state.get("hum")
    d.text("%sC" % _fmt(t, 0), 78, 14)
    d.text("%s%%" % _fmt(h, 0), 78, 26)

    # bottom strip: sparkline, or the reason there is no number
    d.hline(0, 41, 128)
    trust = s.get("trust")
    if trust:
        d.text(trust[:16], 0, 45)
    else:
        d.text("30m", 0, 45)
        _sparkline(d, state.get("hist", []), 30, 44, 96, 19)


def screen_detail(d, state):
    """The numbers behind the number - for calibrating and for arguing with."""
    r = state["raw"]
    _strip(d, state)
    d.text("Rs   %s" % _fmt(r.get("rs"), 0), 0, 12)
    d.text("R0   %s" % _fmt(r.get("r0"), 0), 0, 22)
    ratio = r.get("ratio")
    d.text("Rs/R0 %s" % _fmt(ratio, 2), 0, 32)
    d.text("CO2~ %s ppm" % _fmt(r.get("ppm"), 0), 0, 42)
    d.hline(0, 52, 128)
    d.text("%sV %s" % (_fmt(r.get("volts"), 2),
                       "corr" if r.get("corrected") else "raw"), 0, 55)


def screen_warmup(d, state):
    """Shown until the heater is up. Not decoration - a cold MQ-135 reads high
    and falling, and a number shown here would be believed."""
    s = state["aq"]
    _strip(d, state)
    d.text("HEATER WARMING", 4, 14)
    left = s.get("warm_left") or 0
    d.big("%02d:%02d" % (left // 60, left % 60), 12, 26, 2)
    total = float(config.MQ135_WARMUP_S) or 1.0
    done = 1.0 - (left / total)
    if done < 0:
        done = 0.0
    elif done > 1:
        done = 1.0
    d.rect(4, 48, 120, 8)
    d.fill_rect(5, 49, int(118 * done), 6)
    if not s.get("cal"):
        d.text("uncalibrated", 4, 58)


def screen_cal(d, state, secs_left, note=""):
    """Live feedback during a clean-air calibration."""
    d.fill(0)
    d.text("CALIBRATING", 20, 4)
    d.hline(0, 14, 128)
    d.big("%02d" % secs_left, 46, 20, 3)
    d.text("clean air only", 8, 46)
    if note:
        d.text(note[:16], 0, 56)


SCREENS = (screen_main, screen_detail)


def render(d, state):
    """Draw whichever screen the state asks for. Returns nothing; the caller
    owns show(), so a failed draw never leaves half a frame on the panel."""
    d.fill(0)
    if not state["aq"].get("warm"):
        screen_warmup(d, state)
    else:
        SCREENS[state.get("screen", 0) % len(SCREENS)](d, state)
