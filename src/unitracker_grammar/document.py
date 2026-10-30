"""The canonical document as a typed model (:mod:`unitracker_grammar.model`): :func:`read`
builds it from a text, its classes build one directly, and :func:`printed` writes its one
canonical text (the README's "Documents" section); a sharp's letter in lower case and a phrase
note's octave left out where it is the previous note's."""

import re
from dataclasses import replace

from lark import Token, Transformer, exceptions, v_args

from unitracker_grammar import code as _code
from unitracker_grammar.canonical import CanonicalError, absolute, parse
from unitracker_grammar.cells import CELLS, LATER_CELLS
from unitracker_grammar.code import Call
from unitracker_grammar.model import (  # pylint: disable=unused-import
    _CMD_KEYS,
    _INS_KEYS,
    _INT,
    _ROW_KEYS,
    CONT,
    END,
    HOLD,
    KINDS,
    LAYERED_KINDS,
    NONE,
    RESET,
    VERSION,
    VERSION_2_4,
    VERSION_2_5,
    Code,
    Def,
    Document,
    Event,
    Expr,
    Group,
    Header,
    Instrument,
    Once,
    PARAM,
    Part,
    Play,
    Program,
    Row,
    Run,
    Section,
    Signed,
    Slot,
    SongRow,
    Voice,
    _CELL,
    base,
    signature,
)

__all__ = [
    "CELLS",
    "CONT",
    "END",
    "HOLD",
    "KINDS",
    "LAYERED_KINDS",
    "NONE",
    "RESET",
    "VERSION",
    "VERSION_2_4",
    "VERSION_2_5",
    "Call",
    "Code",
    "Def",
    "Document",
    "Event",
    "Expr",
    "Group",
    "Header",
    "Instrument",
    "Once",
    "Part",
    "Play",
    "Program",
    "Row",
    "Run",
    "Section",
    "Signed",
    "Slot",
    "SongRow",
    "Voice",
    "base",
    "first_use",
    "printed",
    "read",
    "replace",
    "signature",
    "top_level",
]


# ---- reading ------------------------------------------------------------------------------


class _Chain(list):
    """A key chain's ``(key, value)`` pairs from a link on."""


def _leaf(token: Token):
    if token.type == "INT":
        return int(token)
    if token.type == "SIGNED":
        return Signed(token)
    if token.type in ("CALL", "PHRASE_CALL"):
        return Call(token.partition("(")[0], _arguments(token))
    if token.type == "TIMES":
        return int(token[1:])
    return str(token)


def _argument(text: str):
    """A call's argument: an int, a Signed where written with its sign, or a name (a parameter
    or a chord)."""
    if text[0].isalpha():
        return text
    return Signed(text) if text[0] in "+-" else int(text)


_WRITTEN_NOTE = re.compile(r"[A-Gacdfg]-?\d+")


def _arguments(text: str) -> tuple:
    """The arguments of a call's ``(...)``: a phrase template's notes absolute (``C#4``)."""
    args = [a for a in text[text.index("(") + 1 : -1].split(",") if a]
    if args and _WRITTEN_NOTE.fullmatch(args[0]):
        return tuple(absolute(a) for a in args)
    return tuple(_argument(a) for a in args)


def _value(value):
    """A binding where an integer and its expression are one text: the int."""
    if isinstance(value, Token):
        return _leaf(value)
    if isinstance(value, Expr) and _INT.fullmatch(value.text):
        return int(value.text)
    return value


def _param(value):
    """A cell's value where a template's parameter stands: its name."""
    value = _value(value)
    return value.text if isinstance(value, Expr) and PARAM.fullmatch(value.text) else value


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
    """A command's value: a token's, an expression kept as written."""
    return _leaf(value) if isinstance(value, Token) else value


def _definitions(kind: str):
    """A definition section's rule: its records, each a key token and its value."""

    def method(_self, children):
        values = (_leaf(v) if isinstance(v, Token) else v for v in children[1::2])
        return Section(kind, tuple(zip(map(str, children[::2]), values)))

    return method


