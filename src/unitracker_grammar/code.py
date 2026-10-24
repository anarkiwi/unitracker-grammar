"""Code templates: NMOS 6502 routines a ``mod:`` record may be, read and checked.

A routine is a tuple of statements, each a :class:`Label` or an :class:`Op`, whose operand is
``None`` (implied), an :class:`Imm`, a :class:`Mem` or, for a branch or ``jmp``, a label's name;
:func:`printed` is its one text. A template's key may be its signature, ``name(a, b)``, which a
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
_INDENT = " " * 4


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
    """``(name, parameters)`` of a ``SIGNATURE`` text, ``name(a, b)`` or ``name()``;
    CodeError when a parameter is declared twice."""
    name, names = _CALL.fullmatch(text).groups()
    declared = tuple(names.split(", ")) if names else ()
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
    ``+offset`` when not 0) and its ``index`` (written ``,x`` or ``,y`` when set)."""

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
        offset = f"+{operand.offset}" if operand.offset else ""
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


def state(tree: Tree) -> dict[str, tuple[tuple[str, int], ...]]:
    """Per cell, in cell order, a document parse tree's state variables and their sizes;
    CanonicalError when a name is declared twice."""
    cells = {
        node.data[6:]: tuple((str(v.children[0]), int(v.children[1])) for v in child.children)
        for node in tree.iter_subtrees_topdown()
        if node.data in ("state_freq", "state_pw", "state_cut")
        for child in node.children
        if isinstance(child, Tree) and child.data == "state_vars"
    }
    names = [n for variables in cells.values() for n, _ in variables]
    if len(set(names)) != len(names):
        raise CanonicalError(f"state variables declared twice: {names}")
    return cells


def _records(tree: Tree, kind: str = "mod"):
    """``(key, body)`` of each record of a document parse tree's ``kind`` section: a template's
    key a SIGNATURE token and its body a ``code`` or ``expr`` tree."""
    for node in tree.find_data(f"def_{kind}"):
        yield from zip(node.children[::2], node.children[1::2])


def templates(tree: Tree) -> dict[str, tuple]:
    """A document parse tree's checked code templates by name; no label names a state
    variable, and a signature declares the parameters the routine reads."""
    names = {n for variables in state(tree).values() for n, _ in variables}
    out = {}
    for key, body in _records(tree):
        if body.data == "code":
            statements = check(Statements().transform(body), names)
            out[declare(key, params(statements), names)[0]] = statements
    return out


def signatures(tree: Tree) -> dict[str, tuple[str, ...]]:
    """The declared parameters of each template of a document parse tree keyed by its
    signature, checked as :func:`declare` checks them (an expression's parameters are its
    :func:`~unitracker_grammar.expr.params`)."""
    names = {n for variables in state(tree).values() for n, _ in variables}
    return dict(declare(key, reads(body), names) for key, body in _records(tree))


def reads(body: Tree) -> tuple[str, ...]:
    """The parameters a template's ``code`` or ``expr`` parse tree reads."""
    if body.data == "code":
        return params(Statements().transform(body))
    return tuple(sorted(expr.params(expr.Nodes().transform(body))))


PROGRAM_KINDS = ("restart", "ctrl", "pw", "filter")


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
            elif child.type == "CALL":
                out.extend(a for a in call(child).args if isinstance(a, str))
        elif id(child) in skip:
            continue
        elif child.data == "fexpr" and node.data in ("cell_value", "modulation"):
            value = expr.Nodes().transform(child)
            if declared is None or not expr.params(value):
                continue
            if isinstance(value, ast.Name):
                out.append(value.id)
            elif expr.params(value) & set(declared):
                raise CodeError(f"{expr.printed(value)}: a parameter is a whole cell value")
        elif child.data == "run_program" and (inner := _reads(child, [], skip)):
            raise CodeError(f"an inline program reads no parameter, {inner[0]}")
        else:
            _reads(child, out, skip, declared)
    return out


def program_reads(body: Tree, declared=None) -> tuple[str, ...]:
    """The parameters a program's parse tree (a ``program`` or a pulse or filter record's
    ``modulation``) reads, in first-use order: a ``PARAM`` where a row takes an integer, a
    relative note's ``+p`` or ``-p``, a call's named arguments and, in a template of
    ``declared`` parameters, a cell value that is a name alone; CodeError where a cell
    expression names one of ``declared`` inside a larger expression, or an inline program reads
    one."""
    return tuple(dict.fromkeys(_reads(body, [], declared=declared)))


def programs(tree: Tree) -> dict[str, tuple[str, tuple[str, ...]]]:
    """``{name: (kind, parameters)}`` of a document parse tree's program templates, checked:
    each declares what its rows read (:func:`program_reads`), a program keyed by its name reads
    none, nothing outside a program's records reads one, and no two templates, of programs or
    modulators, share a name."""
    out, bodies = {}, set()
    for kind in PROGRAM_KINDS:
        for key, body in _records(tree, kind):
            bodies.add(id(body))
            if key.type == "PROGRAM_SIG":
                name, declared = declare(key, program_reads(body, signature(key)[1]))
                if name in out:
                    raise CodeError(f"program template {name} is defined twice")
                out[name] = (kind, declared)
            elif used := program_reads(body):
                raise CodeError(f"{key}: reads {list(used)} and declares no parameter")
    if outside := _reads(tree, [], bodies):
        raise CodeError(f"parameters {list(dict.fromkeys(outside))} read outside a template")
    mods = {signature(key)[0] for key, _ in _records(tree)}
    if clash := sorted(out.keys() & mods):
        raise CodeError(f"{clash} name both a program and a modulator template")
    return out
