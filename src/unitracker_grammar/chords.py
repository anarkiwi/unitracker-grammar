"""Chord names a call's arguments may hold, each standing for its intervals above the root
(semitones, ascending): music21's chord types within an octave by their longest lowercase
abbreviation, and ``oct``. Written by ``tools/chords.py``."""

CHORDS = {
    "maj": (4, 7),
    "min": (3, 7),
    "aug": (4, 8),
    "dim": (3, 6),
    "dom7": (4, 7, 10),
    "maj7": (4, 7, 11),
    "minmaj7": (3, 7, 11),
    "min7": (3, 7, 10),
    "augmaj7": (4, 8, 11),
    "aug7": (4, 8, 10),
    "m7b5": (3, 6, 10),
    "dim7": (3, 6, 9),
    "dom7dim5": (4, 6, 10),
    "min6": (3, 7, 9),
    "sus2": (2, 7),
    "sus4": (5, 7),
    "power": (7,),
    "oct": (12,),
}