class _ToModel(Transformer):
    """The parse tree of ``canonical.lark`` to a Document; each method the rule of its name."""

    # pylint: disable=missing-function-docstring,too-many-public-methods

    def __init__(self, text: str):
        super().__init__()
        self.source = text

    @v_args(meta=True)
    def expr(self, meta, _children):
        return Expr(self.source[meta.start_pos : meta.end_pos])

    @staticmethod
    def start(children):
        head, body = {}, {"rows": [], "defs": []}
        for c in children[1:]:
            if isinstance(c, (SongRow, Part, Group, Voice)):
                body["rows"].append(c)
            elif isinstance(c, Section):
                body["defs"].append(c)
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
        return ("clock", tuple(int(c) if c.type == "INT" else str(c) for c in children))

    @staticmethod
    def voices(children):
        return ("voices", int(children[0]))

    @staticmethod
    def tempo(children):
        return ("tempo", _pair([int(c) for c in children]))

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
    def layers(children):
        return ("layers", tuple(children[0]))

    @staticmethod
    def layer_names(children):
        return tuple(map(str, children))

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
    def regs(children):
        return ("regs", children[0])

    @staticmethod
    def lag(children):
        return ("lag", int(children[0]))

    @staticmethod
    def holds(children):
        return ("holds", tuple(children))

    @staticmethod
    def hold_key(children):
        return (str(children[0]), children[1])

    @staticmethod
    def calls(children):
        return ("calls", (int(children[0]), children[1] if len(children) > 1 else None))

    @staticmethod
    def bits(children):
        return tuple(int(c) for c in children)

    @staticmethod
    def global_cells(children):
        return ("global_cells", tuple(str(c) for c in children))

    @staticmethod
    def tables(children):
        return ("tables", tuple(zip(map(str, children[::2]), children[1::2])))

    @staticmethod
    def intlist(children):
        return tuple(int(c) for c in children)

    @staticmethod
    def def_mod(children):
        return ("mods", tuple(zip(map(str, children[::2]), children[1::2])))

    @staticmethod
    def init(children):
        return ("init", tuple(children))

    @staticmethod
    def item(children):
        return children[0]

    @staticmethod
    def row(children):
        return SongRow(children[0])

    @staticmethod
    def part(children):
        times = _leaf(children[1]) if len(children) > 1 else None
        return Part(str(children[0]) if isinstance(children[0], Token) else children[0], times)

    @staticmethod
    def section(children):
        return tuple(children)

    items = body = voice_items = section

    @staticmethod
    def voice(children):
        last = children[-1]
        loop = int(last) if last.type == "INT" else None
        return Voice(tuple(c for c in children if not isinstance(c, Token)), loop)

    @staticmethod
    def group(children):
        if isinstance(children[-1], Token):
            return Group(children[0], _leaf(children[-1]))
        return Group(children[0], None, tuple(children[1:]))

    song_group = voice_group = group

    @staticmethod
    def once(children):
        return Once(_value(children[0]))

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
        phrase = _leaf(first) if isinstance(first, Token) else first
        return Play(phrase, Signed(children[1]) if len(children) > 1 else None)

    voice_play = play

    @staticmethod
    def use(children):
        args = _arguments(children[2]) if len(children) > 2 else None
        body = children[1] if args is not None else _value(children[1])
        return Def(str(children[0])[:-1], body, args)

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
    def fexpr(children):
        return children[0]

    @staticmethod
    def row_(children):
        return Row(children[0] if children else ())

    @staticmethod
    def note_value(children):
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
        ins = rest.pop(0) if isinstance(rest[0], (Instrument, Token, Def)) else None
        ins = _leaf(ins) if isinstance(ins, Token) else ins
        steps = int(rest[3]) if len(rest) > 3 else None
        return Event(note, ins, tuple(rest[0]), rest[1], rest[2], steps)

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


for _name, _method in {
    **{f"row_{k}": _link(k, normal=_param if k in LATER_CELLS else _value) for k in _ROW_KEYS},
    **{f"ins_{k}": _link(k, normal=_param if k in ("ad", "sr") else _value) for k in _INS_KEYS},
    **{
        f"cmd_{k}": _link(k, normal=_token)
        for k in "run ad sr ctrl res route mode vol pw cut freq".split()
    },
    **{f"cmd_{k}": _link(k, _pair) for k in ("tempo", "vtempo")},
    **{f"slot_{k}": _link(k, normal=_token) for k in ("mod", "hold", "reset")},
    **{f"state_{k}": _link(k) for k in CELLS},
    **{f"layers_{k}": _link(k) for k in LAYERED_KINDS},
    **{f"def_{k}": _definitions(k) for k in KINDS},
    **{f"use_{k}": _ToModel.__dict__["use"] for k in KINDS + ("template",)},
}.items():
    setattr(_ToModel, _name, _method)


