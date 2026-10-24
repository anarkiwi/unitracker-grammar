"""The canonical document grammar, ``canonical.lark``, and a parser for it."""

import functools
from importlib import resources

from lark import Lark, Tree, exceptions

GRAMMAR = resources.files("unitracker_grammar") / "canonical.lark"


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


def parse(text: str) -> Tree:
    """The parse tree of canonical document ``text``, checked by
    :func:`unitracker_grammar.code.check_document`: CanonicalError outside the grammar, naming
    the line and column, and that function's errors where it refuses the tree."""
    from unitracker_grammar import code  # pylint: disable=import-outside-toplevel,cyclic-import

    try:
        tree = parser().parse(text)
    except exceptions.UnexpectedInput as exc:
        raise CanonicalError(
            f"line {exc.line} column {exc.column}: {str(exc).splitlines()[0]}"
        ) from exc
    code.check_document(tree)
    return tree
