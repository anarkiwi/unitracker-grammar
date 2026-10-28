"""The canonical document's model classes (:mod:`unitracker_grammar.document` reads and prints
them): a note is absolute in the model (``C#4``), a list or dict field a tuple."""

import re
from dataclasses import dataclass, field, fields
from typing import NamedTuple

from unitracker_grammar import code as _code

VERSION, VERSION_2_4 = "2.3", "2.4"
NONE, HOLD, RESET, CONT, END = "none", "hold", "reset", "~", "end"
KINDS = ("restart", "ins", "ctrl", "pw", "filter", "phrase", "section")
CELLS = ("freq", "pw", "cut")
LAYERED_KINDS = ("ctrl", "pw", "filter")
_INT = re.compile(r"\d+")
_ROW_KEYS = (
    "wait hold ctrl mask gate note ad sr pw cut res route route_on route_off mode freq run vol"
).split()
_INS_KEYS = "ad sr ctrl pw filter freq restart".split()
_CMD_KEYS = "run pw ad sr ctrl res route mode vol cut tempo vtempo freq legato".split()


class Signed(int):
    """An integer written with its sign: a relative note, a transpose, a signed value."""

    def __str__(self):
        return f"{int(self):+d}"

    __repr__ = __str__


@dataclass(frozen=True)
class Expr:
    """A modulator expression, as its text (:mod:`unitracker_grammar.expr`'s language)."""

    text: str

    def __str__(self):
        return self.text


@dataclass(frozen=True)
class Code:
    """A code template's statements (:mod:`unitracker_grammar.code`): a block in a ``mod``
    record, an anonymous ``asm{...}`` body where it binds a cell."""

    statements: tuple

    @classmethod
    def of(cls, text: str) -> "Code":
        """The checked code of a routine's text, one statement per line."""
        return cls(_code.read(text if text.endswith("\n") else text + "\n"))


class Run(NamedTuple):
    """An inline program after its kind in a ``run:`` or `` run:``: ``pw[{pw:5},end]``."""

    kind: str
    program: object


class Once(NamedTuple):
    """A binding that fires once, then leaves its slot unbound: ``snap()!``."""

    value: object


class Def(NamedTuple):
    """A definition at its first reference: its name (a template's signature) and value, and
    for a template the arguments of its call there (None for a named definition):
    ``i3={ad:9}`` is ``Def("i3", Instrument(...))``, ``vib(c)=asm{...}(4)``
    ``Def("vib(c)", Code(...), (4,))``; a program template's body is a Program, a Run where a
    ``run:`` starts it."""

    name: str
    value: object
    args: tuple | None = None


def _pairs(value) -> tuple:
    return tuple(value.items()) if isinstance(value, dict) else tuple(value)


def _tuple(value):
    return tuple(value) if isinstance(value, list) else value


def base(key: str) -> str:
    """A key without its slot prefix: ``tick.freq`` is ``freq``."""
    return key.rpartition(".")[2]


def _ordered(pairs, order: list) -> tuple:
    """``pairs`` in the grammar's key order, a key's repeats as given."""
    pairs = _pairs(pairs)
    rank = {k: i for i, k in enumerate(order)}
    for key, _ in pairs:
        if base(key) not in rank:
            raise ValueError(f"{key} is not one of {order}")
    return tuple(sorted(pairs, key=lambda kv: rank[base(kv[0])]))


class _Node:  # pylint: disable=too-few-public-methods
    """A model class: its list and dict fields stored as tuples, then its ``_normal``."""

    def __post_init__(self):
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, (list, dict)):
                object.__setattr__(self, f.name, _pairs(value))
        getattr(self, "_normal", lambda: None)()


def _set(obj, name: str, value):
    object.__setattr__(obj, name, value)


@dataclass(frozen=True)
class Row(_Node):
    """A program row: its keys ``(key, value)`` in the grammar's order (``slot.pw`` sorts as
    ``pw``), built from a dict or pairs: ``Row({"wait": 2, "ctrl": 65})``."""

    keys: tuple = ()

    def _normal(self):
        _set(self, "keys", _ordered(self.keys, _ROW_KEYS))

    def get(self, key, default=None):
        """The value of ``key``, its first if repeated."""
        return next((v for k, v in self.keys if k == key), default)


