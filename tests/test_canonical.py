"""The canonical grammar: each form of the vocabulary has one spelling."""

import pytest
from lark import Token, Tree

from unitracker_grammar import GRAMMAR, CanonicalError, parse, parser

HEADER = "unitracker: 1.20\nplayroutine: {ref: goattracker2}\nmeta: {title: T, author: A}\n"
INS = "      ins:\n        i1: "


def doc(
    defs: str, head: str = "", play: str = "[p1, p1, p1]", ending: str = "  - {loop: 0}"
) -> str:
    """A document of one row defining ``defs`` and phrase ``p1``."""
    phrase = "      phrase:\n        p1: [C4.i1, -*3]\n"
    return f"{HEADER}{head}song:\n  - def:\n{defs}{phrase}    play: {play}\n{ending}\n"


def chain(tree: Tree, prefix: str) -> list[tuple[str, list[str]]]:
    """The links of a ``prefix`` chain under ``tree`` that carry values, outermost first."""

    def values(node):
        return [
            str(v)
            for c in node.children
            if isinstance(c, Token) or not c.data.startswith(prefix)
            for v in ([c] if isinstance(c, Token) else c.scan_values(lambda _: True))
        ]

    links = (n for n in tree.iter_subtrees_topdown() if n.data.startswith(prefix))
    return [(n.data, v) for n in links if (v := values(n))]


def first(tree: Tree, data: str) -> Tree:
    """The first subtree named ``data``, top down."""
    return next(tree.find_data(data))


CASES = [
    INS + "{ad: 1, sr: 2, ctrl: [{ctrl: 65, note: +0}, {wait: 2, ctrl: 17, note: C5}, {loop: 1}],"
    " pw: 2048, restart: r1}\n      restart:\n"
    "        r1: [{hold: 2, gate: 0, ad: 15, sr: 0}, {ctrl: 9}, end]\n",
    INS + "{filter: [{cut: '-12*min(1, max(0, φ - 5)) + 512', res: 15, route: +, mode: 16},"
    " {hold: 5}, {}, {loop: 2}]}\n",
    "      x:\n        x1: (F(N) < (v + F(N)) % 65536)*(v - 263) + 767*(v % 32768 < 1)\n"
    + INS
    + "{pw: 16*abs((φ - 32) % 128 - 64) + 512, freq: v - 139}\n",
    INS + "{ctrl: c1, filter: f1}\n      ctrl:\n        c1: [{ctrl: 129^8, note: G#5}, end]\n"
    "      filter:\n        f1: 1024\n"
    "      pw:\n        pw1: [{pw: none}, {run: c1}, {filter: none}, end]\n",
    INS + "{pw: 95*φ\n            + 296, restart: [{hold: 3, ctrl: ^8, gate: 0}, {},\n"
    "            end]}\n",
    INS + "{ad: 1}\n      phrase:\n"
    "        p2: [C4.i1!run:c1!ad:1!sr:2!ctrl:65!resfilt:15/1!vol:15!cut:x1!tempo:6/7!vtempo:8"
    "!freq:x1!legato!pw!filter*2, -!pw:none!filter:none,\n"
    "          off!cut:80, on!freq:none, B-1!freq:-139, C10!pw:256, -!pw:x1!cut:512]\n",
]


@pytest.mark.parametrize("defs", CASES)
def test_each_form_of_the_vocabulary_parses(defs):
    """Rows, instruments, programs, expressions, wraps and every command shape."""
    tree = parse(doc(defs))
    assert tree.data == "start"
    assert [str(t) for t in first(tree, "plays").scan_values(lambda v: True)] == ["p1"] * 3


def test_the_commands_are_one_chain_in_vocabulary_order():
    """An event's commands nest in the vocabulary's order, each with its arguments."""
    tree = parse(doc(CASES[-1]))
    event = first(first(tree, "phrase"), "event")
    assert [str(c) for c in event.children if isinstance(c, Token)] == ["C4", "i1", "2"]
    assert chain(event, "cmd_") == [
        ("cmd_run", ["c1"]),
        ("cmd_ad", ["1"]),
        ("cmd_sr", ["2"]),
        ("cmd_ctrl", ["65"]),
        ("cmd_resfilt", ["15", "1"]),
        ("cmd_vol", ["15"]),
        ("cmd_cut", ["x1"]),
        ("cmd_tempo", ["6", "7"]),
        ("cmd_vtempo", ["8"]),
        ("cmd_freq", ["x1"]),
    ]


