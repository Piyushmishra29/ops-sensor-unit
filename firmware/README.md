# OPS Sensor Unit — firmware

MicroPython, offline, no external libraries. Verified running on an
**ESP32-WROOM-32D** with MicroPython v1.28.0.

## Wiring (classic ESP32 — NOT S3 pins)

| ESP32 | Component |
|---|---|
| GPIO21 | OLED SDA |
| GPIO22 | OLED SCL |
| 3V3 | OLED VCC + DHT11 VCC |
| GPIO4 | DHT11 DATA |
| GPIO34 | MQ-135 AOUT **via divider** |
| 5V / VIN | MQ-135 VCC (heater needs 5 V) |
| GPIO25 | optional button to GND |
| GND | OLED, DHT11, MQ-135, divider bottom |

**The divider is mandatory.** AOUT swings to 5 V; an ESP32 ADC pin is 3.3 V max.

```
MQ-135 AOUT ──[10k]──┬──► GPIO34
                     │
                  [15k]
                     │
                    GND
```

Pin rules on this chip: **GPIO6–11 are the SPI flash — never use them.**
GPIO0/2/12/15 are strapping pins. GPIO34–39 are input-only (fine for the
MQ-135, useless for the DHT11). The MQ-135 must sit on **ADC1** (GPIO32–39):
ADC2 stops working the moment anyone enables WiFi.

## Flashing

```bash
pip install esptool mpremote
esptool --port /dev/ttyUSB0 erase_flash
esptool --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-*.bin
for f in sh1106.py config.py mq135.py aq.py display.py main.py boot.py; do
  mpremote connect /dev/ttyUSB0 cp $f :
done
mpremote connect /dev/ttyUSB0 run main.py     # or just reset — boot.py→main.py
```

## First run

1. **Warm-up** — 3 minutes on every boot. The display shows a countdown; no
   gas number is presented before it finishes, because a cold element reads
   high and falling.
2. **Burn-in** — a new MQ-135 wants 24–48 h powered before its baseline stops
   wandering. It responds to gas long before that; the absolute numbers just
   keep moving.
3. **Calibrate** — hold the button at boot for 3 s, **outdoors or at an open
   window**. This measures R0 against outdoor background CO₂ (421 ppm).
   Calibrating in a closed room bakes that room in and the unit reads it as
   perfect forever. Note a HEPA purifier's output is *not* a substitute: it
   removes particles and VOCs, not CO₂.

## What it measures

Temperature and humidity honestly (±2 °C, ±5 % RH). For air it reports an
**AQ index 0–100 with a band** (GOOD/FAIR/POOR/BAD) derived from Rs relative
to calibration-day Rs — a relative, single-sensor indicator of reducing gases
(CO₂, VOCs, smoke, alcohol, ammonia).

**It is not an AQI and cannot be.** An MQ-135 cannot see particulates. See the
comment block at the top of `aq.py`. Add a PMS5003/SDS011 for real PM2.5.

## Files

| File | Role |
|---|---|
| `config.py` | every pin, constant and threshold, with the reasoning |
| `sh1106.py` | 1.3" OLED driver (from the author's *shopkeeper* project) |
| `mq135.py` | ADC → Rs → Rs/R0 → ppm, calibration, T/RH correction, warm-up gate |
| `aq.py` | Rs → index and band, in log space |
| `display.py` | screens: main, detail, warm-up, calibration |
| `main.py` | init, sensor intervals, history, screen cycling, fault tolerance |

## Measured on hardware

| | |
|---|---|
| OLED | 0x3C on SDA 21 / SCL 22 |
| DHT11 | 27 °C, 62 % RH |
| MQ-135 | 1.54 V idle → Rs ≈ 13 kΩ |
| Filtered air vs room air | Rs **+11.7 %** in filtered air — correct polarity |
