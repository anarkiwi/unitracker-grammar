"""The note table: ``F(k)``, the SID frequency word of format note ``k`` at a clock, rounded
to the nearest word or down."""

import math

PAL_HZ = 985248
NTSC_HZ = 1022727
A4 = 57
A4_HZ = 440
WORD = 1 << 16
PHASE = 1 << 24
ROUNDINGS = {"round": round, "floor": math.floor}


def frequency(note: int, clock_hz: int = PAL_HZ, rounding: str = "round") -> int:
    """``F(k)``: the frequency word of format note ``k`` (C2 is 24) in equal temperament from
    A4 at 440 Hz, ``rounding`` (``round`` or ``floor``) to a word, for every ``k`` (below C0
    too); 0 where the word rounds to 0 or overflows."""
    word = ROUNDINGS[rounding](A4_HZ * 2 ** ((note - A4) / 12) * PHASE / clock_hz)
    return word if word < WORD else 0


def table(clock_hz: int = PAL_HZ, rounding: str = "round") -> list[int]:
    """``F(k)`` for every note whose word fits, from C0."""
    out = []
    while (word := frequency(len(out), clock_hz, rounding)) > 0:
        out.append(word)
    return out