def test_a_program_is_its_rows_in_order():
    """Each program row is a chain of its keys in the vocabulary's order."""
    tree = parse(doc(CASES[0]))
    rows = list(first(tree, "program").find_data("row_"))
    assert [chain(row, "row_") for row in rows] == [
        [("row_ctrl", ["65"]), ("row_note", ["+0"])],
        [("row_wait", ["2"]), ("row_ctrl", ["17"]), ("row_note", ["C5"])],
    ]
    assert str(first(tree, "program").children[-1]) == "1"


def test_the_header_forms_parse():
    """Block playroutine with constants and tables, clock, voices, a swing tempo, the init row."""
    head = (
        "clock: {cycles_per_tick: 17095, clock_hz: 1022727}\nvoices: 3\ntempo: [6, 7]\n"
        "init: [E2!pw:256!cut:x1!freq:-139!legato, -!pw:2048, -]\n"
    )
    tree = parse(doc("      ins:\n        i1: {ad: 1}\n", head, ending="  - end"))
    init = first(tree, "init")
    assert [str(e.children[0]) for e in init.children] == ["E2", "-", "-"]
    assert [chain(e, "cmd_") for e in init.children] == [
        [("cmd_pw", ["256"]), ("cmd_cut", ["x1"]), ("cmd_freq", ["-139"])],
        [("cmd_pw", ["2048"])],
        [],
    ]
    assert [str(t) for t in first(tree, "tempo").children] == ["6", "7"]
    block = (
        "unitracker: 1.20\nplayroutine:\n  ref: defmon\n  constants: {floor: 2, dbl: 0}\n"
        "  tables:\n    note_lo: {18: 922, 22: 967,\n      42: 3178}\n    por_lo: [1, 2, 3]\n"
        "meta: {title: T}\n"
    )
    tree = parse(
        doc("      ins:\n        i1: {ad: 1}\n", play="[p1, p1+5, ~]").replace(HEADER, block)
    )
    assert [str(t) for t in first(tree, "intmap").children] == [
        "18",
        "922",
        "22",
        "967",
        "42",
        "3178",
    ]
    assert [[str(t) for t in p.children] for p in first(tree, "plays").children] == [
        ["p1"],
        ["p1", "+5"],
        [],
    ]


@pytest.mark.parametrize(
    "text, where",
    [
        (doc(INS + "{sr: 2, ad: 1}\n"), "line 7"),
        (doc(INS + "{ctrl: [{note: C4, ctrl: 65}, end]}\n"), "line 7"),
        (doc("      ins:\n       i1: {ad: 1}\n"), "line 7"),
        (doc("      phrase:\n        p2: [C4!legato!freq:x1]\n"), "line 7"),
        (doc("      phrase:\n        p2: [C4 .i1]\n"), "line 7"),
        (doc(INS + "{pw: v+1}\n"), "line 7"),
        (doc("      vinit:\n        0: {pw: 256}\n"), "line 6"),
        (doc(INS + "{ad: 1}\n", ending="  - loop: 0"), "line 11"),
        (HEADER.replace("meta", "title") + "song:\n  - end\n", "line 3"),
    ],
)
def test_other_spellings_are_refused(text, where):
    """Key order, indentation, command order, spaces in an event, operator spacing, fixed records,
    the song's ending and the header keys each have one form."""
    with pytest.raises(CanonicalError, match=rf"{where} column \d+: "):
        parse(text)


def test_the_parser_is_built_once_from_the_packaged_grammar():
    """The grammar ships as package data and the parser is cached."""
    assert GRAMMAR.read_text(encoding="utf-8").startswith("// The canonical unitracker document")
    assert parser() is parser()