def read(text: str) -> Document:
    """The Document of canonical document ``text``; CanonicalError outside the grammar, the
    errors of :func:`unitracker_grammar.canonical.parse` where its checks refuse it."""
    tree = parse(text)
    try:
        return _ToModel(text).transform(tree)
    except exceptions.VisitError as exc:
        raise exc.orig_exc from exc


# ---- printing -----------------------------------------------------------------------------


def _map(pairs) -> str:
    return "{" + ",".join(f"{k}:{v}" for k, v in pairs) + "}"


def _seq(items) -> str:
    return "[" + ",".join(items) + "]"


def _binding(value, where: str = "flow") -> str:
    """The text of a binding or a record's value, ``where`` ``flow``, ``block`` or ``cmd`` (a
    command or a slot's default, whose expressions are always quoted)."""
    # pylint: disable=too-many-return-statements
    if isinstance(value, Def):
        return _defined(value, where)
    if isinstance(value, Once):
        return _binding(value.value, "cmd") + "!"
    if isinstance(value, Expr):
        quoted = where == "cmd" or where == "flow" and "," in value.text
        return f"'{value.text}'" if quoted else value.text
    if isinstance(value, Code):
        return _code.inline(value.statements)
    if isinstance(value, Program):
        return _program(value)
    if isinstance(value, Run):
        return value.kind + _program(value.program)
    if isinstance(value, Instrument):
        return _map((k, _binding(v)) for k, v in value.fields)
    return str(value)


def _defined(value: Def, where: str) -> str:
    """The text of a definition at its first use."""
    if value.args is None and _kind(value.name) in ("phrase", "section"):
        return f"{value.name}={_body(value.value, _kind(value.name))}"
    if value.args is None:
        return f"{value.name}={_binding(value.value, where)}"
    if type(value.value) is tuple:  # pylint: disable=unidiomatic-typecheck
        return f"{value.name}={_events(value.value)}{_args(value.args)}"
    body = _binding(value.value, "cmd" if isinstance(value.value, Expr) else where)
    return f"{value.name}={body}{_args(value.args)}"


def _args(args: tuple) -> str:
    """A call's arguments: integers and names as written, notes with their octaves."""
    return "(" + ",".join(_note(a)[0] if isinstance(a, str) else str(a) for a in args) + ")"


def _body(value: tuple, kind: str) -> str:
    """A phrase's events, its template's call or that template at its first use, or a section's
    items."""
    if isinstance(value, Def):
        return _defined(value, "flow")
    if isinstance(value, Call):
        return value.name + _args(value.args)
    return _seq(_item(i) for i in value) if kind == "section" else _events(value)


def _row_value(key: str, value) -> str:
    """A row key's value: an absolute note as written (a sharp's letter in lower case)."""
    if key == "note" and isinstance(value, str) and _ABSOLUTE.fullmatch(value):
        return _note(value)[0]
    return _binding(value)


def _program(program: Program) -> str:
    rows = [_map((k, _row_value(k, v)) for k, v in row.keys) for row in program.rows]
    return _seq(rows + ["end" if program.loop is None else f"{{loop:{program.loop}}}"])


def _command(key: str, value) -> str:
    if key == "legato":
        return " legato"
    if isinstance(value, tuple) and not isinstance(value, (Call, Run, Def, Once)):
        return f" {key}:{value[0]}/{value[1]}"
    return f" {key}:{_binding(value, 'cmd')}"


def _event(event: Event, note: str) -> str:
    out = note
    if event.ins is not None:
        out += "." + _binding(event.ins)
    out += "".join(_command(k, v) for k, v in event.commands)
    out += " pw" * event.keep_pw + " filter" * event.keep_filter
    return out + ("" if event.steps is None else f"*{event.steps}")


_ABSOLUTE = re.compile(r"([A-G])(#?)(-?\d+)")


