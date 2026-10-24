"""Writes ``src/unitracker_grammar/chords.py`` from music21's chord types within an octave:
each type's longest abbreviation that is a lowercase name, and its pitch classes above the root,
ascending; a type whose intervals an earlier one has is left out."""

import re
import sys
from pathlib import Path

from music21 import harmony

OUT = Path(__file__).resolve().parents[1] / "src" / "unitracker_grammar" / "chords.py"
_NAME = re.compile(r"[a-z][a-z0-9]*")
EXTRA = {"oct": (12,)}


def table() -> dict:
    """``{name: intervals}`` of music21's chord types with a lowercase abbreviation, and the
    octave."""
    out = {}
    for kind, (degrees, abbreviations) in harmony.CHORD_TYPES.items():
        names = [a for a in abbreviations if _NAME.fullmatch(a)]
        if not names or any(d.lstrip("-#") in ("9", "11", "13") for d in degrees.split(",")):
            continue
        symbol = harmony.ChordSymbol(root="C4", kind=kind)
        base = symbol.root().midi
        intervals = tuple(sorted({(p.midi - base) % 12 for p in symbol.pitches} - {0}))
        if intervals and intervals not in out.values():
            out[max(names, key=len)] = intervals
    return out | EXTRA


DOC = (
    "Chord names a call's arguments may hold, each standing for its intervals above the root\n"
    "(semitones, ascending): music21's chord types within an octave by their longest lowercase\n"
    "abbreviation, and ``oct``. Written by ``tools/chords.py``."
)


def text() -> str:
    """The module's text."""
    rows = "".join(f'    "{k}": {v!r},\n' for k, v in table().items())
    return f'"""{DOC}"""\n\nCHORDS = {{\n{rows}}}\n'


if __name__ == "__main__":
    OUT.write_text(text(), encoding="utf-8")
    sys.exit(0)
