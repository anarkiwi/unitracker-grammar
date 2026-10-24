"""The canonical document as a typed model: :func:`read` builds it from a text, its classes
build one directly, and :func:`printed` writes its one canonical text, wrapped as PyYAML's
emitter wraps at width 100 (the README's "Documents" section).
"""

import functools
import re
from dataclasses import dataclass, field, fields, replace
from typing import NamedTuple

from lark import Lark, Token, Transformer, exceptions, v_args

from unitracker_grammar import code as _code
from unitracker_grammar.canonical import GRAMMAR, CanonicalError
from unitracker_grammar.code import Call

__all__ = [
    "CELLS",
    "CONT",
    "END",
    "HOLD",
    "KINDS",
    "NONE",
    "WIDTH",
    "Bound",
    "Call",
    "Code",
    "Document",
    "Event",
    "Expr",
    "Header",
    "Instrument",
    "Play",
    "Program",
    "Row",
    "Run",
    "Section",
    "Shape",
    "Signed",
    "Slot",
    "SongRow",
    "base",
    "printed",
    "read",
    "replace",
    "signature",
]

WIDTH = 100
NONE, HOLD, CONT, END = "none", "hold", "~", "end"
KINDS = ("restart", "ins", "ctrl", "pw", "filter", "mod", "x", "phrase")
CELLS = ("freq", "pw", "cut")
_HARD = "\x00"  # a space the grammar spells literally, never a line wrap
_WRAP = re.compile(r"\n +")
_OPENED = re.compile(r"([\[{])\n +")
_INT = re.compile(r"\d+")
_ROW_KEYS = "wait hold ctrl gate note ad sr pw cut res route mode freq run filter vol".split()
_INS_KEYS = "ad sr ctrl pw filter freq mod restart".split()
_CMD_KEYS = "run pw filter ad sr ctrl resfilt mode vol cut tempo vtempo freq set legato".split()


class Signed(int):
    """An integer written with its sign: a relative note, a transpose, a signed value."""

    def __str__(self):
        return f"{int(self):+d}"

    __repr__ = __str__


@dataclass(frozen=True)
class Expr:
    """A modulator expression, as its text (:mod:`unitracker_grammar.expr`'s language);
    ``quoted`` where it is written quoted though no comma asks for it."""

    text: str
    quoted: bool = field(default=False, compare=False)

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


class Bound(NamedTuple):
    """A 1.22 template bound with its parameter bag: ``porta {s: 32}``."""

    expr: object
    bag: tuple = ()


class Shape(NamedTuple):
    """An instrument's ``mod:`` shape and its parameter bag: ``mod: ramp {step: 2}``."""

    name: str
    bag: tuple = ()


class Run(NamedTuple):
    """A program after its kind in a ``run:`` or ``!run:``: inline, ``pw[{pw: 5}, end]``, or
    a template's Call, ``ctrl:arp(7,4)``."""

    kind: str
    program: object


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
    """A program: its rows (Rows, or dicts), then ``end`` (``loop`` None) or ``{loop: k}``."""

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
class Play(_Node):
    """A play entry: a phrase (a name, or an inline phrase's events) and its transpose (None
    where not written); the entries ``~`` and ``end`` are the strings CONT and END."""

    phrase: str | tuple
    transpose: int | None = None


@dataclass(frozen=True)
class Section(_Node):
    """A row's ``def`` section of one kind and its records ``(name, value)``; a ``mod``
    record's name is its key, a NAME or a :func:`signature`."""

    kind: str
    records: tuple = ()

    def _normal(self):
        if self.kind not in KINDS:
            raise ValueError(f"{self.kind} is not one of {KINDS}")
        _set(self, "records", tuple((k, _tuple(v)) for k, v in _pairs(self.records)))


