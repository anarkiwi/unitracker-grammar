"""Code templates: NMOS 6502 routines a ``mod:`` record may be, read and checked.

A routine is a tuple of statements, each a :class:`Label` or an :class:`Op`, whose operand is
``None`` (implied), an :class:`Imm`, a :class:`Mem` or, for a branch or ``jmp``, a label's name;
:func:`printed` is its one text. A template's key may be its signature, ``name(a,b)``, which a
:class:`Call`, ``name(1,-2)``, binds. A program record (``restart``, ``ctrl``, ``pw``, ``filter``)
may be a template too, keyed by a signature, whose rows read its parameters where they take an
integer (:func:`programs`).
"""

import ast
import functools
import re
from typing import NamedTuple

from jennings.opcodes import ILLEGAL_OPCODES, OPCODES
from lark import Lark, Token, Transformer, Tree, exceptions

from unitracker_grammar import expr
from unitracker_grammar.canonical import GRAMMAR, CanonicalError
from unitracker_grammar.cells import CELLS, LATER_CELLS, LATER_PHASES
from unitracker_grammar.chords import CHORDS
from unitracker_grammar.prelude import NAMES as PRELUDE
from unitracker_grammar.prelude import PROGRAMS

SYMBOLS = ("v", "phi", "nn", "ne")
REGISTERS = ("a", "x", "y")
RESERVED = frozenset(SYMBOLS + REGISTERS)
NOTES = ("F.lo", "F.hi")
EXCLUDED = frozenset({"brk", "jsr", "rti"})
BRANCHES = frozenset({"bcc", "bcs", "beq", "bmi", "bne", "bpl", "bvc", "bvs"})
IMPLIED, IMMEDIATE, MEMORY, LABEL = "implied", "immediate", "memory", "label"
_MODES = {
    "impl": IMPLIED,
    "acc": IMPLIED,
    "imm": IMMEDIATE,
    "zp": MEMORY,
    "abs": MEMORY,
    "zpx": MEMORY + ",x",
    "absx": MEMORY + ",x",
    "zpy": MEMORY + ",y",
    "absy": MEMORY + ",y",
    "rel": LABEL,
}
LEGAL = frozenset(
    (name.lower(), LABEL if name == "JMP" else _MODES[how])
    for opcode, (name, how) in OPCODES.items()
    if opcode not in ILLEGAL_OPCODES and how in _MODES and name.lower() not in EXCLUDED
)
MNEMONICS = frozenset(m for m, _ in LEGAL)
_INDENT = "\t"


class CodeError(ValueError):
    """A text or structure that is no code template."""


class Call(NamedTuple):
    """A binding of a template: its name and its arguments, in its signature's order, each an
    integer or, in a program template's rows, one of its parameters' names."""

    name: str
    args: tuple[int, ...] = ()

    def __str__(self):
        return f"{self.name}({','.join(map(str, self.args))})"


_CALL = re.compile(r"([a-z][a-z0-9_]*)\((.*)\)")


def call(text: str) -> Call:
    """The :class:`Call` of a ``CALL`` text, ``name(1,-2,3)`` or ``name()``."""
    name, args = _CALL.fullmatch(text).groups()
    return Call(name, tuple(a if a[0].isalpha() else int(a) for a in args.split(",") if args))


def signature(text: str) -> tuple[str, tuple[str, ...]]:
    """``(name, parameters)`` of a ``SIGNATURE`` text, ``name(a,b)`` or ``name()``;
    CodeError when a parameter is declared twice."""
    name, names = _CALL.fullmatch(text).groups()
    declared = tuple(names.split(",")) if names else ()
    if len(set(declared)) != len(declared):
        raise CodeError(f"{text}: a parameter declared twice")
    return name, declared


def declare(text: str, used, names=()) -> tuple[str, tuple[str, ...]]:
    """The :func:`signature` of ``text`` if its parameters are the names a template's body reads
    as parameters, ``used``, and none is one of ``names`` (the state variables)."""
    name, declared = signature(text)
    if set(declared) != set(used):
        missing, extra = sorted(set(used) - set(declared)), sorted(set(declared) - set(used))
        raise CodeError(f"{text}: undeclared {missing}, unread {extra}")
    if clash := sorted(set(declared) & set(names)):
        raise CodeError(f"{text}: parameters {clash} are state variables")
    return name, declared