@dataclass(frozen=True)
class Program(_Node):
    """A program: its rows (Rows, or dicts), then ``end`` (``loop`` None) or ``{loop:k}``."""

    rows: tuple = ()
    loop: int | None = None

    def _normal(self):
        _set(self, "rows", tuple(r if isinstance(r, Row) else Row(r) for r in self.rows))


@dataclass(frozen=True)
class Instrument(_Node):
    """An instrument: its fields ``(key, value)`` in the grammar's order."""

    fields: tuple = ()

    def _normal(self):
        _set(self, "fields", _ordered(self.fields, _INS_KEYS))

    def get(self, key, default=None):
        """The value of field ``key``, its first if repeated."""
        return next((v for k, v in self.fields if k == key), default)


@dataclass(frozen=True)
class Event(_Node):
    """An event: its note atom (a note, ``-``, ``off``, ``on``), its instrument (a name or an
    Instrument), its commands ``(key, value)`` in the grammar's order, its keep flags and its
    ``*k`` (None where not written)."""

    note: str
    ins: str | Instrument | None = None
    commands: tuple = ()
    keep_pw: bool = False
    keep_filter: bool = False
    steps: int | None = None

    def _normal(self):
        _set(self, "commands", _ordered(self.commands, _CMD_KEYS))


@dataclass(frozen=True)
class Group(_Node):
    """A group of a phrase's events or of song items: ``body`` played ``times`` (``[...]x2``),
    or before each of ``endings`` in turn (a volta, ``[body|end1|end2]``)."""

    body: tuple
    times: int | None = None
    endings: tuple = ()

    def _normal(self):
        _set(self, "endings", tuple(tuple(e) for e in self.endings))


@dataclass(frozen=True)
class Part(_Node):
    """A song item playing a section (its name, or a Def at its first use) once or ``times``."""

    section: object
    times: int | None = None


@dataclass(frozen=True)
class Play(_Node):
    """A play entry: a phrase (a name, an inline phrase's events, a Def or a phrase template's
    Call of absolute notes) and its transpose (None where not written); the entries ``~`` and
    ``end`` are the strings CONT and END."""

    phrase: str | tuple
    transpose: int | None = None


_CELL = {"pw": "pw", "filter": "cut"}


def _short(kind: str, value):
    """A pulse or filter record's value: a program of one row binding the cell's first slot,
    ``[{pw:b},end]``, is its binding ``b``."""
    rows = value.rows if isinstance(value, Program) and value.loop is None else ()
    keys = rows[0].keys if len(rows) == 1 else ()
    if len(keys) == 1 and keys[0][0] == _CELL.get(kind) and not isinstance(keys[0][1], str):
        return keys[0][1]
    return value


@dataclass(frozen=True)
class Section(_Node):
    """A section of definitions of one kind and its records ``(name, value)``, a template's
    name its :func:`signature`; a pulse or filter record that is one binding is that binding."""

    kind: str
    records: tuple = ()

    def _normal(self):
        if self.kind not in KINDS:
            raise ValueError(f"{self.kind} is not one of {KINDS}")
        _set(
            self,
            "records",
            tuple((k, _short(self.kind, _tuple(v))) for k, v in _pairs(self.records)),
        )


@dataclass(frozen=True)
class SongRow(_Node):
    """A timeline row: its play entries."""

    play: tuple

    def _normal(self):
        _set(
            self,
            "play",
            tuple(p if isinstance(p, Play) or p in (CONT, END) else Play(p) for p in self.play),
        )


@dataclass(frozen=True)
class Voice(_Node):
    """A voice's orderlist: its play entries (Plays and Groups of them), then ``end`` (``loop``
    None) or the top-level entry it loops to."""

    play: tuple
    loop: int | None = None

    def _normal(self):
        _set(self, "play", tuple(p if isinstance(p, (Play, Group)) else Play(p) for p in self.play))