@dataclass(frozen=True)
class SongRow(_Node):
    """A timeline row: its play entries and its definitions (Sections, or ``(kind,
    records)`` pairs, a dict)."""

    play: tuple
    defs: tuple = ()

    def _normal(self):
        _set(self, "defs", tuple(s if isinstance(s, Section) else Section(*s) for s in self.defs))
        _set(
            self,
            "play",
            tuple(p if isinstance(p, Play) or p in (CONT, END) else Play(p) for p in self.play),
        )


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
    text as written, plain or quoted, ``clock`` is ``(cycles_per_tick, clock_hz)``, ``tempo``
    an int or ``(a, b)``, and ``hold``, ``slots`` and ``state`` are ``(cell, ...)`` pairs."""

    version: str = "1.23"
    meta: tuple = ()
    clock: tuple | None = None
    voices: int | None = None
    tempo: int | tuple | None = None
    hold: tuple | None = None
    slots: tuple | None = None
    order: tuple | None = None
    state: tuple | None = None

    def _normal(self):
        for name in ("hold", "slots", "state"):
            value = getattr(self, name)
            if value is not None:
                _set(self, name, tuple((k, tuple(v)) for k, v in _pairs(value)))

    def slot(self, cell: str) -> tuple:
        """The Slots of ``cell``: one named after it where the slots line leaves it out."""
        return dict(self.slots or ()).get(cell, (Slot(cell),))


@dataclass(frozen=True)
class Document(_Node):  # pylint: disable=too-many-instance-attributes
    """A whole document: its header, tables ``(name, values)``, top-level templates
    ``(signature, Expr | Code)``, top-level definitions (Sections, or ``{kind: records}``),
    init events (None where not written), timeline rows and ending, ``loop`` the row it loops
    to (None for ``end``); ``layout`` pairs a printed line with its text as read otherwise."""

    header: Header = field(default_factory=Header)
    tables: tuple = ()
    mods: tuple = ()
    defs: tuple = ()
    init: tuple | None = None
    rows: tuple = ()
    loop: int | None = None
    layout: tuple = field(default=(), compare=False, repr=False)

    def _normal(self):
        _set(self, "tables", tuple((k, tuple(v)) for k, v in _pairs(self.tables)))
        _set(self, "defs", tuple(s if isinstance(s, Section) else Section(*s) for s in self.defs))
        _set(self, "rows", tuple(r if isinstance(r, SongRow) else SongRow(*r) for r in self.rows))

    def sections(self, kind: str) -> list:
        """``(row index, Section)`` of every section of ``kind``, in document order, a
        top-level one's index None."""
        top = [(None, s) for s in self.defs if s.kind == kind]
        return top + [(i, s) for i, r in enumerate(self.rows) for s in r.defs if s.kind == kind]

    def records(self, kind: str) -> dict:
        """Every record of ``kind``, ``{name: value}``; ``mod``'s top-level templates first."""
        out = dict(self.mods) if kind == "mod" else {}
        for _, section in self.sections(kind):
            out.update(section.records)
        return out


def signature(name: str, params=()) -> str:
    """A template's key, ``name(a, b)``."""
    return f"{name}({', '.join(params)})"


# ---- reading ------------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _parser() -> Lark:
    return Lark(
        GRAMMAR.read_text(encoding="utf-8"),
        parser="lalr",
        lexer="contextual",
        propagate_positions=True,
    )


class _Chain(list):
    """A key chain's ``(key, value)`` pairs from a link on."""


def _leaf(token: Token):
    if token.type == "INT":
        return int(token)
    if token.type == "SIGNED":
        return Signed(token)
    if token.type == "CALL":
        name, args = _code.call(token).name, token[token.index("(") + 1 : -1].split(",")
        return Call(name, tuple(_argument(a) for a in args if a))
    return _WRAP.sub(" ", str(token))


def _argument(text: str):
    """A call's argument: an int, a Signed where written with its sign, or a parameter."""
    if text[0].isalpha():
        return text
    return Signed(text) if text[0] in "+-" else int(text)


def _value(value):
    """A binding where an integer and its expression are one text: the int."""
    if isinstance(value, Token):
        return _leaf(value)
    if isinstance(value, Expr) and not value.quoted and _INT.fullmatch(value.text):
        return int(value.text)
    return value


def _pair(values):
    return values[0] if len(values) == 1 else tuple(values)


def _link(key, convert=lambda own: own[0], normal=_value):
    """A key chain's link: its own ``(key, value)``, a slot prefix's key, then the rest."""

    def method(_self, children):
        rest, own, prefix = _Chain(), [], ""
        for c in children:
            if isinstance(c, _Chain):
                rest = c
            elif isinstance(c, Token) and c.type == "SLOT":
                prefix = str(c)
            elif isinstance(c, Token) and c.type.startswith("CMD_"):
                prefix = c[1 : -1 - len(key)]
            else:
                own.append(normal(c))
        return _Chain([(prefix + key, convert(own))] + rest) if own else rest

    return method


def _token(value):
    """A command's value: a token's, an expression kept as quoted."""
    return _leaf(value) if isinstance(value, Token) else value