class Label(NamedTuple):
    """A label definition, ``name:``."""

    name: str


class Imm(NamedTuple):
    """An immediate: an integer 0-255, or a parameter (its low byte bare or after ``byte``
    ``<``, its high byte after ``byte`` ``>``)."""

    value: int | str
    byte: str = ""


class Mem(NamedTuple):
    """A memory operand: ``symbol`` (a symbol, ``T.lo`` or ``T.hi``), its ``offset`` (written
    with its sign when not 0, negative only on a table's bytes) and its ``index`` (written ``,x``
    or ``,y`` when set)."""

    symbol: str
    offset: int = 0
    index: str = ""


class Op(NamedTuple):
    """An instruction: its lowercase mnemonic, its mode (that of :func:`mode`) and operand."""

    mnemonic: str
    mode: str
    operand: None | Imm | Mem | str = None


def mode(operand) -> str:
    """The mode of an op with ``operand``: ``implied``, ``immediate``, ``memory``,
    ``memory,x``, ``memory,y`` or ``label``."""
    if operand is None:
        return IMPLIED
    if isinstance(operand, Imm):
        return IMMEDIATE
    if isinstance(operand, Mem):
        return MEMORY + (f",{operand.index}" if operand.index else "")
    return LABEL


def op(mnemonic: str, operand=None) -> Op:
    """The op of ``mnemonic`` with ``operand``; a branch's or ``jmp``'s plain symbol is a label."""
    if (
        mnemonic in BRANCHES | {"jmp"}
        and isinstance(operand, Mem)
        and operand[1:] == (0, "")
        and "." not in operand.symbol
    ):
        operand = operand.symbol
    return Op(mnemonic, mode(operand), operand)


class Statements(Transformer):
    """The routines of a canonical parse tree (rules ``code`` and ``asm`` and their ``code_*``
    rules) as tuples of statements, unchecked."""

    # pylint: disable=missing-function-docstring

    def code(self, children):
        return tuple(children)

    asm = code

    def code_label(self, children):
        return Label(str(children[0]))

    def code_op(self, children):
        return op(str(children[0]), *children[1:])

    def code_imm(self, children):
        *byte, value = children
        return Imm(int(value) if value.type == "INT" else str(value), str(byte[0]) if byte else "")

    def code_mem(self, children):
        parts = {t.type: str(t) for t in children[1:]}
        return Mem(str(children[0]), int(parts.get("OFFSET", 0)), parts.get("INDEX", ",")[1:])


def _refusal(statement: Op, labels: set) -> str | None:
    """Why op ``statement`` is refused, if it is."""
    # pylint: disable=too-many-return-statements
    name, how, operand = statement
    if name not in MNEMONICS:
        return f"unknown mnemonic {name!r}"
    if how != mode(operand):
        return f"{line(statement)!r} is not in mode {how!r}"
    if (name, how) not in LEGAL:
        return f"{name} has no {how} mode"
    if isinstance(operand, str) and operand not in labels:
        return f"undefined label {operand!r}"
    if isinstance(operand, Mem) and operand.symbol in REGISTERS:
        return f"{operand.symbol!r} is a register, not a memory symbol"
    if isinstance(operand, Mem) and operand.symbol in labels:
        return f"{operand.symbol!r} is a label, not a memory symbol"
    if isinstance(operand, Mem) and operand.offset < 0 and "." not in operand.symbol:
        return f"{line(statement)!r}: a negative offset is on a table's bytes only"
    if isinstance(operand, Imm) and isinstance(operand.value, int) and not 0 <= operand.value < 256:
        return f"immediate {operand.value} is not a byte"
    return None


def check(statements: tuple, names=()) -> tuple:
    """``statements`` if they are a code template, else CodeError: legal NMOS 6502 ops but
    ``brk``, ``jsr`` and ``rti``, branches and ``jmp`` to its labels, byte immediates, an
    ``rts``, and unique labels that are no reserved symbol nor one of ``names``."""
    labels = set()
    for label in (s.name for s in statements if isinstance(s, Label)):
        if label in labels:
            raise CodeError(f"duplicate label {label!r}")
        if label in RESERVED or label in names:
            raise CodeError(f"label {label!r} is a symbol")
        labels.add(label)
    for statement in statements:
        if isinstance(statement, Op) and (why := _refusal(statement, labels)):
            raise CodeError(why)
    if Op("rts", IMPLIED) not in statements:
        raise CodeError("no rts")
    return statements