def _note(note: str, octave=None) -> tuple[str, str | None]:
    """A note atom as written, a sharp's letter in lower case and its octave left out where it
    is ``octave``, and the octave it leaves for the next note (``octave`` after a rest)."""
    found = _ABSOLUTE.fullmatch(note)
    if found is None:
        return note, None if note not in ("-", "off", "on") else octave
    letter, sharp, number = found.groups()
    return (letter.lower() if sharp else letter) + ("" if number == octave else number), number


def _events(events, phrase: bool = True) -> str:
    """A phrase's events, its groups' among them (``init``'s where not ``phrase``: each note
    with its octave)."""
    octave = [None]

    def text(items) -> str:
        out = []
        for event in items:
            if isinstance(event, Group):
                out.append(_group(event, text))
                continue
            note, octave[0] = _note(event.note, octave[0] if phrase else None)
            out.append(_event(event, note))
        return ",".join(out)

    return "[" + text(events) + "]"


def _group(group: Group, text) -> str:
    """A group: its body and endings each by ``text``, then its count."""
    parts = [text(group.body)] + [text(e) for e in group.endings]
    return "[" + "|".join(parts) + "]" + ("" if group.times is None else f"x{group.times}")


def _item(item) -> str:
    """A song item."""
    if isinstance(item, SongRow):
        return f"play:{_seq(_play(p) for p in item.play)}"
    if isinstance(item, Part):
        times = "" if item.times is None else f"x{item.times}"
        return _binding(item.section) + times
    if isinstance(item, Voice):
        end = "end" if item.loop is None else f"loop:{item.loop}"
        return f"voice:[{','.join(_item(i) for i in item.play)}|{end}]"
    if isinstance(item, Play):
        return _play(item)
    return _group(item, lambda items: ",".join(_item(i) for i in items))


def _play(entry) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry.phrase, Call):
        head = entry.phrase.name + _args(entry.phrase.args)
    elif isinstance(entry.phrase, (str, Def)):
        head = _binding(entry.phrase)
    else:
        head = _events(entry.phrase)
    return head + ("" if entry.transpose is None else str(Signed(entry.transpose)))


def _flat(value) -> str:
    """A header line's flow value."""
    if isinstance(value, list):
        return "{" + ",".join(f"{k}:{_flat(v)}" for k, v in value) + "}"
    if isinstance(value, tuple):
        return "[" + ",".join(map(str, value)) + "]"
    return str(value)


def _slot(slot: Slot) -> list:
    out = [] if slot.mod is None else [("mod", _binding(slot.mod, "cmd"))]
    return out + [(k, tuple(getattr(slot, k))) for k in ("hold", "reset") if getattr(slot, k)]


def _header(head: Header) -> list:
    lines = [f"meta:{_map(head.meta)}\n"]
    if head.clock is not None:
        lines.append(f"clock:{{cycles_per_tick:{head.clock[0]},clock_hz:{head.clock[1]}}}\n")
    if head.voices is not None:
        lines.append(f"voices:{head.voices}\n")
    if head.tempo is not None:
        lines.append(f"tempo:{_flat(head.tempo)}\n")
    if head.slots is not None:
        cells = [(c, [(s.name, _slot(s)) for s in slots]) for c, slots in head.slots]
        lines.append(f"slots:{_flat(cells)}\n")
    if head.layers is not None:
        lines.append(f"layers:{_flat(list(head.layers))}\n")
    if head.holds is not None:
        lines.append(f"holds:{_flat([(k, tuple(e)) for k, e in head.holds])}\n")
    if head.order is not None:
        lines.append(f"order:{_flat(tuple(head.order))}\n")
    if head.state is not None:
        lines.append(f"state:{_flat([(c, list(names)) for c, names in head.state])}\n")
    if head.regs is not None:
        lines.append(f"regs:{_flat(head.regs)}\n")
    if head.lag is not None:
        lines.append(f"lag:{head.lag}\n")
    if head.calls is not None:
        frame, full = head.calls
        pattern = "" if full is None else f",full:{_flat(full)}"
        lines.append(f"calls:{{frame:{frame}{pattern}}}\n")
    if head.global_cells is not None:
        lines.append(f"global:{_flat(head.global_cells)}\n")
    return lines