class _ToModel(Transformer):
    """The parse tree of ``canonical.lark`` to a Document; each method the rule of its name."""

    # pylint: disable=missing-function-docstring,too-many-public-methods

    def __init__(self, text: str):
        super().__init__()
        self.source = text

    @v_args(meta=True)
    def expr(self, meta, _children):
        text = _WRAP.sub(" ", self.source[meta.start_pos : meta.end_pos])
        return Expr(text, "," not in text and self.source[meta.start_pos - 1] == "'")

    @staticmethod
    def start(children):
        head, body = {"version": str(children[0])}, {"rows": []}
        for c in children[1:]:
            if isinstance(c, SongRow):
                body["rows"].append(c)
            elif isinstance(c, Section):
                body["defs"] = (*body.get("defs", ()), c)
            elif c[0] in ("tables", "mods", "init", "loop"):
                body[c[0]] = c[1]
            else:
                head[c[0]] = c[1]
        return Document(Header(**head), **body)

    @staticmethod
    def meta(children):
        return ("meta", tuple(children))

    @staticmethod
    def meta_item(children):
        return (str(children[0]), children[1])

    @staticmethod
    def text(children):
        return _leaf(children[0])

    @staticmethod
    def clock(children):
        return ("clock", tuple(int(c) for c in children))

    @staticmethod
    def voices(children):
        return ("voices", int(children[0]))

    @staticmethod
    def tempo(children):
        return ("tempo", _pair([int(c) for c in children]))

    @staticmethod
    def hold(children):
        return ("hold", tuple(children))

    @staticmethod
    def hold_cell(children):
        return (str(children[0]), children[1])

    @staticmethod
    def events(children):
        return tuple(str(c) for c in children)

    @staticmethod
    def slots(children):
        return ("slots", tuple(children))

    @staticmethod
    def slot_cell(children):
        return (str(children[0]), tuple(children[1:]))

    @staticmethod
    def slot(children):
        return Slot(str(children[0]), **dict(children[1] if len(children) > 1 else ()))

    @staticmethod
    def order(children):
        return ("order", tuple(str(c) for c in children))

    @staticmethod
    def state(children):
        return ("state", tuple(children[0]))

    @staticmethod
    def state_vars(children):
        return tuple((str(v.children[0]), int(v.children[1])) for v in children)

    @staticmethod
    def tables(children):
        return ("tables", tuple(zip(map(str, children[::2]), children[1::2])))

    @staticmethod
    def intlist(children):
        return tuple(int(c) for c in children)

    @staticmethod
    def mods(children):
        return ("mods", tuple(zip(map(str, children[::2]), children[1::2])))

    @staticmethod
    def init(children):
        return ("init", tuple(children))

    @staticmethod
    def row(children):
        return SongRow(children[-1], tuple(children[:-1]))

    @staticmethod
    def ending(children):
        return ("loop", int(children[0]) if children else None)

    @staticmethod
    def plays(children):
        return tuple(children)

    @staticmethod
    def play(children):
        first = children[0]
        if isinstance(first, Token) and first.type in ("CONT", "END"):
            return str(first)
        phrase = str(first) if isinstance(first, Token) else first
        return Play(phrase, Signed(children[1]) if len(children) > 1 else None)

    @staticmethod
    def section(children):
        kind = {"NAME": "mod", "SIGNATURE": "mod", "INS": "ins"}.get(
            children[0].type, children[0].type.lower().removesuffix("_sig")
        )
        records = []
        for c in children:
            if isinstance(c, Token):
                records.append([str(c)])
            elif isinstance(c, dict):
                records[-1][1] = Bound(records[-1][1], tuple(c.items()))
            else:
                records[-1].append(_value(c) if kind in ("pw", "filter", "x") else c)
        return Section(kind, tuple(tuple(r) for r in records))

    @staticmethod
    def instrument(children):
        return Instrument(children[0] if children else ())

    @staticmethod
    def program(children):
        last = children[-1]
        loop = int(last) if isinstance(last, Token) and last.type == "INT" else None
        return Program(tuple(c for c in children if isinstance(c, Row)), loop)

    @staticmethod
    def modulation(children):
        return _value(children[0])

    cell_value = modulation

    @staticmethod
    def bound(children):
        return Bound(children[0], tuple(children[1].items()))

    @staticmethod
    def fexpr(children):
        return children[0]

    @staticmethod
    def param_bag(children):
        return dict(children)

    @staticmethod
    def pname_val(children):
        return (str(children[0]), _value(children[1]))

    @staticmethod
    def pname_list(children):
        return tuple(_leaf(c) for c in children)

    @staticmethod
    def ins_fn(children):
        rest = next((c for c in children if isinstance(c, _Chain)), _Chain())
        if not isinstance(children[0], Token):
            return rest
        bag = next((c for c in children if isinstance(c, dict)), {})
        return _Chain([("mod", Shape(str(children[0]), tuple(bag.items())))] + rest)

    @staticmethod
    def row_(children):
        return Row(children[0] if children else ())

    @staticmethod
    def ctrl_value(children):
        return _leaf(children[0])

    note_value = ctrl_value

    @staticmethod
    def route_value(children):
        if len(children) == 1 and children[0].type == "INT":
            return int(children[0])
        text = "".join(str(c) for c in children)
        return text + "'" if text.startswith("'- ") else text

    @staticmethod
    def program_name(children):
        if len(children) == 2:
            return Run(str(children[0])[:-1], _leaf(children[1]))
        return _leaf(children[0])

    @staticmethod
    def run_program(children):
        return Run(str(children[0]), children[1])

    @staticmethod
    def phrase(children):
        return tuple(children)

    @staticmethod
    def event(children):
        note, rest = str(children[0]), list(children[1:])
        ins = rest.pop(0) if isinstance(rest[0], (Instrument, Token)) else None
        ins = str(ins) if isinstance(ins, Token) else ins
        steps = int(rest[3]) if len(rest) > 3 else None
        return Event(note, ins, tuple(rest[0]), rest[1], rest[2], steps)

    @staticmethod
    def cmd_filter(children):
        rest = children[-1]
        return _Chain([("filter", NONE)] + rest) if len(children) > 1 else rest

    @staticmethod
    def cmd_set(children):
        rest = children[-1] if isinstance(children[-1], _Chain) else _Chain()
        flat = [c for c in children if isinstance(c, Token)]
        return _Chain([("set", (str(k), _leaf(v))) for k, v in zip(flat[::2], flat[1::2])] + rest)

    @staticmethod
    def cmd_legato(children):
        return _Chain([("legato", True)] if children else [])

    @staticmethod
    def keep_pw(children):
        return bool(children)

    keep_filter = keep_pw

    def code(self, children):
        return Code(_code.Statements.code(self, children))

    asm = code
    code_label, code_op = _code.Statements.code_label, _code.Statements.code_op
    code_imm, code_mem = _code.Statements.code_imm, _code.Statements.code_mem