@functools.lru_cache(maxsize=1)
def parser() -> Lark:
    """The LALR parser of the canonical grammar's ``code`` rule (a block's lines indented)."""
    return Lark(
        GRAMMAR.read_text(encoding="utf-8"), parser="lalr", lexer="contextual", start="code"
    )


def read(text: str, names=()) -> tuple:
    """The checked statements of a block's text, one canonical statement per line, each line
    ending in its newline (``names`` as in :func:`check`)."""
    if not text.endswith("\n"):
        raise CodeError("a code template's lines each end in a newline")
    try:
        tree = parser().parse("".join(f"{_INDENT}{s}\n" for s in text[:-1].split("\n")))
    except exceptions.UnexpectedInput as exc:
        raise CodeError(f"line {exc.line}: {str(exc).splitlines()[0]}") from exc
    return check(Statements().transform(tree), names)


def line(statement) -> str:
    """The one text of a statement."""
    if isinstance(statement, Label):
        return f"{statement.name}:"
    name, _, operand = statement
    if operand is None:
        return name
    if isinstance(operand, Imm):
        return f"{name} #{operand.byte}{operand.value}"
    if isinstance(operand, Mem):
        offset = f"{operand.offset:+d}" if operand.offset else ""
        return f"{name} {operand.symbol}{offset}{',' + operand.index if operand.index else ''}"
    return f"{name} {operand}"


def printed(statements) -> str:
    """The one text of a routine: its statements' lines, each ending in its newline."""
    return "".join(f"{line(s)}\n" for s in statements)


def inline(statements) -> str:
    """The one text of an anonymous routine: ``asm{`` its statements' lines separated by ``; ``
    then ``}``."""
    return "asm{" + "; ".join(line(s) for s in statements) + "}"


def canonical(text: str) -> str:
    """The one text of a routine's text (see :func:`read`)."""
    return printed(read(text))


def params(statements) -> tuple[str, ...]:
    """The parameters a routine reads, its immediates' names, in first-use order."""
    return tuple(
        dict.fromkeys(
            s.operand.value
            for s in statements
            if isinstance(s, Op) and isinstance(s.operand, Imm) and isinstance(s.operand.value, str)
        )
    )


def symbols(statements) -> tuple[str, ...]:
    """The memory symbols a routine names, in first-use order."""
    return tuple(
        dict.fromkeys(
            s.operand.symbol for s in statements if isinstance(s, Op) and isinstance(s.operand, Mem)
        )
    )


STATE_RULES = frozenset(f"state_{cell}" for cell in CELLS)


def state(tree: Tree) -> dict[str, tuple[tuple[str, int], ...]]:
    """Per cell, in cell order, a document parse tree's state variables and their sizes;
    CanonicalError when a name is declared twice."""
    cells = {
        node.data[6:]: tuple((str(v.children[0]), int(v.children[1])) for v in child.children)
        for top in _top(tree, "state")
        for node in top.iter_subtrees_topdown()
        if node.data in STATE_RULES
        for child in node.children
        if isinstance(child, Tree) and child.data == "state_vars"
    }
    names = [n for variables in cells.values() for n, _ in variables]
    if len(set(names)) != len(names):
        raise CanonicalError(f"state variables declared twice: {names}")
    return cells


def _top(tree: Tree, data: str) -> list:
    """The top-level nodes named ``data`` of a document parse tree."""
    return [c for c in tree.children if isinstance(c, Tree) and c.data == data]


def _records(tree: Tree, kind: str = "mod"):
    """``(key, body)`` of each definition of ``kind`` in a document parse tree, its section's
    records then those at their first use: a template's key a SIGNATURE token and its body a
    ``code``, ``asm``, ``expr`` or ``fexpr`` tree, a program template's a program."""
    for node in _top(tree, f"def_{kind}"):
        yield from zip(node.children[::2], node.children[1::2])
    yield from ((key, body) for k, key, body in first_uses(tree) if k == kind)