def _template(key: str, body) -> list:
    if isinstance(body, Code):
        return [f" {key}:|\n"] + [f"\t{_code.line(s)}\n" for s in body.statements]
    return [f" {key}:{_binding(body, 'block')}\n"]


def _section(section: Section) -> list:
    lines = [f"{section.kind}:\n"]
    for name, value in section.records:
        text = _body(value, section.kind) if section.kind in ("phrase", "section") else None
        text = _binding(value, "block") if text is None else text
        lines.append(f" {name}:{text}\n")
    return lines


def printed(doc: Document) -> str:
    """The one canonical text of ``doc``; CanonicalError where the grammar refuses its shape
    (no meta, no row, an empty play or section, a section twice or out of KINDS order)."""
    kinds = [s.kind for s in doc.defs]
    rows = [r for r in doc.rows if isinstance(r, SongRow)]
    if not doc.header.meta or not doc.rows or not all(r.play for r in rows):
        raise CanonicalError("a document has a meta and song items, each row with a play entry")
    if kinds != sorted(set(kinds), key=KINDS.index) or not all(s.records for s in doc.defs):
        raise CanonicalError(f"sections {kinds}: each once, with records, in the order {KINDS}")
    voices = [r for r in doc.rows if isinstance(r, Voice)]
    if voices and (
        len(voices) < len(doc.rows) or doc.loop is not None or not all(r.play for r in voices)
    ):
        raise CanonicalError("a song of orderlists is one Voice per voice, each with an entry")
    return "".join(_lines(doc))


def _lines(doc: Document) -> list:
    """The canonical lines of ``doc``."""
    lines = [f"unitracker:{doc.version}\n"] + _header(doc.header)
    if doc.tables:
        lines.append("tables:\n")
        lines += [f" {k}:{_flat(tuple(v))}\n" for k, v in doc.tables]
    if doc.mods:
        lines.append("mod:\n")
        for key, body in doc.mods:
            lines += _template(key, body)
    for section in doc.defs:
        lines += _section(section)
    if doc.init is not None:
        lines.append(f"init:{_events(doc.init, phrase=False)}\n")
    lines.append("song:\n")
    lines += [f" - {_item(item)}\n" for item in doc.rows]
    if not doc.voiced:
        lines.append(" - end\n" if doc.loop is None else f" - {{loop:{doc.loop}}}\n")
    return lines


# ---- definitions at their first use -----------------------------------------------------

_NAMED = re.compile(r"(?:pw|[icfrps])\d+")
_PREFIX = {"i": "ins", "c": "ctrl", "pw": "pw", "f": "filter", "r": "restart", "p": "phrase"}
_PREFIX["s"] = "section"
_REFERENCES = frozenset({"ins", "ctrl", "pw", "filter", "restart", "run", "phrase", "section"})


def _kind(name: str) -> str:
    """The section of a named definition, by its name's prefix."""
    return _PREFIX[name.rstrip("0123456789")]


_SAME = object()
_KEYED = object()
# per model class, each field the walk enters and the site below it
_FIELDS = {
    Row: {"keys": _KEYED},
    Instrument: {"fields": _KEYED},
    Event: {"ins": "ins", "commands": _KEYED},
    Program: {"rows": _SAME},
    Play: {"phrase": "phrase"},
    Part: {"section": "section"},
    SongRow: {"play": None},
    Voice: {"play": None},
    Group: {"body": _SAME, "endings": _SAME},
    Slot: {"mod": "mod"},
}


def _walk(value, visit, site=None):
    """``value`` with each reference (a definition's name where one stands, a Call) and each
    Def replaced by ``visit(value, site)``, in reading order, ``site`` the key or kind it
    stands under (``ins``, ``phrase``, a row key, an instrument field, a section's kind)."""
    if isinstance(value, (Call, Def)) or isinstance(value, str) and site in _REFERENCES:
        return (
            value if isinstance(value, str) and not _NAMED.fullmatch(value) else visit(value, site)
        )
    if isinstance(value, Run):
        return Run(value.kind, _walk(value.program, visit, value.kind))
    if isinstance(value, Once):
        return Once(_walk(value.value, visit, site))
    if type(value) in _FIELDS:
        changes = {}
        for name, under in _FIELDS[type(value)].items():
            old = getattr(value, name)
            if under is _KEYED:
                changes[name] = tuple((k, _walk(v, visit, base(k))) for k, v in old)
            else:
                changes[name] = _walk(old, visit, site if under is _SAME else under)
        return replace(value, **changes)
    if isinstance(value, tuple):
        return tuple(_walk(v, visit, site) for v in value)
    return value


