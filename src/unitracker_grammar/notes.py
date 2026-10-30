"""The note table: ``F(k)``, the SID frequency word of format note ``k`` at a clock, rounded
to the nearest word."""

PAL_HZ = 985248
NTSC_HZ = 1022727
A4 = 57
A4_HZ = 440
WORD = 1 << 16
PHASE = 1 << 24


def frequency(note: int, clock_hz: int = PAL_HZ) -> int:
    """``F(k)``: ``round(440 * 2**((k - 57)/12) * 2**24 / clock_hz)``, the frequency word of
    format note ``k`` (C2 is 24) in equal temperament from A4 at 440 Hz, for every ``k`` (below
    C0 too); 0 where the word rounds to 0 or reaches 65536."""
    word = round(A4_HZ * 2 ** ((note - A4) / 12) * PHASE / clock_hz)
    return word if word < WORD else 0


def table(clock_hz: int = PAL_HZ) -> list[int]:
    """``F(k)`` for every note whose word fits, from C0."""
    out = []
    while (word := frequency(len(out), clock_hz)) > 0:
        out.append(word)
    return out