_USES = {
    "use_ins": "ins",
    "use_restart": "restart",
    "use_ctrl": "ctrl",
    "use_pw": "pw",
    "use_filter": "filter",
    "use_phrase": "phrase",
    "use_section": "section",
}
_SITES = {
    "ins_ctrl": "ctrl",
    "ins_restart": "restart",
    "ins_pw": "pw",
    "ins_filter": "filter",
    "def_pw": "pw",
    "def_filter": "filter",
    "use_pw": "pw",
    "use_filter": "filter",
}
_KEYS = {"DEF_SIG": "SIGNATURE", "DEF_INS": "INS", "DEF_RESTART": "RESTART", "DEF_CTRL": "CTRL"}
_KEYS |= {"DEF_PW": "PW", "DEF_FILTER": "FILTER", "DEF_PHRASE": "PHRASE"}
_KEYS |= {"DEF_SECTION": "SECTION"}
_BODIES = {"asm": "mod", "fexpr": "mod", "instrument": "ins", "phrase": "phrase"}


def first_uses(tree: Tree) -> tuple:
    """``(kind, key, body)`` of each definition at its first use in a document parse tree, in
    reading order: its key a token of its section's key type without the ``=``; a template's
    kind ``mod`` for a code or expression body, else the program kind of its site (found once
    per tree)."""
    if getattr(tree, "_first_uses", None) is None:
        tree._first_uses = tuple(_walk_uses(tree))  # pylint: disable=protected-access
    return tree._first_uses  # pylint: disable=protected-access


def _walk_uses(tree: Tree):
    stack = [(tree, (None, None))]
    while stack:
        node, (parent, grand) = stack.pop()
        if node.data in _USES or node.data == "use_template":
            key, body = node.children[0], node.children[1]
            key = Token.new_borrow_pos(_KEYS[key.type], key[:-1], key)
            if node.data in _USES:
                kind = _USES[node.data]
            elif body.data in _BODIES:
                kind = _BODIES[body.data]
            elif body.data == "run_program":
                kind, body = str(body.children[0]), body.children[1]
            elif (kind := _SITES.get(parent if parent != "modulation" else grand)) is None:
                raise CanonicalError(f"{key}: a program template stands where a program does")
            yield kind, key, body
        stack.extend(
            (c, (node.data, parent)) for c in reversed(node.children) if isinstance(c, Tree)
        )


def _name(token: Token) -> str:
    """The name a key or reference token names: a template's without its parameters."""
    return token.partition("(")[0].rstrip("=")


_REFS = frozenset({"INS", "RESTART", "CTRL", "PW", "FILTER", "PHRASE", "CALL", "SECTION"})
_REFS |= {"PHRASE_CALL"}
_KINDS = ("mod", "restart", "ins", "ctrl", "pw", "filter", "phrase", "section")


def _scope(tree: Tree, uses: list):
    """CanonicalError where a name is defined twice, or referenced before its definition at its
    first use; a section's records are defined throughout."""
    keys = [k for kind in _KINDS for node in _top(tree, f"def_{kind}") for k in node.children[::2]]
    top, skip = {_name(k) for k in keys}, {id(k) for k in keys}
    later, defined = {_name(k) for _, k, _ in uses}, set()
    for token in tree.scan_values(lambda v: v.type in _REFS or v.type in _KEYS):
        name = _name(token)
        if token.type in _KEYS:
            if name in top or name in defined:
                raise CanonicalError(f"{name} is defined twice")
            defined.add(name)
        elif id(token) not in skip and name in later and name not in defined:
            raise CanonicalError(f"{name} is referenced before its definition")


def templates(tree: Tree) -> dict[str, tuple]:
    """A document parse tree's checked code templates by name; no label names a state
    variable, and a signature declares the parameters the routine reads."""
    names = {n for variables in state(tree).values() for n, _ in variables}
    out = {}
    for key, body in _records(tree):
        if body.data in ("code", "asm"):
            statements = check(Statements().transform(body), names)
            out[declare(key, params(statements), names)[0]] = statements
    return out


def signatures(tree: Tree) -> dict[str, tuple[str, ...]]:
    """The declared parameters of each template of a document parse tree keyed by its
    signature, checked as :func:`declare` checks them (an expression's parameters are its
    :func:`~unitracker_grammar.expr.params`)."""
    names, out = {n for variables in state(tree).values() for n, _ in variables}, {}
    for key, body in _records(tree):
        name, declared = declare(key, reads(body), names)
        if name in out:
            raise CodeError(f"template {name} is defined twice")
        out[name] = declared
    return out


