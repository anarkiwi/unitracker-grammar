"""Format 2.5's constructs: :func:`uses` says whether a document has any, which makes it format
2.5 (:attr:`~unitracker_grammar.model.Document.version`)."""

from dataclasses import fields, is_dataclass

from unitracker_grammar import expr
from unitracker_grammar.cells import LATER_CELLS, LATER_PHASES
from unitracker_grammar.code import Call
from unitracker_grammar.model import (
    HOLD,
    NONE,
    PARAM,
    RESET,
    Code,
    Def,
    Document,
    Event,
    Expr,
    Instrument,
    Once,
    Row,
    base,
)

__all__ = ["uses"]

_FIELDS = ("ad", "sr")


def _nodes(value):
    """``value`` and everything in it, a routine's statements left out."""
    yield value
    if is_dataclass(value) and not isinstance(value, Code):
        inside = (getattr(value, f.name) for f in fields(value))
    elif isinstance(value, tuple) and not isinstance(value, Code):
        inside = value
    else:
        return
    for child in inside:
        yield from _nodes(child)


def _bound(key: str, value) -> bool:
    """Whether a cell's key, with its slot prefix or its value, binds a modulator or stops it
    rather than sets an integer (or a template's parameter)."""
    if key != base(key) or value in (NONE, HOLD, RESET):
        return True
    if isinstance(value, Expr):
        return not (value.text.isdigit() or PARAM.fullmatch(value.text))
    return isinstance(value, (Call, Code, Once, Def))


def _pairs(node):
    """The ``(key, value)`` pairs of a row, an instrument or an event that name cells format 2.5
    can bind."""
    if isinstance(node, Row):
        return node.keys
    if isinstance(node, Event):
        return node.commands
    if isinstance(node, Instrument):
        return [(k, v) for k, v in node.fields if base(k) in _FIELDS]
    return ()


def uses(doc: Document) -> bool:
    """Whether ``doc`` has a construct of format 2.5: a ``calls`` or ``holds`` line, a global
    cell but the cutoff, a slots or state line or an order line naming a cell or phase 2.5 adds,
    a binding or stop of a cell 2.5 adds, or an expression with an operator, function or
    comparison 2.5 adds."""
    head = doc.header
    if head.calls is not None or head.holds is not None:
        return True
    if set(head.global_cells or ()) - {"cut"} or set(head.order or ()) & set(LATER_PHASES):
        return True
    if {c for c, _ in (head.slots or ()) + (head.state or ())} & set(LATER_CELLS):
        return True
    for node in _nodes(doc):
        if isinstance(node, Expr) and expr.later(node.text):
            return True
        if any(base(k) in LATER_CELLS and _bound(k, v) for k, v in _pairs(node)):
            return True
    return False