@dataclass(frozen=True)
class Slot(_Node):
    """A modulator slot: its name, its default binding (a name, a Call, a Code or an Expr) and
    the events it holds and resets on (``note-1``, ``row.freq``), None where not written."""

    name: str
    mod: object = None
    hold: tuple | None = None
    reset: tuple | None = None


@dataclass(frozen=True)
class Header(_Node):  # pylint: disable=too-many-instance-attributes
    """The header lines, each None (``meta`` empty) where not written; ``meta`` holds each
    text as written, plain or quoted, ``clock`` is ``(cycles_per_tick, clock_hz)`` or
    ``(cycles_per_tick, clock_hz, "floor")`` (a ``"round"`` third is dropped), ``tempo``
    an int or ``(a, b)``, ``slots`` and ``state`` are ``(cell, ...)`` pairs, ``layers``
    ``(kind, names)`` pairs in LAYERED_KINDS order, ``regs`` the 25 registers' values before
    tick 0, ``lag`` the output's ticks of lag and ``global_cells`` the cells the song owns
    (``("cut",)``)."""

    meta: tuple = ()
    clock: tuple | None = None
    voices: int | None = None
    tempo: int | tuple | None = None
    slots: tuple | None = None
    layers: tuple | None = None
    order: tuple | None = None
    state: tuple | None = None
    regs: tuple | None = None
    lag: int | None = None
    global_cells: tuple | None = None

    def _normal(self):
        if self.clock is not None:
            rounding = tuple(set(self.clock[2:]) - {"round"})
            if not set(rounding) <= {"floor"}:
                raise ValueError(f"clock: rounding {rounding} is not round or floor")
            _set(self, "clock", tuple(self.clock[:2]) + rounding)
        for name in ("regs", "global_cells"):
            if getattr(self, name) is not None:
                _set(self, name, tuple(getattr(self, name)))
        for name in ("slots", "layers", "state"):
            value = getattr(self, name)
            if value is not None:
                _set(self, name, tuple((k, tuple(v)) for k, v in _pairs(value)))
        if self.layers is not None:
            _set(self, "layers", _ordered(self.layers, list(LAYERED_KINDS)))

    def slot(self, cell: str) -> tuple:
        """The Slots of ``cell``: one named after it where the slots line leaves it out."""
        return dict(self.slots or ()).get(cell, (Slot(cell),))


@dataclass(frozen=True)
class Document(_Node):  # pylint: disable=too-many-instance-attributes
    """A whole document: its header, tables ``(name, values)``, templates ``(signature, Expr |
    Code)``, definitions (Sections in KINDS order, or ``{kind: records}``), init events (None
    where not written), song items (SongRows, Parts and Groups) and ending, ``loop`` the item it
    loops to (None for ``end``), or a Voice per voice and ``loop`` None."""

    header: Header = field(default_factory=Header)
    tables: tuple = ()
    mods: tuple = ()
    defs: tuple = ()
    init: tuple | None = None
    rows: tuple = ()
    loop: int | None = None

    def _normal(self):
        _set(self, "tables", tuple((k, tuple(v)) for k, v in _pairs(self.tables)))
        _set(self, "defs", tuple(s if isinstance(s, Section) else Section(*s) for s in self.defs))
        _set(
            self,
            "rows",
            tuple(
                r if isinstance(r, (SongRow, Part, Group, Voice)) else SongRow(r) for r in self.rows
            ),
        )

    @property
    def voiced(self) -> bool:
        """Whether the song is one orderlist per voice."""
        return any(isinstance(r, Voice) for r in self.rows)

    @property
    def version(self) -> str:
        """The format of the version line: VERSION_2_4 where it has layers or orderlists."""
        return VERSION_2_4 if self.header.layers is not None or self.voiced else VERSION

    def records(self, kind: str) -> dict:
        """Every record of ``kind``, ``{name: value}``; ``mod`` the templates."""
        if kind == "mod":
            return dict(self.mods)
        return {k: v for s in self.defs if s.kind == kind for k, v in s.records}


def signature(name: str, params=()) -> str:
    """A template's key, ``name(a,b)``."""
    return f"{name}({','.join(params)})"