def reads(body: Tree) -> tuple[str, ...]:
    """The parameters a template's ``code`` (``asm``) or ``expr`` (``fexpr``) parse tree reads."""
    if body.data in ("code", "asm"):
        return params(Statements().transform(body))
    return tuple(sorted(expr.params(expr.Nodes().transform(body))))


PROGRAM_KINDS = ("restart", "ctrl", "pw", "filter")


_CELL_LINKS = frozenset(f"row_{c}" for c in LATER_CELLS) | {"ins_ad", "ins_sr"}


def _cell_reads(value: Tree, out: list, declared, integer: bool):
    """``out`` extended by the parameter a cell's value ``value`` is alone (any ``integer``
    cell's, an integer position format 2.4 had, else only of a template of ``declared``
    parameters); CodeError where a declared parameter is part of a larger expression."""
    node = expr.Nodes().transform(value)
    if (declared is None and not integer) or not expr.params(node):
        return
    if isinstance(node, ast.Name):
        out.append(node.id)
    elif expr.params(node) & set(declared or ()):
        raise CodeError(f"{expr.printed(node)}: a parameter is a whole cell value")


def _reads(node: Tree, out: list, skip=frozenset(), declared=None) -> list:
    """``out`` extended by the parameters ``node`` reads in order (see :func:`program_reads`),
    the subtrees whose ids are in ``skip`` left out; a cell value's names are a template's
    reads only where its ``declared`` parameters are given."""
    for child in node.children:
        if isinstance(child, Token):
            if child.type == "PARAM" and node.data != "factor":
                out.append(str(child))
            elif child.type == "REL_PARAM":
                out.append(child[1:])
            elif child.type in ("CALL", "ARGS"):
                out.extend(
                    a
                    for a in call(f"a{child}"[child.type == "CALL" :]).args
                    if isinstance(a, str) and (a not in CHORDS or a in (declared or ()))
                )
        elif id(child) in skip:
            continue
        elif child.data == "fexpr" and node.data in ("cell_value", "modulation", *_CELL_LINKS):
            _cell_reads(child, out, declared, node.data in _CELL_LINKS)
        elif child.data == "cell_value" and node.data in _CELL_LINKS:
            inner = child.children[0]
            if isinstance(inner, Tree) and inner.data == "fexpr":
                _cell_reads(inner, out, declared, True)
            else:
                _reads(child, out, skip, declared)
        elif child.data == "run_program" and (inner := _reads(child, [], skip)):
            raise CodeError(f"an inline program reads no parameter, {inner[0]}")
        else:
            _reads(child, out, skip, declared)
    return out


def program_reads(body: Tree, declared=None, skip=frozenset()) -> tuple[str, ...]:
    """The parameters a program's parse tree (a ``program`` or a pulse or filter record's
    ``modulation``) reads, in first-use order: a ``PARAM`` where a row takes an integer, a
    relative note's ``+p`` or ``-p``, a call's named arguments and, in a template of
    ``declared`` parameters, a cell value that is a name alone; CodeError where a cell
    expression names one of ``declared`` inside a larger expression, or an inline program reads
    one; the subtrees whose ids are in ``skip`` (templates defined within) left out."""
    return tuple(dict.fromkeys(_reads(body, [], skip, declared)))


def programs(tree: Tree) -> dict[str, tuple[str, tuple[str, ...]]]:
    """``{name: (kind, parameters)}`` of a document parse tree's program and instrument
    templates, checked: each declares what its rows (fields) read (:func:`program_reads`), a
    record keyed by its name reads none, nothing outside a record reads one, and no two
    templates, of programs, instruments or modulators, share a name."""
    out, bodies = {}, set()
    nested = {id(body) for _, key, body in first_uses(tree) if key.type == "SIGNATURE"}
    for kind in PROGRAM_KINDS + ("ins",):
        for key, body in _records(tree, kind):
            if isinstance(body, Token):
                if used := [a for a in call(body).args if isinstance(a, str) and a not in CHORDS]:
                    raise CodeError(f"{key}: reads {used} and declares no parameter")
                continue
            bodies.add(id(body))
            if key.type == "SIGNATURE":
                reads_ = program_reads(body, signature(key)[1], nested - {id(body)})
                name, declared = declare(key, reads_)
                if name in out:
                    raise CodeError(f"program template {name} is defined twice")
                out[name] = (kind, declared)
            elif used := program_reads(body, skip=nested):
                raise CodeError(f"{key}: reads {list(used)} and declares no parameter")
    if outside := _reads(tree, [], bodies):
        raise CodeError(f"parameters {list(dict.fromkeys(outside))} read outside a template")
    mods = {signature(key)[0] for key, _ in _records(tree)}
    if clash := sorted(out.keys() & mods):
        raise CodeError(f"{clash} name both a program and a modulator template")
    return out


