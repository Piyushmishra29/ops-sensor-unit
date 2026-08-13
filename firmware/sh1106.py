"""
SH1106 128x64 I2C OLED — the 1.3" panel, not the 0.96".

ORIGIN: carried over from the author's shopkeeper NANO firmware
(shopkeeper/firmware/sh1106.py). Same author, same part number, same bench.
This is not generic library code — the two notes below are what an afternoon of
debugging bought, which is exactly why the file gets copied between projects
instead of being rewritten from a datasheet each time. The driver class is
byte-for-byte the original. Only attach() differs: its prose argued about
drawers, and this unit has none, so the argument was restated for a sensor.

Two things about this part cost an afternoon on the bench and are encoded here
so they cost nobody else one.

1. COLUMN OFFSET. The SH1106 has 132 columns of RAM behind a 128-pixel panel,
   so the visible window starts at column 2. Driven by an SSD1306 library
   everything sits two pixels left with the wrap showing as a stripe down one
   edge. The 0.96" module IS an SSD1306 and does not want this offset; the 1.3"
   almost always is not.

2. WRITE BEFORE YOU LIGHT IT. Turning the panel on takes the module from about
   0.5 mA to over 20 mA. On a marginal supply it browns out, stops
   acknowledging its own address, and stays dead until the rail is cycled - a
   reset will not clear it, because an ESP32 reset does not drop 3V3. The
   symptom is a screen full of random pixels: the panel lit, then the
   controller fell off the bus before a single byte of frame reached it. So
   show() writes the whole frame with the panel still off and only then sends
   display-on.

   If it dies anyway, the supply is the fault and not this file. Step the
   contrast up while scanning the bus after each step; the level it dies at
   tells you how little headroom there is.

The internal DC-DC command (0xAD 0x8B) is deliberately absent. Modules that
carry their own boost regulator do not want the controller driving one too.
"""
import framebuf

_INIT = (
    0xAE,               # display off - stays off until the frame is in
    0xD5, 0x80,         # clock divide
    0xA8, 0x3F,         # multiplex 64
    0xD3, 0x00,         # display offset
    0x40,               # start line 0
    0xA1,               # segment remap
    0xC8,               # COM scan direction, flipped
    0xDA, 0x12,         # COM pins, alternative
    0xD9, 0x22,         # precharge
    0xDB, 0x35,         # VCOM deselect
    0xA4,               # resume from RAM
    0xA6,               # normal, not inverted
)


class SH1106:
    def __init__(self, i2c, addr=0x3C, width=128, height=64,
                 col_offset=2, contrast=0x60):
        self.i2c, self.addr = i2c, addr
        self.width, self.height = width, height
        self.col_offset = col_offset
        self.pages = height // 8
        self.buf = bytearray(width * self.pages)
        self.fb = framebuf.FrameBuffer(self.buf, width, height,
                                       framebuf.MONO_VLSB)
        self._on = False
        for c in _INIT:
            self.cmd(c)
        self.cmd(0x81); self.cmd(contrast)

    def cmd(self, c):
        self.i2c.writeto(self.addr, bytes([0x80, c]))

    def contrast(self, level):
        self.cmd(0x81); self.cmd(level)

    def show(self):
        """Whole frame, then light it. Order matters - see the module note."""
        w, off = self.width, self.col_offset
        for page in range(self.pages):
            self.cmd(0xB0 | page)
            self.cmd(0x00 | (off & 0x0F))
            self.cmd(0x10 | (off >> 4))
            self.i2c.writeto(self.addr, b"\x40" + self.buf[page*w:(page+1)*w])
        if not self._on:
            self.cmd(0xAF)
            self._on = True

    def poweroff(self):
        self.cmd(0xAE); self._on = False

    # framebuf passthroughs, so callers need not reach into .fb
    def fill(self, c):              self.fb.fill(c)
    def text(self, s, x, y, c=1):   self.fb.text(s, x, y, c)
    def rect(self, x, y, w, h, c=1): self.fb.rect(x, y, w, h, c)
    def fill_rect(self, x, y, w, h, c=1): self.fb.fill_rect(x, y, w, h, c)
    def hline(self, x, y, w, c=1):  self.fb.hline(x, y, w, c)
    def pixel(self, x, y, c=1):     self.fb.pixel(x, y, c)

    def big(self, s, x, y, scale=2, c=1):
        """Scaled text. framebuf ships one 8x8 font and no scaling, so the
        string is rendered into a scratch buffer and each set pixel is blitted
        as a scale x scale block. Cheap enough for a status line; do not call it
        per frame on long strings."""
        w = len(s) * 8
        tmp = bytearray(w * 8 // 8 * 8)
        t = framebuf.FrameBuffer(tmp, w, 8, framebuf.MONO_VLSB)
        t.fill(0); t.text(s, 0, 0, 1)
        for px in range(w):
            for py in range(8):
                if t.pixel(px, py):
                    self.fb.fill_rect(x + px*scale, y + py*scale, scale, scale, c)
        return w * scale

    def width_of(self, s, scale=2):
        return len(s) * 8 * scale


def attach():
    """Build a display from config, or return None if it is absent or refuses.

    Never raises. A sensor whose screen is unplugged must still sample the air -
    the screen is how the reading is delivered, not what the reading is. Losing
    the panel must not stop the loop, and it must not be a boot failure either.
    """
    import config
    import time
    if not getattr(config, "OLED", True):
        return None
    try:
        from machine import Pin, I2C
        i2c = I2C(0, scl=Pin(config.OLED_SCL), sda=Pin(config.OLED_SDA),
                  freq=config.OLED_FREQ)
    except Exception:
        return None
    # Retry, do not scan once. The MQ-135 heater is the peak current draw of
    # this whole unit and it switches on the instant the rail comes up - the
    # supply sags, the module stops acknowledging, and a single scan taken at
    # that instant reports no display on a unit that has one. This is the same
    # failure the shopkeeper cabinet showed while parking two servos: "display:
    # none" at boot, 0x3C on the very next manual scan.
    for attempt in range(6):
        try:
            if config.OLED_ADDR in i2c.scan():
                return SH1106(i2c, config.OLED_ADDR,
                              contrast=config.OLED_CONTRAST)
        except Exception:
            pass
        time.sleep_ms(250)
    return None
