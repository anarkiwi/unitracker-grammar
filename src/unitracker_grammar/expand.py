"""Format 2.3's sugar written in the core: :func:`expanded` is the document a player plays, its
templates of instruments and phrases, groups, sections and chord names spelled out (a prelude
call stays a call); :func:`core` the parse tree of a text's core."""

from dataclasses import replace

from lark import Token, Tree

from unitracker_grammar import code as _code
from unitracker_grammar.canonical import CanonicalError, parse
from unitracker_grammar.chords import CHORDS
from unitracker_grammar.document import (
    KINDS,
    Call,
    Document,
    Expr,
    Group,
    Instrument,
    Once,
    Part,
    Play,
    Section,
    SongRow,
    _order,
    _walk,
    printed,
    read,
    top_level,
)

__all__ = ["core", "expanded", "flat"]

_SUGAR = frozenset({"group", "song_group", "part", "def_section", "use_template"})
_SUGAR |= {f"use_{k}" for k in KINDS}


def _templates(doc: Document, kind: str) -> dict:
    """``{name: (parameters, body)}`` of the records of ``kind`` keyed by a signature."""
    return {
        _code.signature(k)[0]: (_code.signature(k)[1], v)
        for k, v in doc.records(kind).items()
        if "(" in k
    }


def _call(call: Call, params: tuple) -> dict:
    if len(call.args) != len(params):
        raise CanonicalError(f"{call}: {call.name} takes {len(params)} argument(s)")
    return dict(zip(params, call.args))


def _chords(call: Call, params=()) -> Call:
    """``call`` with each argument that is a chord's name, and no parameter of ``params``, its
    intervals."""
    args = []
    for a in call.args:
        args += CHORDS[a] if isinstance(a, str) and a in CHORDS and a not in params else [a]
    return Call(call.name, tuple(args))


def _named_chords(doc: Document) -> Document:
    """``doc`` with every call's chord names their intervals, a template's parameters kept."""

    def visit(params):
        def fn(value, site):
            return _chords(value, params) if isinstance(value, Call) and site != "phrase" else value

        return fn

    defs = []
    for section in doc.defs:
        records = []
        for key, value in section.records:
            params = _code.signature(key)[1] if "(" in key else ()
            records.append((key, _walk(value, visit(params), section.kind)))
        defs.append(replace(section, records=tuple(records)))
    rest = _order(replace(doc, defs=()), visit(()))
    return replace(rest, defs=tuple(defs))


def _bound(value, bag: dict):
    """An instrument template's field value with each parameter its integer in ``bag``."""
    if isinstance(value, str) and value in bag:
        return bag[value]
    if isinstance(value, Expr) and value.text in bag:
        return bag[value.text]
    if isinstance(value, Call):
        return Call(
            value.name, tuple(bag.get(a, a) if isinstance(a, str) else a for a in value.args)
        )
    if isinstance(value, Once):
        return Once(_bound(value.value, bag))
    if isinstance(value, Instrument):
        return replace(value, fields=tuple((k, _bound(v, bag)) for k, v in value.fields))
    return value


def _instruments(doc: Document) -> Document:
    """``doc`` with each distinct call of an instrument template a named instrument, the next
    free ``iK`` in reading order."""
    templates = _templates(doc, "ins")
    base = max((int(n[1:]) for n in doc.records("ins") if "(" not in n), default=0)
    names, made = {}, []

    def instance(call: Call) -> Instrument:
        if call.name not in templates:
            raise CanonicalError(f"{call}: {call.name} is no instrument template")
        params, body = templates[call.name]
        return _bound(body, _call(call, params))

    named = [
        (k, instance(v) if isinstance(v, Call) else v)
        for k, v in doc.records("ins").items()
        if "(" not in k
    ]
    doc = _with(doc, "ins", named + [(k, v) for k, v in doc.records("ins").items() if "(" in k])

    def visit(value, site):
        if site != "ins" or not isinstance(value, Call):
            return value
        if value not in names:
            names[value] = f"i{base + len(made) + 1}"
            made.append((names[value], instance(value)))
        return names[value]

    doc = _order(doc, visit)
    records = [(k, v) for k, v in doc.records("ins").items() if "(" not in k] + made
    return _with(doc, "ins", records)


def _with(doc: Document, kind: str, records: list) -> Document:
    """``doc`` with section ``kind``'s records ``records`` (none: no section)."""
    sections = {s.kind: s for s in doc.defs} | {kind: Section(kind, tuple(records))}
    return replace(
        doc, defs=tuple(sections[k] for k in KINDS if sections.get(k, Section(k)).records)
    )


