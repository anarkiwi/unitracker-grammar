"""The canonical document grammar, ``canonical.lark``, and a parser for it."""

import functools
import re
from importlib import resources

from lark import Lark, Token, Tree, exceptions

GRAMMAR = resources.files("unitracker_grammar") / "canonical.lark"
_NOTE = re.compile(r"([A-Ga-g])(-?\d+)?")


class CanonicalError(ValueError):
    """A text that is not a canonical document."""


@functools.lru_cache(maxsize=1)
def parser() -> Lark:
    """The LALR parser of the canonical grammar, its trees carrying their positions."""
    return Lark(
        GRAMMAR.read_text(encoding="utf-8"),
        parser="lalr",
        lexer="contextual",
        propagate_positions=True,
    )


def absolute(note: str, octave: str | None = None) -> str:
    """A written note as its letter, ``#`` for a sharp, and its octave: ``c4`` is ``C#4``, and a
    note written without its octave (``E``) takes ``octave``; CanonicalError where it has none."""
    letter, written = _NOTE.fullmatch(note).groups()
    if (written or octave) is None:
        raise CanonicalError(f"{note}: a note without its octave where no note before it has one")
    return letter.upper() + "#" * letter.islower() + (written or octave)


def _resolve(tree: Tree):
    """Each note of ``tree`` written absolute (``C#4``): a phrase's notes in order, each without
    its octave taking the previous note's in that phrase, ``init``'s and a program row's each
    with its own."""
    for node in tree.iter_subtrees():
        if node.data in ("phrase", "init"):
            octave = None
            for event in node.children:
                atom = event.children[0]
                if _NOTE.fullmatch(atom):
                    note = _absolute(atom, octave if node.data == "phrase" else None)
                    event.children[0] = note
                    octave = note.lstrip("ABCDEFG#")
        elif node.data == "note_value" and node.children[0].type == "NOTE":
            node.children[0] = _absolute(node.children[0])


def _absolute(token: Token, octave: str | None = None) -> Token:
    try:
        return token.update(value=absolute(token, octave))
    except CanonicalError as exc:
        raise CanonicalError(f"line {token.line} column {token.column}: {exc}") from exc


def parse(text: str) -> Tree:
    """The parse tree of canonical document ``text``, its notes absolute (``C#4``; a phrase's
    octaves filled in) and checked by :func:`unitracker_grammar.code.check_document`:
    CanonicalError outside the grammar, naming the line and column, and that function's errors
    where it refuses the tree."""
    from unitracker_grammar import code  # pylint: disable=import-outside-toplevel,cyclic-import

    try:
        tree = parser().parse(text)
    except exceptions.UnexpectedInput as exc:
        raise CanonicalError(
            f"line {exc.line} column {exc.column}: {str(exc).splitlines()[0]}"
        ) from exc
    _resolve(tree)
    code.check_document(tree)
    return tree
