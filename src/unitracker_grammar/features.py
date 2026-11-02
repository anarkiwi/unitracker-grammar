"""Format 2.5's constructs: :func:`uses` says whether a document has any, which makes it format
2.5 (:attr:`~unitracker_grammar.model.Document.version`)."""

from dataclasses import fields, is_dataclass

from unitracker_grammar import expr
from unitracker_grammar.cells import LATER_CELLS, LATER_PHASES, TERM
from unitracker_grammar.code import Call
from unitracker_grammar.model import (
    HOLD,
    NONE,
    PARAM,
    RESET,
    Code,
    Def,
    Document,
    Env,
    Event,
    Expr,
    Header,
    Instrument,
    Once,
    Row,
    Slot,
    Writes,
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
    return isinstance(value, (Call, Code, Once, Def, Writes))


def _all(node):
    """The ``(key, value)`` pairs of a row, an instrument or an event."""
    if isinstance(node, Row):
        return node.keys
    if isinstance(node, Event):
        return node.commands
    if isinstance(node, Instrument):
        return node.fields
    return ()


def _pairs(node):
    """The ``(key, value)`` pairs of a row, an instrument or an event that name cells format 2.5
    can bind."""
    pairs = _all(node)
    return [(k, v) for k, v in pairs if not isinstance(node, Instrument) or base(k) in _FIELDS]


def _long_tempo(node) -> bool:
    """Whether ``node`` is a tempo of more than two entries, a header's or an event's."""
    if isinstance(node, Header):
        return len(node.tempo or ()) > 2
    return isinstance(node, Event) and any(
        len(v) > 2 for k, v in node.commands if k in ("tempo", "vtempo")
    )


def _event_slot(node) -> bool:
    """Whether ``node`` is a slot holding or resetting on the ``event`` event."""
    return isinstance(node, Slot) and any(
        e.split("-")[0] == "event" for e in (node.hold or ()) + (node.reset or ())
    )


def _later_expr(node) -> bool:
    return isinstance(node, Expr) and expr.later(node.text)


def _later_node(node) -> bool:
    """Whether one node of a document is a construct of format 2.5 inside a header, a row, an
    instrument or an event."""
    return (
        _event_slot(node)
        or isinstance(node, Env)
        or _later_expr(node)
        or _long_tempo(node)
        or any(k.startswith(TERM + ".") for k, _ in _all(node))
        or any(base(k) in LATER_CELLS and _bound(k, v) for k, v in _pairs(node))
    )


def uses(doc: Document) -> bool:
    """Whether ``doc`` has a construct of format 2.5: a ``calls`` or ``holds`` line, a global
    cell but the cutoff, a slots or state line or an order line naming a cell or phase 2.5 adds,
    an env, a binding or stop of a cell 2.5 adds, a ``mask`` term, a tempo of more than two
    entries, or an expression with an operator, function, cell name or comparison 2.5 adds."""
    head = doc.header
    if head.calls is not None or head.holds is not None:
        return True
    if set(head.global_cells or ()) - {"cut"} or set(head.order or ()) & set(LATER_PHASES):
        return True
    if {c for c, _ in (head.slots or ()) + (head.state or ())} & set(LATER_CELLS):
        return True
    return any(_later_node(node) for node in _nodes(doc))
