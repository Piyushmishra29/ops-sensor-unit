"""
Turning one gas-sensor resistance into something a person can act on.

READ THIS BEFORE YOU RENAME ANYTHING IN HERE.

This is NOT an AQI. A published AQI is defined on measured pollutant
concentrations - PM2.5, PM10, O3, NO2, SO2, CO - each with its own breakpoint
table. An MQ-135 measures none of them. It is a single tin-dioxide element
whose resistance falls in the presence of a whole family of reducing gases:
CO2, VOCs, alcohol, benzene, smoke, ammonia. One number, many causes, no way
to tell them apart.

So the device reports an **AQ index**: 0 means "same as the air I was
calibrated in", 100 means "something is clearly present". It is a relative,
single-sensor indicator - genuinely useful for "is this room stale", "is
solvent evaporating", "did something start smouldering" - and dishonest the
moment it is labelled AQI or PM2.5.

If you want a real AQI, add a particulate sensor (PMS5003, SDS011). The case
has room. Until then the honest answer to "what is the AQI in here" is that
this device cannot know.

The mapping itself
------------------
config gives two anchors as *normalised* Rs (Rs now / Rs on calibration day):

    AQ_NORM_CLEAN = 1.00   -> index   0
    AQ_NORM_FOUL  = 0.15   -> index 100

Rs falls as gas concentration rises, and it falls logarithmically - the
sensor's response is a power law, which is why ppm_from_ratio() in mq135.py is
a power law too. Interpolating linearly between those anchors would waste most
of the scale: the first 10% of index would cover an enormous change in air and
the last 90% would cover almost nothing. So the interpolation is done in log
space, where the sensor's own physics is straight.
"""
import math

import config


# ── the index ──────────────────────────────────────────────────────────────
def index(norm):
    """Normalised Rs -> 0..100 AQ index, or None if there is nothing to say.

    norm is mq135's "norm" field: Rs / Rs-at-calibration. None means the sensor
    has never produced a sample, or has never been calibrated - in both cases
    the only honest output is no number at all, which is why this returns None
    rather than 0. Zero is a claim; None is an admission.
    """
    if norm is None:
        return None
    clean = config.AQ_NORM_CLEAN
    foul = config.AQ_NORM_FOUL
    # Guard the arithmetic rather than trusting config: a zero or negative
    # anchor would make log() explode, and a unit that hard-faults on a bad
    # constant is worse than one that pins the scale.
    if norm <= 0 or clean <= 0 or foul <= 0 or clean == foul:
        return None
    # Log interpolation. Both anchors and the sample go through log(), so equal
    # *ratios* of Rs move the index by equal amounts - which is how the sensor
    # actually behaves.
    span = math.log(clean) - math.log(foul)
    pos = (math.log(clean) - math.log(norm)) / span
    v = int(round(pos * 100.0))
    if v < 0:
        v = 0            # cleaner than calibration day. Believe it, cap it.
    elif v > 100:
        v = 100          # dirtier than the foul anchor. The band already says BAD.
    return v


def band(idx):
    """Index -> short label. Four bands, because a 128x64 mono panel can show
    four states unambiguously and because nobody behaves differently on a
    fifth. Returns "--" for None so the caller never has to special-case it."""
    if idx is None:
        return "--"
    for upper, label in config.AQ_BANDS:
        if idx < upper:
            return label
    return config.AQ_BANDS[-1][1]


def summary(reading):
    """Fold an mq135 reading dict into what the screens want.

    Kept here rather than in display.py so that the display stays a renderer:
    every judgement about the air lives in this file, and the screens only draw
    what they are handed.
    """
    idx = index(reading.get("norm"))
    return {
        "index": idx,
        "band": band(idx),
        "ppm": reading.get("ppm"),
        "trust": reading.get("trust"),      # why the number may be wrong
        "warm": reading.get("warm"),
        "warm_left": reading.get("warm_left"),
        "cal": reading.get("cal"),
    }