_ROW_LINKS = "wait hold ctrl gate note ad sr pw cut res route mode freq run filter vol"
for _name, _method in {
    **{f"row_{k}": _link(k) for k in _ROW_LINKS.split()},
    **{f"ins_{k}": _link(k) for k in "ad sr ctrl restart pw filter freq".split()},
    **{f"cmd_{k}": _link(k, normal=_token) for k in "run ad sr ctrl mode vol pw cut freq".split()},
    **{f"cmd_{k}": _link(k, _pair) for k in ("resfilt", "tempo", "vtempo")},
    **{f"slot_{k}": _link(k, normal=_token) for k in ("mod", "hold", "reset")},
    **{f"state_{k}": _link(k) for k in CELLS},
}.items():
    setattr(_ToModel, _name, _method)


def read(text: str) -> Document:
    """The Document of canonical document ``text``; CanonicalError outside the grammar."""
    try:
        tree = _parser().parse(text)
    except exceptions.UnexpectedInput as exc:
        raise CanonicalError(
            f"line {exc.line} column {exc.column}: {str(exc).splitlines()[0]}"
        ) from exc
    try:
        doc = _ToModel(text).transform(tree)
    except exceptions.VisitError as exc:
        raise exc.orig_exc from exc
    return replace(doc, layout=_layout(_lines(doc), text.splitlines(keepends=True)))


def _unwrapped(text: str) -> str:
    return _WRAP.sub(" ", _OPENED.sub(r"\1", text))


def _layout(lines: list, physical: list) -> tuple:
    """``(line, as read)`` of each printed line whose text as read wraps otherwise."""
    out, at = [], 0
    for line in lines:
        target, k = _unwrapped(line), 1
        while at + k <= len(physical):
            written = "".join(physical[at : at + k])
            if len(_unwrapped(written)) >= len(target):
                break
            k += 1
        if _unwrapped(written) != target:
            return tuple(out)
        if written != line:
            out.append((line, written))
        at += k
    return tuple(out)


# ---- printing -----------------------------------------------------------------------------