_CELLS = {"pw": "row_pw", "filter": "row_cut"}


def _links(row: Tree) -> list:
    """The links of a program row's key chain that carry their own key."""
    return [
        n
        for n in row.iter_subtrees_topdown()
        if n is not row
        and n.data.startswith("row_")
        and any(not (isinstance(c, Tree) and c.data.startswith("row_")) for c in n.children)
    ]


def _long(kind: str, body: Tree) -> bool:
    """Whether a pulse or filter record's ``modulation`` is a program of one row binding the
    cell's first slot, ``[{pw:b},end]``, which is written ``b``."""
    program = body.children[0]
    if not isinstance(program, Tree) or program.data != "program":
        return False
    rows = [c for c in program.children if isinstance(c, Tree)]
    if len(rows) != 1 or program.children[-1].type != "END":
        return False
    links = _links(rows[0])
    if len(links) != 1 or links[0].data != _CELLS[kind]:
        return False
    (value,) = (c.children[0] for c in links[0].children if isinstance(c, Tree))
    slotted = any(isinstance(c, Token) for c in links[0].children)
    return not slotted and (isinstance(value, Tree) or value.type == "CALL")


def _nodes(tree: Tree, skip: set):
    """``(node, outside)`` of every subtree of ``tree``, ``outside`` whether it is outside the
    subtrees whose ids are in ``skip``."""
    stack = [(tree, True)]
    while stack:
        node, outside = stack.pop()
        outside = outside and id(node) not in skip
        yield node, outside
        stack.extend((c, outside) for c in node.children if isinstance(c, Tree))


def check_document(tree: Tree) -> Tree:
    """``tree``, a document's parse tree, if what its grammar cannot say holds, else CodeError
    or ExpressionError: its state names (:func:`state`), its templates (:func:`templates`,
    :func:`signatures`, :func:`programs`), its anonymous code bodies (checked as templates,
    reading no parameter), its tables (every table an expression or code reads is defined),
    an expression outside a template reads no parameter nor names a template, and a pulse or
    filter record that is one binding is written as that binding, and the format is the latest
    one whose constructs the document has (CanonicalError)."""
    names = {n for variables in state(tree).values() for n, _ in variables}
    uses = list(first_uses(tree))
    _scope(tree, uses)
    templates(tree)
    named = signatures(tree).keys() | programs(tree).keys()
    tables = {"F"} | {str(t) for node in _top(tree, "tables") for t in node.children[::2]}
    signed = {
        id(body)
        for kind in PROGRAM_KINDS + ("ins",)
        for key, body in _records(tree, kind)
        if key.type == "SIGNATURE"
    } | {id(body) for kind, key, body in uses if kind == "mod"}
    for node, outside in _nodes(tree, signed):
        if node.data == "asm" and outside:
            statements = check(Statements().transform(node), names)
            if used := params(statements):
                raise CodeError(f"{inline(statements)}: an anonymous body reads {list(used)}")
        elif node.data == "fexpr" and outside:
            if bound := sorted(expr.params(expr.Nodes().transform(node)) & named):
                raise expr.ExpressionError(f"{bound}: a template is bound by a call, name(1,-2)")
            if used := expr.params(expr.Nodes().transform(node)):
                raise expr.ExpressionError(f"unbound parameters {sorted(used)}")
        for token in node.children:
            if getattr(token, "type", "") in ("XTABLE", "TABLE_BYTE"):
                if token.split(".")[0] not in tables:
                    raise expr.ExpressionError(f"unknown table {token.split('.')[0]!r}")
    _short_records(tree)
    if clash := sorted((named | phrases(tree).keys()) & PRELUDE):
        raise CodeError(f"{clash} name prelude templates, which a document does not define")
    _version(tree, named)
    return tree