def _order(doc: Document, visit) -> Document:
    """``doc`` walked in reading order: its slots' defaults, templates, sections, init and rows."""
    head = doc.header
    slots = head.slots and tuple((c, _walk(s, visit, "mod")) for c, s in head.slots)
    header = replace(head, slots=slots)
    mods = tuple((k, _walk(v, visit, "mod")) for k, v in doc.mods)
    defs = tuple(
        replace(s, records=tuple((n, _walk(v, visit, s.kind)) for n, v in s.records))
        for s in doc.defs
    )
    init = doc.init and _walk(doc.init, visit)
    rows = _walk(doc.rows, visit)
    return replace(doc, header=header, mods=mods, defs=defs, init=init, rows=rows)


def top_level(doc: Document) -> Document:
    """``doc`` with each definition at its first use moved to its section (a template's to the
    templates, a program template's to its kind's), each in reading order after the
    section's records, and the use its reference."""
    mods, records = [], {}

    def visit(value, site):
        if not isinstance(value, Def):
            return value
        body = _walk(value.value, visit, site)
        if value.args is None:
            records.setdefault(_kind(value.name), []).append((value.name, body))
            return value.name
        if isinstance(body, (Code, Expr)):
            mods.append((value.name, body))
        else:
            kind, body = (body.kind, body.program) if isinstance(body, Run) else (site, body)
            records.setdefault(kind, []).append((value.name, body))
        return Call(_code.signature(value.name)[0], value.args)

    doc = _order(doc, visit)
    for section in doc.defs:
        records[section.kind] = list(section.records) + records.get(section.kind, [])
    defs = tuple(Section(k, records[k]) for k in KINDS if records.get(k))
    return replace(doc, mods=doc.mods + tuple(mods), defs=defs)


def _cell(kind: str, body):
    """A program template's body as a program: a pulse or filter binding the one-row program
    binding the cell."""
    return body if isinstance(body, Program) else Program([{_CELL[kind]: body}])


def first_use(doc: Document) -> Document:
    """``doc`` with each definition its song reaches (from the slots, the init row and the
    rows) moved to its first reference in reading order; the rest, and what only they reach,
    stay in their sections. The inverse of :func:`top_level` up to records' order."""
    doc = top_level(doc)
    found = {}
    for kind, key, value in [("mod", k, v) for k, v in doc.mods] + [
        (s.kind, k, v) for s in doc.defs for k, v in s.records
    ]:
        if _named(key) in found:
            raise CanonicalError(f"{_named(key)} is defined twice")
        found[_named(key)] = (kind, key, value)
    reached, todo = set(), [doc.header.slots, doc.init, doc.rows]

    def reach(value, _site):
        name = value.name if isinstance(value, Call) else value
        if name in found and name not in reached:
            reached.add(name)
            todo.append(found[name][2])
        return value

    while todo:
        _walk(todo.pop(), reach, "run")
    placed = set()

    def visit(value, site):
        name = value.name if isinstance(value, Call) else value
        if name not in reached or name in placed:
            return value
        placed.add(name)
        kind, key, body = found[name]
        body = _walk(body, visit, kind)
        if not isinstance(value, Call):
            return Def(key, body)
        if kind in _CELL:
            body = Run(kind, _cell(kind, body)) if site == "run" else _cell(kind, body)
        elif kind in ("restart", "ctrl") and site == "run":
            body = Run(kind, body)
        return Def(key, body, value.args)

    kept = tuple((k, v) for k, v in doc.mods if _code.signature(k)[0] not in reached)
    defs = tuple(
        replace(s, records=tuple((k, v) for k, v in s.records if _named(k) not in reached))
        for s in doc.defs
    )
    return _order(replace(doc, mods=kept, defs=tuple(s for s in defs if s.records)), visit)


def _named(key: str) -> str:
    return _code.signature(key)[0] if "(" in key else key
