"""The canonical grammar: each form of the vocabulary has one spelling."""

import pytest
from lark import Token, Tree

from unitracker_grammar import (
    GRAMMAR,
    NTSC_HZ,
    PAL_HZ,
    CanonicalError,
    frequency,
    parse,
    parser,
    table,
)

HEADER = "unitracker: 1.20\nmeta: {title: T, author: A}\n"
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
    INS + "{ad: 1, sr: 2, mod: ramp}\n",
    INS + "{ad: 1, sr: 2, mod: ramp {step: 2, skip: [1, 3]}}\n",
    INS + "{ad: 1, mod: set {detune: 1, offset: -2}}\n",
    INS + "{ad: 1, sr: 2, freq: v - 3, mod: ramp {step: 2}}\n",
    INS + "{ad: 1, mod: set {detune: 1}}\n      phrase:\n"
    "        p2: [C4.i1!freq:-4!set step 4!set offset 1, -*3]\n",
    INS + "{ad: 1}\n      phrase:\n"
    "        p2: [C4.i1!run:c1!ad:1!sr:2!ctrl:65!resfilt:15/1!mode:16!vol:15!cut:x1!tempo:6/7"
    "!vtempo:8!freq:x1!legato!pw!filter*2, -!pw:none!filter:none,\n"
    "          off!cut:80, on!freq:none, B-1!freq:-139, C10!pw:256, -!pw:x1!cut:512]\n",
]


