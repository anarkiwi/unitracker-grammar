"""The note table: ``F(k)``, the SID frequency word of format note ``k`` at a clock."""

PAL_HZ = 985248
NTSC_HZ = 1022727
A4 = 57
A4_HZ = 440
WORD = 1 << 16
PHASE = 1 << 24


def frequency(note: int, clock_hz: int = PAL_HZ) -> int:
    """``F(k)``: the frequency word of format note ``k`` (C2 is 24) in equal temperament from
    A4 at 440 Hz, rounded to the nearest word; 0 below C0 and where the word overflows."""
    if note < 0:
        return 0
    word = round(A4_HZ * 2 ** ((note - A4) / 12) * PHASE / clock_hz)
    return word if word < WORD else 0


def table(clock_hz: int = PAL_HZ) -> list[int]:
    """``F(k)`` for every note whose word fits, from C0."""
    out = []
    while (word := frequency(len(out), clock_hz)) > 0:
        out.append(word)
    return out