class _Seq(NamedTuple):
    """A flow collection: its items, each a list of parts (scalars and collections), its
    brackets, and whether a line may wrap after its opening bracket."""

    items: list
    open: str = "["
    close: str = "]"
    wraps: bool = True


class _Emitter:
    """PyYAML's flow layout: past the width, a break before an item at its collection's
    indentation, or at a scalar's space at that plus 2."""

    def __init__(self, width: int):
        self.width, self.out, self.column = width, [], 0

    def write(self, text: str):
        """``text`` on the current line."""
        self.out.append(text)
        self.column += len(text)

    def indent(self, indent: int):
        """A line break, then ``indent`` spaces."""
        self.out.append("\n" + " " * indent)
        self.column = indent

    def scalar(self, text: str, indent: int):
        """A plain scalar, wrapping at a space past the width."""
        words = text.split(" ")
        self.write(words[0])
        for word in words[1:]:
            if self.column > self.width:
                self.indent(indent)
            else:
                self.write(" ")
            self.write(word)

    def parts(self, parts, indent: int):
        """``parts`` within a collection (or a block mapping) of ``indent``."""
        for part in parts:
            if isinstance(part, str):
                self.scalar(part, indent + 2)
            else:
                self.seq(part, indent + 2)

    def seq(self, seq: _Seq, indent: int):
        """A flow collection of ``indent``, wrapping before an item past the width."""
        self.write(seq.open)
        for i, item in enumerate(seq.items):
            if i:
                self.write(",")
            if self.column > self.width and (i or seq.wraps):
                self.indent(indent)
            elif i:
                self.write(" ")
            self.parts(item, indent)
        self.write(seq.close)

    def text(self) -> str:
        """The text written."""
        return "".join(self.out).replace(_HARD, " ")


def _line(prefix: str, parts, indent: int) -> str:
    """A block line: ``prefix`` then its value's ``parts``, in a block mapping of ``indent``."""
    emitter = _Emitter(WIDTH)
    emitter.write(prefix)
    emitter.parts(parts, indent)
    return emitter.text() + "\n"


def _map(pairs, wraps: bool = True) -> _Seq:
    return _Seq([[f"{k}:{_HARD}", *v] for k, v in pairs], "{", "}", wraps)


def _hard(text: str) -> str:
    return text.replace(" ", _HARD)


def _binding(value, where: str = "flow") -> list:
    """The parts of a binding or a record's value, ``where`` ``flow``, ``block`` or ``cmd``
    (a command or a slot's default, whose expressions are always quoted)."""
    # pylint: disable=too-many-return-statements
    if isinstance(value, Expr):
        quoted = where == "cmd" or value.quoted or where == "flow" and "," in value.text
        return [f"'{value.text}'" if quoted else value.text]
    if isinstance(value, Code):
        return [_hard(_code.inline(value.statements))]
    if isinstance(value, Program):
        return [_program(value)]
    if isinstance(value, Bound):
        return [*_binding(value.expr, where), _HARD, _bag(value.bag)]
    if isinstance(value, Shape):
        return [value.name] + ([" ", _bag(value.bag)] if value.bag else [])
    if isinstance(value, Run) and isinstance(value.program, Call):
        return [f"{value.kind}:{value.program}"]
    if isinstance(value, Run):
        return [value.kind, _program(value.program)]
    if isinstance(value, Instrument):
        return [_map((k, _binding(v)) for k, v in value.fields)]
    return [_hard(str(value))]


def _bag(bag) -> _Seq:
    def item(value):
        return (
            [_Seq([[str(x)] for x in value], wraps=False)]
            if isinstance(value, tuple)
            else [str(value)]
        )

    return _map(((k, item(v)) for k, v in bag), wraps=False)


def _program(program: Program) -> _Seq:
    rows = [[_map((k, _binding(v)) for k, v in row.keys)] for row in program.rows]
    loop = [_map([("loop", [str(program.loop)])])]
    return _Seq(rows + [["end"] if program.loop is None else loop])


def _command(key: str, value) -> list:
    if key == "legato":
        return ["!legato"]
    if key == "filter":
        return ["!filter:none"]
    if key == "set":
        return [_hard(f"!set {value[0]} {value[1]}")]
    if isinstance(value, tuple) and not isinstance(value, (Call, Run)):
        return [f"!{key}:{value[0]}/{value[1]}"]
    return [f"!{key}:", *_binding(value, "cmd")]


def _event(event: Event) -> list:
    parts = [event.note]
    if event.ins is not None:
        parts += ["."] + _binding(event.ins)
    for key, value in event.commands:
        parts += _command(key, value)
    parts += ["!pw"] * event.keep_pw + ["!filter"] * event.keep_filter
    return parts + ([] if event.steps is None else [f"*{event.steps}"])