REFUSED = [
    (doc(INS + "{sr: 2, ad: 1}\n"), "line 6"),
    (doc(INS + "{ctrl: [{note: C4, ctrl: 65}, end]}\n"), "line 6"),
    (doc("      ins:\n       i1: {ad: 1}\n"), "line 6"),
    (doc("      phrase:\n        p2: [C4!legato!freq:x1]\n"), "line 6"),
    (doc("      phrase:\n        p2: [C4 .i1]\n"), "line 6"),
    (doc(INS + "{pw: v+1}\n"), "line 6"),
    (doc(INS + "{ad: 1, mod: ramp {}}\n"), "line 6"),
    (doc(INS + "{ad: 1, mod: 4}\n"), "line 6"),
    (doc(INS + "{ad: 1, mod: ramp {step 2}}\n"), "line 6"),
    (doc("      phrase:\n        p2: [C4.i1!set step]\n"), "line 6"),
    (doc("      vinit:\n        0: {pw: 256}\n"), "line 5"),
    (doc(INS + "{ad: 1}\n", ending="  - loop: 0"), "line 10"),
    (HEADER.replace("meta", "title") + "song:\n  - end\n", "line 2"),
    (
        HEADER.replace("meta", "playroutine: {ref: goattracker2}\nmeta") + "song:\n  - end\n",
        "line 2",
    ),
    (doc(INS + "{ad: 1}\n", "tables:\n  ftab: [1, 2]\n"), "line 4"),
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
        ("cmd_mode", ["16"]),
        ("cmd_vol", ["15"]),
        ("cmd_cut", ["x1"]),
        ("cmd_tempo", ["6", "7"]),
        ("cmd_vtempo", ["8"]),
        ("cmd_freq", ["x1"]),
        ("cmd_legato", ["!legato"]),
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


def test_a_modulator_is_its_shape_and_its_bag():
    """The instrument's ``mod:`` is its shape's name and its parameter bag, in the bag's order."""
    tree = parse(doc(INS + "{ad: 1, sr: 2, mod: ramp {step: 2, skip: [1, 3]}}\n"))
    fn = first(tree, "ins_fn")
    assert str(fn.children[0]) == "ramp"
    assert [str(v) for v in fn.scan_values(lambda v: True)] == [
        "ramp",
        "step",
        "2",
        "skip",
        "1",
        "3",
    ]
    assert [str(c) for c in first(tree, "ins_ad").children if isinstance(c, Token)] == ["1"]


def test_a_note_set_is_its_writes_in_order():
    """A note's ``!set`` writes name-value pairs in the order they come."""
    tree = parse(
        doc(
            INS + "{ad: 1, mod: set {detune: 1}}\n      phrase:\n"
            "        p2: [C4.i1!freq:-4!set step 4!set offset 1, -*3]\n"
        )
    )
    event = first(first(tree, "phrase"), "event")
    assert chain(event, "cmd_")[-2:] == [
        ("cmd_freq", ["-4"]),
        ("cmd_set", ["step", "4", "offset", "1"]),
    ]


def test_the_header_forms_parse():
    """Clock, voices, a swing tempo, the document's tables and the init row."""
    head = (
        "clock: {cycles_per_tick: 17095, clock_hz: 1022727}\nvoices: 3\ntempo: [6, 7]\n"
        "tables:\n  W: [1, 2, 3]\n  Por: [922, 967,\n    3178]\n"
        "init: [E2!pw:256!cut:x1!freq:-139!legato, -!pw:2048, -]\n"
    )
    tree = parse(doc("      ins:\n        i1: {ad: 1}\n", head, ending="  - end"))
    init = first(tree, "init")
    assert [str(e.children[0]) for e in init.children] == ["E2", "-", "-"]
    assert [chain(e, "cmd_") for e in init.children] == [
        [
            ("cmd_pw", ["256"]),
            ("cmd_cut", ["x1"]),
            ("cmd_freq", ["-139"]),
            ("cmd_legato", ["!legato"]),
        ],
        [("cmd_pw", ["2048"])],
        [],
    ]
    assert [str(t) for t in first(tree, "tempo").children] == ["6", "7"]
    tables = first(tree, "tables")
    assert [str(t) for t in tables.children if isinstance(t, Token)] == ["W", "Por"]
    assert [[str(t) for t in l.children] for l in tables.find_data("intlist")] == [
        ["1", "2", "3"],
        ["922", "967", "3178"],
    ]
    tree = parse(doc("      ins:\n        i1: {ad: 1}\n", play="[p1, p1+5, ~]"))
    assert [[str(t) for t in p.children] for p in first(tree, "plays").children] == [
        ["p1"],
        ["p1", "+5"],
        ["~"],
    ]


def test_the_hold_line_names_each_cell_s_events():
    """``hold`` maps each cell to the voice events its modulators hold on, ``-k`` earlier."""
    head = (
        "tempo: 3\nhold: {freq: [step-1, row],\n  pw: [read, note-1, last-1], cut: [legato-2],"
        " ctrl.freq: [note-1]}\n"
    )
    tree = parse(doc("", head))
    cells = [[str(t) for t in c.children] for c in first(tree, "hold").children]
    assert cells == [
        ["freq", "step-1", "row"],
        ["pw", "read", "note-1", "last-1"],
        ["cut", "legato-2"],
        ["ctrl.freq", "note-1"],
    ]


@pytest.mark.parametrize(
    "hold",
    [
        "{vol: [step]}",
        "{ctrl.vol: [step]}",
        "{pw.ctrl: [step]}",
        "{pw: [row-1]}",
        "{pw: [step-0]}",
        "{pw: [phrase]}",
        "{pw: []}",
        "{pw: [step,row]}",
    ],
)
def test_other_hold_spellings_are_refused(hold):
    """A cell other than freq, pw or cut (with or without ctrl.), an offset on row or of 0, an
    unknown event, an empty list and a missing space are refused."""
    with pytest.raises(CanonicalError):
        parse(doc("", f"hold: {hold}\n"))


@pytest.mark.parametrize("text, where", REFUSED)
def test_other_spellings_are_refused(text, where):
    """Key order, indentation, command order, spaces in an event, operator spacing, fixed records,
    the song's ending, the header keys, a player's name and a lower-case table each have one
    form or none."""
    with pytest.raises(CanonicalError, match=rf"{where} column \d+: "):
        parse(text)


@pytest.mark.parametrize(
    "case, column",
    list(zip(REFUSED, [21, 32, 1, 23, 16, 19, 32, 26, 36, 28, 1, 1, 1, 1, 3], strict=True)),
)
def test_a_refusal_is_at_its_place(case, column):
    """Each refused spelling is refused at the same line and column as before the operators and
    keywords became named terminals."""
    text, where = case
    with pytest.raises(CanonicalError, match=rf"^{where} column {column}: "):
        parse(text)


def test_the_operators_and_keywords_are_in_the_tree():
    """The operators, keywords and keep flags are tokens of the tree, and layout is not."""
    extra = [
        doc("      x:\n        x1: -(9 // 2)\n", play="[p1, ~, end]"),
        *(doc(INS + "{ctrl: [{route: " + r + "}, end]}\n") for r in ("+ 3", "'-'", "'- 3'")),
    ]
    trees = [parse(doc(d)) for d in CASES] + [parse(t) for t in extra]
    tokens = {(t.type, t.strip()) for tree in trees for t in tree.scan_values(lambda _: True)}
    assert {
        ("ADD", "+"),
        ("ADD", "-"),
        ("MUL", "*"),
        ("FLOORDIV", "//"),
        ("MOD", "%"),
        ("CMP", "<"),
        ("V", "v"),
        ("PHI", "φ"),
        ("N", "N"),
        ("F", "F("),
        ("ABS", "abs("),
        ("MIN", "min("),
        ("MAX", "max("),
        ("NEG", "-"),
        ("CONT", "~"),
        ("END", "end"),
        ("LOOP", "loop:"),
        ("NONE", "none"),
        ("FILTER_NONE", "!filter:none"),
        ("LEGATO", "!legato"),
        ("KEEP_PW", "!pw"),
        ("KEEP_FILTER", "!filter"),
        ("ROUTE_ADD", "+"),
        ("ROUTE_ADD_MASK", "+"),
        ("ROUTE_REMOVE", "'-'"),
        ("ROUTE_REMOVE_MASK", "'-"),
    } <= tokens
    assert not {t for t, _ in tokens} & {"_NL", "_LB", "_LC", "_SEP"}
    assert [[str(c) for c in p.children] for p in first(trees[-4], "plays").children] == [
        ["p1"],
        ["~"],
        ["end"],
    ]


def test_the_parser_is_built_once_from_the_packaged_grammar():
    """The grammar ships as package data and the parser is cached."""
    assert GRAMMAR.read_text(encoding="utf-8").startswith("// The canonical unitracker document")
    assert parser() is parser()


def test_the_note_table_is_equal_temperament_from_a4_in_words_that_fit():
    """A4 at PAL is 7493; an octave doubles the word within rounding; NTSC words are lower; the
    table stops where a word overflows and F(k) is 0 there and below C0."""
    assert frequency(57) == 7493
    assert frequency(57, NTSC_HZ) == 7218
    pal = table(PAL_HZ)
    assert pal[24] == frequency(24) and all(
        abs(pal[k + 12] - 2 * pal[k]) <= 1 for k in range(len(pal) - 12)
    )
    ntsc = table(NTSC_HZ)
    assert all(a < b for a, b in zip(ntsc, pal)) and len(ntsc) > len(pal)
    assert pal[-1] < 1 << 16 and frequency(len(pal)) == 0 and frequency(-1) == 0
    assert ntsc[:3] == [268, 284, 301]
