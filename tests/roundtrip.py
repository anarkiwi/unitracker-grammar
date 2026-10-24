"""A pytest plugin: every document a test parses must print back as its text from its model.

``pytest -p roundtrip`` (with this directory on the path) runs it over another suite."""

import pytest

from unitracker_grammar import canonical
from unitracker_grammar.document import printed, read

_SEEN: list = []


def _recording(parse):
    def recorded(text, *args, **kwargs):
        tree = parse(text, *args, **kwargs)
        if not args and not kwargs:
            _SEEN.append(text)
        return tree

    return recorded


def pytest_configure(config):  # pylint: disable=unused-argument
    lark = canonical.parser()
    lark.parse = _recording(lark.parse)


def mismatch(text: str) -> str | None:
    """Why ``text`` does not round-trip through its model, or None."""
    doc = read(text)
    out = printed(doc)
    if out != text:
        lines = zip(text.splitlines(), out.splitlines())
        line = next((i for i, (a, b) in enumerate(lines, 1) if a != b), None)
        return f"printed differs at line {line}:\n{text}\n---\n{out}"
    if read(out) != doc:
        return f"read(printed(doc)) != doc:\n{text}"
    return None


@pytest.fixture(autouse=True)
def round_trip():
    """Fails the test whose documents do not round-trip."""
    _SEEN.clear()
    yield
    failures = [why for text in dict.fromkeys(_SEEN) if (why := mismatch(text))]
    _SEEN.clear()
    assert not failures, failures[0]