def _events(events) -> _Seq:
    return _Seq([_event(e) for e in events])


def _play(entry) -> list:
    if isinstance(entry, str):
        return [entry]
    head = entry.phrase if isinstance(entry.phrase, str) else _events(entry.phrase)
    return [head] + ([] if entry.transpose is None else [str(Signed(entry.transpose))])


def _flat(value) -> str:
    """A header line's flow value, never wrapped."""
    if isinstance(value, list):
        return "{" + ", ".join(f"{k}: {_flat(v)}" for k, v in value) + "}"
    if isinstance(value, tuple):
        return "[" + ", ".join(map(str, value)) + "]"
    return str(value)


def _slot(slot: Slot) -> list:
    out = [] if slot.mod is None else [("mod", "".join(_binding(slot.mod, "cmd")))]
    return out + [(k, tuple(getattr(slot, k))) for k in ("hold", "reset") if getattr(slot, k)]


def _header(head: Header) -> list:
    meta = _map((k, [v]) for k, v in head.meta)
    lines = [f"unitracker: {head.version}\n", _line("meta: ", [meta], 0)]
    if head.clock is not None:
        lines.append(f"clock: {{cycles_per_tick: {head.clock[0]}, clock_hz: {head.clock[1]}}}\n")
    if head.voices is not None:
        lines.append(f"voices: {head.voices}\n")
    if head.tempo is not None:
        lines.append(f"tempo: {_flat(head.tempo)}\n")
    if head.hold is not None:
        lines.append(f"hold: {_flat(list(head.hold))}\n")
    if head.slots is not None:
        cells = [(c, [(s.name, _slot(s)) for s in slots]) for c, slots in head.slots]
        lines.append(f"slots: {_flat(cells)}\n".replace(_HARD, " "))
    if head.order is not None:
        lines.append(f"order: {_flat(tuple(head.order))}\n")
    if head.state is not None:
        lines.append(f"state: {_flat([(c, list(names)) for c, names in head.state])}\n")
    return lines


def _template(key: str, body, indent: int) -> list:
    pad = " " * indent
    if isinstance(body, Code):
        lines = _code.printed(body.statements).splitlines(keepends=True)
        return [f"{pad}{key}: |\n"] + [f"{pad}  {s}" for s in lines]
    return [_line(f"{pad}{key}: ", _binding(body, "block"), indent)]


def _record(kind: str, name: str, value, indent: int = 8) -> list:
    if kind == "mod":
        return _template(name, value, indent)
    parts = [_events(value)] if kind == "phrase" else _binding(value, "block")
    return [_line(f"{' ' * indent}{name}: ", parts, indent)]


def printed(doc: Document) -> str:
    """The canonical text of ``doc``: its lines as read where its layout holds them."""
    layout = {}
    for line, written in doc.layout:
        layout.setdefault(line, []).append(written)
    seen = {}
    out = []
    for line in _lines(doc):
        forms = layout.get(line)
        if forms:
            k = seen[line] = seen.get(line, -1) + 1
            line = forms[min(k, len(forms) - 1)]
        out.append(line)
    return "".join(out)


def _lines(doc: Document) -> list:
    """The canonical lines of ``doc``, each a block line with its wraps."""
    lines = _header(doc.header)
    if doc.tables:
        lines.append("tables:\n")
        lines += [_line(f"  {k}: ", [_Seq([[str(x)] for x in v])], 2) for k, v in doc.tables]
    if doc.mods:
        lines.append("mod:\n")
        for key, body in doc.mods:
            lines += _template(key, body, 2)
    for section in doc.defs:
        lines.append(f"{section.kind}:\n")
        for name, value in section.records:
            lines += _record(section.kind, name, value, 2)
    if doc.init is not None:
        lines.append(_line("init: ", [_events(doc.init)], 0))
    lines.append("song:\n")
    for row in doc.rows:
        plays = [_Seq([_play(p) for p in row.play])]
        if not row.defs:
            lines.append(_line("  - play: ", plays, 4))
            continue
        lines.append("  - def:\n")
        for section in row.defs:
            lines.append(f"      {section.kind}:\n")
            for name, value in section.records:
                lines += _record(section.kind, name, value)
        lines.append(_line("    play: ", plays, 4))
    lines.append("  - end\n" if doc.loop is None else f"  - {{loop: {doc.loop}}}\n")
    return lines