def flat(items: tuple) -> tuple:
    """``items``, events or song items, with each group played out: its body ``times`` times,
    or its body before each of its endings."""
    out = []
    for item in items:
        if not isinstance(item, Group):
            out.append(item)
        elif item.endings:
            if len(item.endings) < 2 and item.times is None:
                raise CanonicalError("a volta has two endings or more")
            for ending in item.endings:
                out += flat(item.body) + flat(ending)
        else:
            out += flat(item.body) * item.times
    return tuple(out)


def _phrase(events: tuple, bag: dict) -> tuple:
    """A phrase template's events with each note's parameter its note in ``bag``."""
    out = []
    for e in events:
        if isinstance(e, Group):
            out.append(replace(e, body=_phrase(e.body, bag), endings=_phrases_of(e.endings, bag)))
        else:
            out.append(replace(e, note=bag.get(e.note, e.note)))
    return tuple(out)


def _phrases_of(endings: tuple, bag: dict) -> tuple:
    return tuple(_phrase(e, bag) for e in endings)


def _phrases(doc: Document) -> Document:
    """``doc`` with each phrase template's call its events, inline, and every phrase's groups
    played out."""
    templates = _templates(doc, "phrase")

    def visit(value, site):
        if site == "phrase" and isinstance(value, Call):
            if value.name not in templates:
                raise CanonicalError(f"{value}: {value.name} is no phrase template")
            params, body = templates[value.name]
            return _phrase(body, _call(value, params))
        return value

    def played(node):
        if isinstance(node, Play) and isinstance(node.phrase, tuple):
            return replace(node, phrase=flat(node.phrase))
        if isinstance(node, SongRow):
            return replace(node, play=tuple(played(p) for p in node.play))
        return node

    doc = _order(doc, visit)
    records = [(k, flat(v)) for k, v in doc.records("phrase").items() if "(" not in k]
    doc = replace(_with(doc, "phrase", records), rows=_map_rows(doc.rows, played))
    sections = [(k, _map_rows(v, played)) for k, v in doc.records("section").items()]
    return _with(doc, "section", sections)


def _map_rows(items: tuple, fn) -> tuple:
    out = []
    for item in items:
        if isinstance(item, Group):
            item = replace(
                item,
                body=_map_rows(item.body, fn),
                endings=tuple(_map_rows(e, fn) for e in item.endings),
            )
        out.append(fn(item))
    return tuple(out)


def _song(doc: Document) -> Document:
    """``doc`` with its song's sections and groups played out into rows, its loop the row its
    loop item starts."""
    sections = doc.records("section")

    def rows(items: tuple, seen: tuple) -> list:
        out = []
        for item in flat(items):
            if isinstance(item, Part):
                if item.section in seen:
                    raise CanonicalError(f"section {item.section} plays itself")
                if item.section not in sections:
                    raise CanonicalError(f"unknown section {item.section}")
                out += rows(sections[item.section], seen + (item.section,)) * (item.times or 1)
            else:
                out.append(item)
        return out

    starts, out = [], []
    for item in doc.rows:
        starts.append(len(out))
        out += rows((item,), ())
    loop = None if doc.loop is None else starts[doc.loop] if doc.loop < len(starts) else len(out)
    return replace(_with(doc, "section", []), rows=tuple(out), loop=loop)


def expanded(doc: Document) -> Document:
    """``doc`` in format 2.3's core: its definitions in their sections, every call's chord
    names their intervals, each instrument template's call an instrument, each phrase
    template's call its phrase, and groups and sections played out; CanonicalError where a call
    does not fit its template."""
    for step in (top_level, _named_chords, _instruments, _phrases, _song):
        doc = step(doc)
    return doc


def _sugared(tree: Tree) -> bool:
    """Whether a document's parse tree holds any of format 2.3's sugar or a definition at its
    first use."""
    for node in tree.iter_subtrees():
        if node.data in _SUGAR:
            return True
        for token in node.children:
            if not isinstance(token, Token):
                continue
            if token.type in ("PHRASE_CALL", "NOTE_PARAM"):
                return True
            if token.type == "SIGNATURE" and node.data in ("def_ins", "def_phrase"):
                return True
            if token.type == "CALL" and node.data in ("def_ins", "use_ins"):
                return True
            if token.type == "CALL":
                found = _code.call(token)
                if node.data == "event":
                    return True
                if any(isinstance(a, str) and a in CHORDS for a in found.args):
                    return True
    return False


def core(text: str) -> Tree:
    """The parse tree of document ``text`` in format 2.3's core (:func:`expanded`)."""
    tree = parse(text)
    return parse(printed(expanded(read(text)))) if _sugared(tree) else tree
