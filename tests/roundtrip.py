"""A pytest plugin: every document a test parses must be the one canonical text its model prints;
``unitracker_grammar.document.read``'s own parses are a model's, not a test's, and go unchecked.

``pytest -p roundtrip`` (with this directory on the path) runs it over another suite."""

import contextlib

import pytest

from unitracker_grammar import canonical, document
from unitracker_grammar.document import printed, read

_SEEN: list = []
_QUIET: list = []


@contextlib.contextmanager
def _unrecorded():
    _QUIET.append(True)
    try:
        yield
    finally:
        _QUIET.pop()


def _quiet(reader):
    def unrecorded(text):
        with _unrecorded():
            return reader(text)

    return unrecorded


def _recording(parse):
    def recorded(text, *args, **kwargs):
        tree = parse(text, *args, **kwargs)
        if not args and not kwargs and not _QUIET:
            _SEEN.append(text)
        return tree

    return recorded


def pytest_configure(config):
    config.addinivalue_line("markers", "noncanonical: reads texts other than the canonical one")
    lark = canonical.parser()
    lark.parse = _recording(lark.parse)
    document.read = _quiet(document.read)


def mismatch(text: str) -> str | None:
    """Why ``text`` is not the one canonical text of its model, or None (None too where the
    grammar's checks refuse it)."""
    try:
        doc = read(text)
    except ValueError:
        return None
    out = printed(doc)
    if out != text:
        lines = zip(text.splitlines(), out.splitlines())
        line = next((i for i, (a, b) in enumerate(lines, 1) if a != b), None)
        return f"printed differs at line {line}:\n{text}\n---\n{out}"
    if read(out) != doc:
        return f"read(printed(doc)) != doc:\n{text}"
    return None


@pytest.fixture(autouse=True)
def round_trip(request):
    """Fails the test whose documents are not their one canonical text, but a test marked
    ``noncanonical``, which reads the grammar's other spellings."""
    _SEEN.clear()
    yield
    if request.node.get_closest_marker("noncanonical"):
        _SEEN.clear()
        return
    failures = [why for text in dict.fromkeys(_SEEN) if (why := mismatch(text))]
    _SEEN.clear()
    assert not failures, failures[0]
