"""The cells a document drives: the registers' values a modulator slot, a program row, an
instrument field or an event command sets, the phases of a tick that fire them, and the width a
cell wraps its value to."""

CELLS = ("freq", "pw", "cut", "ctrl", "ad", "sr", "res", "route", "mode", "vol")
VOICE_CELLS = ("freq", "pw", "ctrl", "ad", "sr")
SONG_CELLS = ("cut", "res", "route", "mode", "vol")
LATER_CELLS = ("ctrl", "ad", "sr", "res", "route", "mode", "vol")
MASKS = {
    "freq": 0xFFFF,
    "pw": 0x0FFF,
    "cut": 0x07FF,
    "ctrl": 0xFF,
    "ad": 0xFF,
    "sr": 0xFF,
    "res": 0x0F,
    "route": 0x0F,
    "mode": 0x70,
    "vol": 0x0F,
}
PHASE_OF = {cell: "ctl" if cell == "ctrl" else cell for cell in CELLS}
PHASES = ("events", "ctrl", "pulse", "filter") + tuple(PHASE_OF.values()) + ("read",)
LATER_PHASES = ("ctl", "ad", "sr", "res", "route", "mode", "vol")