_LATER_KEYS = tuple(f"{p}_{c}" for p in ("row", "cmd") for c in LATER_CELLS)
_LATER_KEYS += ("ins_ad", "ins_sr")
_LINKS = ("row_", "cmd_", "ins_")
_EXPRESSION = frozenset({"fexpr", "expr", "term", "factor"})


def _plain(value) -> bool:
    """Whether a cell's value in a parse tree is an integer or a template's parameter."""
    while isinstance(value, Tree) and value.data in _EXPRESSION and len(value.children) == 1:
        value = value.children[0]
    return isinstance(value, Token) and value.type in ("INT", "PARAM")


def _binds(link: Tree) -> bool:
    """Whether a row's, an instrument's or a command's key in a parse tree binds a modulator or
    stops one: a slot's prefix, or a value that is no integer nor parameter."""
    for child in link.children:
        if isinstance(child, Tree) and child.data.startswith(_LINKS):
            continue
        if isinstance(child, Token) and child.type.startswith("CMD_"):
            if "." in child:
                return True
        elif isinstance(child, Token) and child.type == "SLOT":
            return True
        elif not _plain(child.children[0] if getattr(child, "data", "") == "cell_value" else child):
            return True
    return False


def _later_node(node: Tree) -> bool:
    """Whether one node of a document's parse tree is a construct of format 2.5."""
    tokens = [c for c in node.children if isinstance(c, Token)]
    if node.data == "global_cells":
        return any(t.type != "GCUT" for t in tokens)
    if node.data == "slot_cell":
        return tokens[0] in LATER_CELLS
    if node.data == "order":
        return any(t in LATER_PHASES for t in tokens)
    if node.data in STATE_RULES:
        return node.data not in ("state_freq", "state_pw", "state_cut")
    return node.data in _LATER_KEYS and _binds(node)


def format_2_5(tree: Tree) -> bool:
    """Whether a document's parse tree has a construct of format 2.5 (see
    :func:`unitracker_grammar.features.uses`, which finds the same in the model)."""
    if _top(tree, "calls") or _top(tree, "holds") or expr.later(tree):
        return True
    return any(_later_node(node) for node in tree.iter_subtrees())


def _version(tree: Tree, named):
    """CanonicalError unless the format is 2.5 exactly where the document has a construct 2.5
    adds, else 2.4 exactly where it has layers, orderlists or a call of a prelude program it does
    not define."""
    calls = any(
        isinstance(t, Token) and t.type == "CALL" and _name(t) in PROGRAMS and _name(t) not in named
        for node in tree.find_data("ins_restart")
        for t in node.children
    )
    earlier = bool(_top(tree, "layers") or _top(tree, "voice") or calls)
    wanted = "2.5" if format_2_5(tree) else "2.4" if earlier else "2.3"
    if not tree.children[0].endswith(wanted):
        raise CanonicalError(
            f"a document is format {wanted} exactly where it has a construct of that format: "
            "2.5 a calls, holds or global line but the cutoff's, a binding of ctrl, ad, sr, res, "
            "route, mode or vol, a slots, state or order line for them, or an expression with "
            "the bitwise, logic or wrap operators; 2.4 layers, orderlists or a prelude program"
        )


def _short_records(tree: Tree):
    """CanonicalError for a pulse or filter record of one binding not written as it."""
    for kind in _CELLS:
        for key, body in _records(tree, kind):
            if _long(kind, body):
                raise CanonicalError(f"{key}: a program of one binding is written as the binding")


def phrases(tree: Tree) -> dict[str, tuple[str, ...]]:
    """``{name: parameters}`` of a document parse tree's phrase templates, each declaring the
    notes its events stand a parameter for; CodeError for a note's parameter outside one."""
    out, bodies = {}, set()
    for key, body in _records(tree, "phrase"):
        if key.type == "SIGNATURE" and isinstance(body, Tree):
            bodies.add(id(body))
            used = dict.fromkeys(str(t) for t in body.scan_values(lambda v: v.type == "NOTE_PARAM"))
            out[declare(key, used)[0]] = signature(key)[1]
    for node, outside in _nodes(tree, bodies):
        if outside and node.data == "event" and node.children[0].type == "NOTE_PARAM":
            raise CodeError(f"{node.children[0]}: a note's parameter outside a phrase template")
    return out
