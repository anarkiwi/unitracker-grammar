"""The note table against pysidtracker's, the table the spec players answer reads with."""

import pytest

from unitracker_grammar import NTSC_HZ, PAL_HZ, frequency

notes = pytest.importorskip("pysidtracker.notes")


@pytest.mark.parametrize("clock_hz", [PAL_HZ, NTSC_HZ])
def test_the_note_table_is_pysidtrackers_standard_word_for_every_note(clock_hz):
    for note in range(-30, 300):
        assert frequency(note, clock_hz) == notes.frequency(note, clock_hz), note
