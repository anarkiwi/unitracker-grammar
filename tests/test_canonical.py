"""The canonical grammar: each form of the vocabulary has one spelling."""

import pytest
from lark import Token, Tree

from unitracker_grammar import expr
from unitracker_grammar.code import Statements, inline
from unitracker_grammar.document import printed, read
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

HEADER = "unitracker:2.3\nmeta:{title:T,author:A}\n"
INS = "ins:\n i1:"


def doc(
    top: str = "",
    phrases: str = "",
    play: str = "[p1,p1,p1]",
    ending: str = " - {loop:0}",
) -> str:
    """A document of the lines ``top`` between its meta and its song, its phrase section,
    phrase ``p1`` and ``phrases``, before ``top``'s init line, in its one canonical text where
    it is in the grammar."""
    head, init, tail = top.partition("init:")
    phrase = f"phrase:\n p1:[C4.i1,-*3]\n{phrases}"
    return canonical(f"{HEADER}{head}{phrase}{init}{tail}song:\n - play:{play}\n{ending}\n")


def canonical(text: str) -> str:
    """The one canonical text of a document's ``text``, or ``text`` outside the grammar."""
    try:
        return printed(read(text))
    except ValueError:
        return text


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


def keys(tree: Tree) -> list:
    """A section's children in order: each key token's text, each value's rule name."""
    return [str(c) if isinstance(c, Token) else c.data for c in tree.children]


WRAP = "(F(N) < (v + F(N)) % 65536)*(v - 263) + 767*(v % 32768 < 1)"
CASES = [
    ("restart:\n r1:[{hold:2,gate:0,ad:15,sr:0},{ctrl:9},end]\n" + INS)
    + "{ad:1,sr:2,ctrl:[{ctrl:65,note:+0},{wait:2,ctrl:17,note:C5},{loop:1}],"
    "pw:2048,restart:r1}\n",
    INS + "{filter:[{cut:'-12*min(1,max(0,phi - 5)) + 512',res:15,route_on:0,mode:16},"
    "{hold:5},{},{loop:2}]}\n",
    f"mod:\n wrap():{WRAP}\n" + INS + "{pw:16*abs((phi - 32) % 128 - 64) + 512,freq:v - 139}\n",
    INS + "{ctrl:c1,filter:f1}\nctrl:\n c1:[{ctrl:129,mask:8,note:g5},end]\n"
    "pw:\n pw1:[{pw:none},{run:c1},end]\nfilter:\n f1:1024\n",
    INS + "{pw:95*phi + 296,restart:[{hold:3,mask:8,gate:0},{},end]}\n",
]
COMMANDS = (
    " p2:[C4.i1 run:c1 ad:1 sr:2 ctrl:65 res:15 route:1 mode:16 vol:15 cut:wrap() tempo:6/7"
    " vtempo:8 freq:wrap() legato pw filter*2,- pw:none cut:none filter,- freq:hold,"
    "off cut:80,on freq:none,B-1 freq:-139,C10 pw:256,- pw:wrap() cut:512]\n"
)


@pytest.mark.parametrize("top, phrases", [(t, "") for t in CASES] + [(INS + "{ad:1}\n", COMMANDS)])
def test_each_form_of_the_vocabulary_parses(top, phrases):
    """Rows, instruments, programs, expressions and every command shape."""
    tree = parse(doc(top, phrases))
    assert tree.data == "start"
    assert [str(t) for t in first(tree, "plays").scan_values(lambda v: True)] == ["p1"] * 3


def test_the_commands_are_one_chain_in_vocabulary_order():
    """An event's commands nest in the vocabulary's order, each with its arguments."""
    tree = parse(doc(INS + "{ad:1}\n", COMMANDS))
    event = list(first(tree, "def_phrase").find_data("event"))[2]
    assert [str(c) for c in event.children if isinstance(c, Token)] == ["C4", "i1", "2"]
    assert chain(event, "cmd_") == [
        ("cmd_run", [" run:", "c1"]),
        ("cmd_ad", ["1"]),
        ("cmd_sr", ["2"]),
        ("cmd_ctrl", ["65"]),
        ("cmd_res", ["15"]),
        ("cmd_route", ["1"]),
        ("cmd_mode", ["16"]),
        ("cmd_vol", ["15"]),
        ("cmd_cut", [" cut:", "wrap()"]),
        ("cmd_tempo", ["6", "7"]),
        ("cmd_vtempo", ["8"]),
        ("cmd_freq", [" freq:", "wrap()"]),
        ("cmd_legato", [" legato"]),
    ]


def test_a_program_is_its_rows_in_order():
    """Each program row is a chain of its keys in the vocabulary's order."""
    tree = parse(doc(CASES[0]))
    program = first(first(tree, "def_ins"), "program")
    assert [chain(row, "row_") for row in program.find_data("row_")] == [
        [("row_ctrl", ["65"]), ("row_note", ["+0"])],
        [("row_wait", ["2"]), ("row_ctrl", ["17"]), ("row_note", ["C5"])],
    ]
    assert str(program.children[-1]) == "1"


@pytest.mark.parametrize("cell", ["freq", "pw", "cut"])
@pytest.mark.parametrize("stop", ["none", "hold"])
def test_each_modulated_cell_takes_none_and_hold_as_a_row_key_and_a_command(cell, stop):
    """``none`` and ``hold`` are one keyword each, the same for freq, pw and cut, in a program
    row and in a command."""
    tree = parse(doc(INS + f"{{ctrl:[{{{cell}:{stop}}},end]}}\n", f" p2:[C4.i1 {cell}:{stop}]\n"))
    row = first(first(tree, f"row_{cell}"), "cell_value")
    command = next(n for n in tree.find_data(f"cmd_{cell}") if isinstance(n.children[0], Token))
    assert [(t.type, str(t)) for t in row.children] == [(stop.upper(), stop)]
    assert [(t.type, str(t)) for t in command.children if isinstance(t, Token)] == [
        (f"CMD_{cell.upper()}", f" {cell}:"),
        (stop.upper(), stop),
    ]


def test_the_header_forms_parse():
    """Clock, voices, a swing tempo, the document's tables, the init row and transposes."""
    top = (
        "clock:{cycles_per_tick:17095,clock_hz:1022727}\nvoices:3\ntempo:[6,7]\n"
        "tables:\n W:[1,2,3]\n Por:[922,967,3178]\n" + INS + "{ad:1}\n"
        "init:[E2 pw:256 cut:walk(1) freq:-139 legato,- pw:2048,-]\n"
    )
    tree = parse(doc(top, ending=" - end"))
    init = first(tree, "init")
    assert [str(e.children[0]) for e in init.children] == ["E2", "-", "-"]
    assert [chain(e, "cmd_") for e in init.children] == [
        [
            ("cmd_pw", [" pw:", "256"]),
            ("cmd_cut", [" cut:", "walk(1)"]),
            ("cmd_freq", [" freq:", "-139"]),
            ("cmd_legato", [" legato"]),
        ],
        [("cmd_pw", [" pw:", "2048"])],
        [],
    ]
    assert [str(t) for t in first(tree, "tempo").children] == ["6", "7"]
    tables = first(tree, "tables")
    assert [str(t) for t in tables.children if isinstance(t, Token)] == ["W", "Por"]
    assert [[str(t) for t in l.children] for l in tables.find_data("intlist")] == [
        ["1", "2", "3"],
        ["922", "967", "3178"],
    ]
    tree = parse(doc(play="[p1,p1+5,~]"))
    assert [[str(t) for t in p.children] for p in first(tree, "plays").children] == [
        ["p1"],
        ["p1", "+5"],
        ["~"],
    ]


REFUSED = [
    (doc(INS + "{sr:2,ad:1}\n"), 4, 11),
    (doc(INS + "{ctrl:[{note:C4,ctrl:65},end]}\n"), 4, 21),
    (doc("ins:\n  i1:{ad:1}\n"), 4, 2),
    (doc(phrases=" p2:[C4 legato freq:1]\n"), 5, 15),
    (doc(phrases=" p2:[C4 .i1]\n"), 5, 8),
    (doc(INS + "{pw:v+1}\n"), 4, 10),
    (doc("vinit:\n 0:{pw:256}\n"), 3, 1),
    (doc(ending=" - loop:0"), 7, 4),
    (HEADER.replace("meta", "title") + "song:\n - end\n", 2, 1),
    (HEADER.replace("meta", "playroutine:{ref:goattracker2}\nmeta") + "song:\n - end\n", 2, 1),
    (doc("tables:\n ftab:[1,2]\n"), 4, 2),
]


@pytest.mark.parametrize("text, line, column", REFUSED)
def test_other_spellings_are_refused_at_their_place(text, line, column):
    """Key order, indentation, command order, spaces in an event, operator spacing, an unknown
    section, the song's ending, the header keys, a player's name and a lower-case table each
    have one form or none, refused where they part from it."""
    with pytest.raises(CanonicalError, match=rf"^line {line} column {column}:"):
        parse(text)


BASE = (
    "unitracker:2.3\nmeta:{title:T}\ntempo:3\nslots:{pw:{a:{mod:m()}}}\n"
    "mod:\n m():v + 1\n porta(s):v + s\n"
    "ins:\n i1:{ad:9,pw:m(),freq:porta(3)}\n"
    "ctrl:\n arp(a,b):[{ctrl:a,note:+b},{run:arp(a,b)},end]\n"
    "pw:\n pt(b):b\n"
    "phrase:\n p1:[C4.i1 run:arp(7,4) freq:+3,- cut:m()]\n"
    "song:\n - play:[p1]\n - end\n"
)


@pytest.mark.parametrize(
    "old, new",
    [
        ("unitracker:2.3", "unitracker:1.23"),
        ("unitracker:2.3", "unitracker:2.0"),
        ("unitracker:2.3", "unitracker:2"),
        ("tempo:3\n", "tempo:3\nhold:{freq:[step-1,row]}\n"),
        ("pw:\n pt(b)", "x:\n x1:v + 1\npw:\n pt(b)"),
        ("phrase:\n", "x:\n x1:v + 1\nphrase:\n"),
        (" freq:+3", " freq:x1"),
        ("freq:porta(3)}", "freq:porta {s:3}}"),
        ("freq:porta(3)}", "mod:ramp {step:2}}"),
        ("freq:porta(3)}", "mod:ramp}"),
        (" freq:+3", " freq:+3 set step 4"),
        ("- cut:m()", "- filter:none"),
        ("pt(b):b", "pt(b):[{pw:b},{filter:none},end]"),
        (" - play:[p1]", " - def:\n\t  ins:\n\t    i2:{ad:1}\n\tplay:[p1]"),
        (" - play:[p1]", " - def:\n\t  phrase:\n\t    p2:[C4]\n\tplay:[p1]"),
        ("phrase:\n p1", "mod:\n n():v\nphrase:\n p1"),
        ("m():v + 1", "m():v + φ"),
        (" freq:+3", " freq:+3 resfilt:1/2"),
        ("pt(b):b", "pt(b):[{pw:b},end]"),
        (" porta(s):v + s\n", " porta:v + 1\n"),
        ("{mod:m()}", "{mod:m}"),
        ("{run:arp(a,b)}", "{run:ctrl:arp(a,b)}"),
        (" run:arp(7,4)", " run:ctrl:arp(7,4)"),
        (" run:arp(7,4)", " run:pw:pt(9)"),
        ("ad:9", "ad:09"),
        (" freq:+3", " freq:+03"),
    ],
)
def test_the_constructs_of_earlier_formats_are_refused(old, new):
    """Any version but 2.1, the hold line, x sections and instances, parameter bags, instrument
    shapes, !set, !filter:none and a row's filter key, a song row's definitions, a section out
    of its order, a template keyed by its name or named as a slot default, a run's kind before a
    call, an integer with a leading zero, φ, !resfilt and a pulse program of one binding."""
    assert old in BASE and parse(BASE)
    with pytest.raises(CanonicalError):
        parse(BASE.replace(old, new))


def test_the_operators_and_keywords_are_in_the_tree():
    """The operators, keywords and keep flags are tokens of the tree, and layout is not."""
    extra = [
        doc("mod:\n neg():-(9 // 2)\n", play="[p1,~,end]"),
    ]
    trees = [parse(doc(INS + "{ad:1}\n", COMMANDS))] + [parse(doc(t)) for t in CASES]
    trees += [parse(t) for t in extra]
    tokens = {(t.type, t.strip()) for tree in trees for t in tree.scan_values(lambda _: True)}
    assert {
        ("ADD", "+"),
        ("ADD", "-"),
        ("MUL", "*"),
        ("FLOORDIV", "//"),
        ("MOD", "%"),
        ("CMP", "<"),
        ("V", "v"),
        ("PHI", "phi"),
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
        ("HOLD", "hold"),
        ("LEGATO", "legato"),
        ("KEEP_PW", "pw"),
        ("KEEP_FILTER", "filter"),
    } <= tokens
    assert not {t for t, _ in tokens} & {"_NL", "_LB", "_LC", "_SEP"}
    assert [[str(c) for c in p.children] for p in first(trees[-1], "plays").children] == [
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
    table stops where a word overflows and F(k) is 0 there; below C0 F(k) goes on halving an
    octave down until the word rounds to 0."""
    assert frequency(57) == 7493
    assert frequency(57, NTSC_HZ) == 7218
    pal = table(PAL_HZ)
    assert pal[24] == frequency(24) and all(
        abs(pal[k + 12] - 2 * pal[k]) <= 1 for k in range(len(pal) - 12)
    )
    ntsc = table(NTSC_HZ)
    assert all(a < b for a, b in zip(ntsc, pal)) and len(ntsc) > len(pal)
    assert pal[-1] < 1 << 16 and frequency(len(pal)) == 0
    assert frequency(-1) == 263 and frequency(-12) == 139 and frequency(-24) == 70
    low = [frequency(k) for k in range(-128, 0)]
    assert low.index(next(filter(None, low))) == 128 - 109 and all(low[19:])
    assert ntsc[:3] == [268, 284, 301]


SLOTS = (
    "slots:{freq:{wave:{mod:note(),reset:[row.note,row.freq]},tick:{hold:[step-1,row]}},"
    "pw:{pulse:{hold:[read,note-1,last-1]}},cut:{filter:{}}}\n"
)
TEMPLATES = (
    "tables:\n G:[1]\nmod:\n note():(phi < 1)*G[N % 128] + v*(phi >= 1)\n porta(s):v + s\n"
    " walk(d,abs_d):v*(1 - min(phi,abs_d)) + abs(d - n)\n"
)


def own(node: Tree) -> bool:
    """Whether a slot link sets its own key: a name or an event list among its children."""
    return node.data.startswith("slot_") and any(
        isinstance(c, Token) or c.data == "events" for c in node.children
    )


def slot_values(node: Tree) -> list[str]:
    """A slot link's own values: its name or its events."""
    return [
        str(t)
        for c in node.children
        if isinstance(c, Token) or c.data == "events"
        for t in ([c] if isinstance(c, Token) else c.children)
    ]


def test_the_slots_line_names_each_cell_s_slots_and_their_events():
    """``slots`` maps a cell to its slots in firing order, each with its default binding and the
    events it holds and resets on, each of them left out or not."""
    tree = parse(doc(SLOTS))
    assert [
        [str(s.children[0])]
        + [(n.data, slot_values(n)) for n in s.iter_subtrees_topdown() if own(n)]
        for c in first(tree, "slots").children
        for s in c.children[1:]
    ] == [
        ["wave", ("slot_mod", ["note()"]), ("slot_reset", ["row.note", "row.freq"])],
        ["tick", ("slot_hold", ["step-1", "row"])],
        ["pulse", ("slot_hold", ["read", "note-1", "last-1"])],
        ["filter"],
    ]
    assert [str(c.children[0]) for c in first(tree, "slots").children] == ["freq", "pw", "cut"]


@pytest.mark.parametrize(
    "top",
    [
        "slots:{vol:{a:{}}}\n",
        "slots:{ctrl.freq:{a:{}}}\n",
        "slots:{freq:{}}\n",
        "slots:{freq:[a]}\n",
        "slots:{freq:{Wave:{}}}\n",
        "slots:{freq:{a:{reset:[row],hold:[step]}}}\n",
        "slots:{freq:{a:{hold:[step],mod:m()}}}\n",
        *(
            f"slots:{{pw:{{a:{{hold:[{events}]}}}}}}\n"
            for events in ("", "row.note-1", "row.", "row-1", "step-0", "phrase", "step, row")
        ),
        "order:[read]\nslots:{freq:{a:{}}}\n",
    ],
)
def test_other_slots_spellings_are_refused(top):
    """A cell other than freq, pw or cut, an empty or listed cell, a name that is no NAME, a
    slot's keys out of order, an empty event list, an offset on row, row.KEY or of 0, an unknown
    event, a space after a comma and a slots line after the order line are refused."""
    with pytest.raises(CanonicalError):
        parse(doc(top))


def test_a_template_reads_named_parameters():
    """A ``mod`` record is keyed by its signature, its expression reading its lowercase
    parameters; a record's name is no parameter."""
    tree = parse(doc(SLOTS + TEMPLATES))
    mods = first(tree, "def_mod")
    assert keys(mods) == ["note()", "expr", "porta(s)", "expr", "walk(d,abs_d)", "expr"]
    assert {t.type for t in mods.children if isinstance(t, Token)} == {"SIGNATURE"}
    assert [str(t) for t in tree.scan_values(lambda v: v.type == "PARAM")] == ["s", "abs_d", "d"]
    assert {str(t) for t in tree.scan_values(lambda v: v.type == "EVENT_NOTE")} == {"n"}
    names = parse(doc(CASES[3])).scan_values(lambda v: v.type in ("FILTER", "CTRL", "PARAM"))
    assert sorted(str(t) for t in names) == ["c1", "c1", "c1", "f1", "f1"]


def test_a_slot_prefix_names_the_slot_a_row_field_or_command_binds():
    """A row key, an instrument field and a command of a modulated cell each take a slot prefix,
    a cell's keys may repeat, one per slot, and a row or field binds a call, an expression or a
    stop."""
    tree = parse(
        doc(
            SLOTS + TEMPLATES + INS + "{ctrl:[{pw:1,pulse.pw:porta(3),filter.cut:none,"
            "wave.freq:v + n,tick.freq:porta(-3)},{cut:v + 40,freq:hold},end],pw:pw1,"
            "filter:porta(1),freq:F(n),wave.freq:note(),tick.freq:none}\n",
            " p2:[C4.i1 pw:5 pulse.pw:none filter.cut:porta(1) freq:+3"
            " tick.freq:porta(2) wave.freq:hold legato,- pw:2 pw]\n",
        )
    )
    links = [
        (
            n.data,
            [str(t) for t in n.children if isinstance(t, Token)],
            [
                c.data
                for c in n.children
                if isinstance(c, Tree) and not c.data.startswith(n.data[:4])
            ],
        )
        for n in tree.iter_subtrees_topdown()
        if n.data.split("_")[-1] in ("pw", "cut", "filter", "freq")
        and n.data[:4] in ("row_", "ins_")
        and any(
            isinstance(c, Token) or c.data in ("cell_value", "modulation", "fexpr")
            for c in n.children
        )
    ]
    assert links == [
        ("row_pw", [], ["cell_value"]),
        ("row_pw", ["pulse."], ["cell_value"]),
        ("row_cut", ["filter."], ["cell_value"]),
        ("row_freq", ["wave."], ["cell_value"]),
        ("row_freq", ["tick."], ["cell_value"]),
        ("row_cut", [], ["cell_value"]),
        ("row_freq", [], ["cell_value"]),
        ("ins_pw", ["pw1"], []),
        ("ins_filter", [], ["modulation"]),
        ("ins_freq", [], ["fexpr"]),
        ("ins_freq", ["wave.", "note()"], []),
        ("ins_freq", ["tick.", "none"], []),
    ]
    events = list(first(tree, "def_phrase").find_data("event"))
    assert chain(events[2], "cmd_") == [
        ("cmd_pw", [" pw:", "5"]),
        ("cmd_pw", [" pulse.pw:", "none"]),
        ("cmd_cut", [" filter.cut:", "porta(1)"]),
        ("cmd_freq", [" freq:", "+3"]),
        ("cmd_freq", [" tick.freq:", "porta(2)"]),
        ("cmd_freq", [" wave.freq:", "hold"]),
        ("cmd_legato", [" legato"]),
    ]
    assert [str(t) for t in events[3].scan_values(lambda _: True)] == ["-", " pw:", "2", " pw"]


@pytest.mark.parametrize(
    "top, phrases",
    [
        (INS + "{ctrl:[{a.ad:1},end]}\n", ""),
        (INS + "{ctrl:[{a. pw:1},end]}\n", ""),
        (INS + "{ctrl:[{freq:1,pw:2},end]}\n", ""),
        (INS + "{a.ad:1}\n", ""),
        ("", " p2:[C4 a.tempo:3]\n"),
        ("", " p2:[C4 a.pw]\n"),
        ("", " p2:[C4 pw:porta]\n"),
        ("mod:\n Porta(s):v\n", ""),
        ("mod:\n porta():pw1 + v\n", ""),
    ],
)
def test_a_slot_prefix_is_where_a_cell_is_bound_alone(top, phrases):
    """A prefix on another key or command, a space after it, a cell's key out of the vocabulary
    order, a prefixed keep flag, a template's bare name in a command, a template name that is no
    NAME and a record's name as a parameter are refused."""
    with pytest.raises(CanonicalError):
        parse(doc(SLOTS + top, phrases))


ORDER = "order:[events,ctrl,pulse,filter,freq,pw,cut,read]\n"


def test_the_order_line_names_the_phases_of_a_tick_after_the_slots_line():
    tree = parse(doc(SLOTS + ORDER))
    assert [str(t) for t in first(tree, "order").children] == [
        "events",
        "ctrl",
        "pulse",
        "filter",
        "freq",
        "pw",
        "cut",
        "read",
    ]
    assert first(parse(doc("order:[read]\n")), "order")


@pytest.mark.parametrize(
    "top",
    [ORDER + SLOTS, "order:[]\n", "order:[events,fetch]\n", "order:[events, ctrl]\n"],
)
def test_other_order_spellings_are_refused(top):
    """An order line before the slots line, an empty list, an unknown phase and a space after a
    comma are refused."""
    with pytest.raises(CanonicalError):
        parse(doc(top))


STATE = "state:{freq:{t:1},pw:{r:1,q:2},cut:{k:2}}\n"


def test_the_state_line_names_each_cell_s_variables_after_the_order_line():
    tree = parse(doc(ORDER + STATE + "tables:\n G:[1]\n"))
    assert [
        (n.data, [str(t) for t in n.children[0].scan_values(lambda _: True)])
        for n in first(tree, "state").iter_subtrees_topdown()
        if n.data.startswith("state_") and isinstance(n.children[0], Tree)
        if n.children[0].data == "state_vars"
    ] == [
        ("state_freq", ["t", "1"]),
        ("state_pw", ["r", "1", "q", "2"]),
        ("state_cut", ["k", "2"]),
    ]
    assert first(parse(doc("state:{cut:{k:1}}\n")), "state")


@pytest.mark.parametrize(
    "top",
    [
        STATE + ORDER,
        "state:{}\n",
        "state:{freq:{}}\n",
        "state:{pw:{r:1},freq:{t:1}}\n",
        "state:{vol:{t:1}}\n",
        "state:{freq:{t:3}}\n",
        "state:{freq:{t:12}}\n",
        "state:{freq:{t:0}}\n",
        "state:{freq:{T:1}}\n",
        "state: {freq:{t:1}}\n",
        *(f"state:{{freq:{{{name}:1}}}}\n" for name in ("v", "phi", "nn", "ne", "a", "x", "y")),
        "tables:\n G:[1]\n" + STATE,
    ],
)
def test_other_state_spellings_are_refused(top):
    """A state line before the order line or after the tables, an empty cell or line, cells out
    of order, a cell that is none, a size other than 1 or 2, a name that is no NAME or a reserved
    symbol and a space after a colon are refused."""
    with pytest.raises(CanonicalError):
        parse(doc(top))


MODS = (
    "tables:\n G:[1]\nmod:\n note():(phi < 1)*F(N) + v*(phi >= 1)\n porta(s,d):v + s - d\n"
    " vib(c):|\n\tlda t\n\tbmi up\n\tcmp #c\n\tadc #>c\n\tsta G.lo+3,x\n"
    "\tlda F.hi,x\n\tup:\n\trts\n"
)


def test_the_mod_section_holds_signed_templates_after_the_tables():
    """Its records are at one space, each keyed by a signature, an expression or a code block of
    statements each after a tab: the tree is a ``def_mod`` of signature tokens each before its
    ``expr`` or ``code``."""
    tree = parse(doc(STATE + MODS + "init:[C4]\n"))
    mods = first(tree, "def_mod")
    assert keys(mods) == ["note()", "expr", "porta(s,d)", "expr", "vib(c)", "code"]
    assert {t.type for t in mods.children if isinstance(t, Token)} == {"SIGNATURE"}
    assert [
        (n.data, [str(t) for t in n.scan_values(lambda _: True)])
        for n in first(tree, "code").children
    ] == [
        ("code_op", ["lda", "t"]),
        ("code_op", ["bmi", "up"]),
        ("code_op", ["cmp", "c"]),
        ("code_op", ["adc", ">", "c"]),
        ("code_op", ["sta", "G.lo", "+3", ",x"]),
        ("code_op", ["lda", "F.hi", ",x"]),
        ("code_label", ["up"]),
        ("code_op", ["rts"]),
    ]


@pytest.mark.parametrize(
    "top",
    [
        MODS.replace("\tup:", " up:"),
        MODS.replace("\trts", "      rts"),
        MODS.replace("\tup:", "          up:"),
        MODS.replace("vib(c):|", "vib(c):| "),
        MODS.replace("vib(c):|\n", "vib(c):|\n\n"),
        MODS.replace("#c", "#$c"),
        MODS.replace(" note()", "\tnote()"),
        MODS.replace("porta(s,d)", "porta(s, d)"),
        MODS.replace("porta(s,d)", "porta(n,d)"),
        MODS.replace("porta(s,d)", "porta( )"),
        MODS.replace("porta(s,d)", "Porta(s,d)"),
        "mod:\n vib():|\n",
        "mod:\n",
        "ctrl:\n c1:|\n\trts\n",
        "mod:\n porta(s):v + s\n" + STATE,
        "mod:\n porta(s):v + s\ntables:\n G:[1]\n",
        "init:[C4]\nmod:\n porta(s):v + s\n",
    ],
)
def test_other_mod_spellings_are_refused(top):
    """A statement, label or record at another indentation, a space after ``|``, a blank line, a
    hex integer, a parameter list spaced otherwise, a code symbol or a name that is no NAME, an
    empty block or section, code in a program section and the section out of its place."""
    with pytest.raises(CanonicalError):
        parse(doc(top))


def test_a_call_binds_a_cell_wherever_a_template_did():
    """A row key, an instrument field, a pw or filter record, a command and a slot's default
    each take a CALL token: the name, then its integer arguments without spaces; ``abs(3)`` is
    the expression."""
    tree = parse(
        doc(
            "slots:{freq:{base:{mod:note()},wob:{},tick:{}}}\n"
            + INS
            + "{ctrl:[{pw:walk(-2),tick.freq:vib(0,4,32)},end],pw:walk(1),"
            "filter:walk(0),freq:abs(3),wob.freq:vib(1,+2,3)}\npw:\n pw1:walk(5)\n",
            " p2:[C4.i1 pw:walk(3) cut:walk(1) wob.freq:vib(0,-4,5) freq:note()]\n",
        )
    )
    calls = [str(t) for t in tree.scan_values(lambda v: v.type == "CALL")]
    assert calls == [
        "note()",
        "walk(-2)",
        "vib(0,4,32)",
        "walk(1)",
        "walk(0)",
        "vib(1,+2,3)",
        "walk(5)",
        "walk(3)",
        "walk(1)",
        "vib(0,-4,5)",
        "note()",
    ]
    assert [str(t) for t in tree.scan_values(lambda v: v.type == "ABS")] == ["abs("]


@pytest.mark.parametrize(
    "top, phrases",
    [
        (INS + "{pw:walk(1, 2)}\n", ""),
        (INS + "{pw:walk(1,)}\n", ""),
        (INS + "{pw:walk (1)}\n", ""),
        (INS + "{pw:Walk(1)}\n", ""),
        ("", " p2:[C4 pw:walk(1, 2)]\n"),
        ("", " p2:[C4 ad:walk(1)]\n"),
    ],
)
def test_other_call_spellings_are_refused(top, phrases):
    """A space in or before the arguments, a trailing comma, a name that is no NAME and a call
    where no cell is bound."""
    with pytest.raises(CanonicalError):
        parse(doc(top, phrases))


INLINE = canonical(
    "unitracker:2.3\nmeta:{title:T}\ntables:\n T:[1]\n"
    "ins:\n i1:{ctrl:[{ctrl:65,run:pw[{pw:5},end]},end],"
    "pw:asm{lda v; up:; adc #1; sta v; bne up; rts},freq:asm{rts}}\n"
    "init:[C4.{ad:1} pw:'v + 1']\nsong:\n"
    " - play:[[C4.{ad:9,ctrl:[{ctrl:65},end]} run:ctrl[{ctrl:64},{loop:0}]"
    " pw:asm{lda T.lo+3,x; sta v; rts} cut:'min(3,v) + 1' freq:'F(N) + 2'*2,"
    "- run:filter[{cut:7},end]]+2]\n"
    " - play:[[C4.i1 tick.freq:'2*v'*3]]\n - end\n"
)


def test_a_definition_stands_inline_where_its_name_does():
    """A program after its kind in a row's run: and a run command, an instrument after an
    event's note, a phrase with its transpose in a play entry, an anonymous code body wherever a
    cell is bound, and a quoted expression in a command and a slot's default."""
    tree = parse(INLINE)
    assert [str(n.children[0]) for n in tree.find_data("run_program")] == ["pw", "ctrl", "filter"]
    assert len(list(tree.find_data("instrument"))) == 3
    plays = list(tree.find_data("play"))
    assert [p.children[0].data for p in plays] == ["phrase", "phrase"]
    assert [str(t) for t in plays[0].children[1:]] == ["+2"]
    asm = [Statements().transform(n) for n in tree.find_data("asm")]
    assert sorted(inline(a) for a in asm) == [
        "asm{lda T.lo+3,x; sta v; rts}",
        "asm{lda v; up:; adc #1; sta v; bne up; rts}",
        "asm{rts}",
    ]
    commands = [
        expr.printed(expr.Nodes().transform(f.children[0]))
        for n in tree.iter_subtrees()
        if n.data.startswith("cmd_")
        for f in n.children
        if isinstance(f, Tree) and f.data == "fexpr"
    ]
    assert sorted(commands) == ["2*v", "F(N) + 2", "min(3,v) + 1", "v + 1"]
    slots = parse(doc("slots:{pw:{a:{mod:asm{rts}},b:{mod:'v + 1',hold:[step]}}}\n"))
    assert [c.data for n in slots.find_data("slot_mod") for c in n.children[:1]] == [
        "asm",
        "fexpr",
    ]


@pytest.mark.parametrize(
    "text",
    [
        INLINE.replace("run:ctrl[", "run:["),
        INLINE.replace("run:pw[", "run:pw ["),
        INLINE.replace("run:pw[", "run:c[", 1),
        INLINE.replace(" pw:'v + 1'", " pw:v + 1"),
        INLINE.replace(" freq:'F(N) + 2'", " freq:F(N)"),
        INLINE.replace("asm{rts}", "asm{}"),
        INLINE.replace("asm{rts}", "asm {rts}"),
        INLINE.replace("asm{rts}", "asm{clc;rts}"),
        INLINE.replace("asm{rts}", "asm{clc;  rts}"),
        INLINE.replace("]+2]", "] +2]"),
        INLINE.replace("C4.{ad:9,", "C4.{ad: 9,"),
        doc("slots:{pw:{a:{mod:v + 1}}}\n"),
    ],
)
def test_other_inline_spellings_are_refused(text):
    """A program without its kind or spaced from it, an unquoted expression in a command or a
    slot's default, an empty or spaced code body, a statement separator other than ``; ``, a
    spaced transpose and an instrument outside the instrument spelling."""
    with pytest.raises(CanonicalError):
        parse(text)


PROGRAMS = (
    "unitracker:2.3\nmeta:{title:T}\nmod:\n walk(s):v + s\n"
    "restart:\n hr(h,ad,sr):[{hold:h,gate:0,ad:ad,sr:sr},end]\n"
    "ins:\n i1:{ad:9,ctrl:arp(7,-4),pw:pt(3),filter:fl(5),restart:hr(2,9,220)}\n"
    "ctrl:\n arp(a,b):[{ctrl:a,note:+a},{wait:a,gate:b,note:-b,"
    "run:pt(b)},{run:fl(a)},{loop:0}]\n"
    " c1:[{ctrl:129,mask:8,route:3,freq:v + 1},end]\n"
    "pw:\n pt(b):[{pw:walk(b)},{pw:b,res:b,route:b,mode:b,vol:b},end]\n"
    " pw1:pt(4)\nfilter:\n fl(c):c\n"
    "phrase:\n p1:[C4.i1 run:arp(1,2),- run:c1,D.{ctrl:arp(0,0)}]\n"
    "song:\n - play:[p1]\n - end\n"
)


def test_a_program_record_may_be_a_template_whose_rows_read_its_parameters():
    """Each program kind's record may be keyed by a signature; a row reads a parameter where it
    takes an integer, as a relative note's +p or -p, as a cell value and as a call's argument,
    and a call binds a template wherever a program name stands, in run: and a run command."""
    tree = parse(PROGRAMS)
    sigs = [
        (s.data, str(t))
        for s in tree.children
        if isinstance(s, Tree) and s.data != "def_mod"
        for t in s.children
        if isinstance(t, Token) and t.type == "SIGNATURE"
    ]
    assert sigs == [
        ("def_restart", "hr(h,ad,sr)"),
        ("def_ctrl", "arp(a,b)"),
        ("def_pw", "pt(b)"),
        ("def_filter", "fl(c)"),
    ]
    reads = [
        (n.data, str(t))
        for n in tree.iter_subtrees_topdown()
        if n.data != "factor"
        for t in n.children
        if isinstance(t, Token) and t.type in ("PARAM", "REL_PARAM")
    ]
    assert reads[:6] == [
        ("row_hold", "h"),
        ("row_ad", "ad"),
        ("row_sr", "sr"),
        ("row_ctrl", "a"),
        ("note_value", "+a"),
        ("row_wait", "a"),
    ]
    assert [d for d, _ in reads[6:]] == [
        "row_gate",
        "note_value",
        "row_res",
        "row_route",
        "row_mode",
        "row_vol",
    ]
    runs = [
        (n.data, t.type, str(t))
        for n in tree.iter_subtrees_topdown()
        if n.data in ("row_run", "cmd_run")
        for t in n.children
        if isinstance(t, Token)
    ]
    assert runs == [
        ("row_run", "CALL", "pt(b)"),
        ("row_run", "CALL", "fl(a)"),
        ("cmd_run", "CMD_RUN", " run:"),
        ("cmd_run", "CALL", "arp(1,2)"),
        ("cmd_run", "CMD_RUN", " run:"),
        ("cmd_run", "CTRL", "c1"),
    ]


@pytest.mark.parametrize(
    "old, new",
    [
        ("arp(a,b):[", "arp(a, b):["),
        ("arp(a,b):[", "arp(v,b):["),
        ("arp(a,b):[", "arp(a,n):["),
        ("fl(c):c", "fl(none):none"),
        ("fl(c):c", "f2(c):c"),
        ("fl(c):c", "fl(c1):c1"),
        ("note:+a", "note:+ a"),
        ("note:+a", "note:a"),
        ("{loop:0}", "{loop:a}"),
        ("route:3", "route:+a"),
        ("ctrl:129,mask:8", "ctrl:129^8"),
        ("mask:8,route:3", "mask:8,route:'-'"),
        ("run:pt(b)", "run:pt (b)"),
        (" run:arp(1,2)", " run:arp(1, 2)"),
        ("pw:pt(3)", "pw:pt(3, 4)"),
        ("arp(7,-4)", "arp(7, -4)"),
    ],
)
def test_other_program_template_spellings_are_refused(old, new):
    """A signature's parameters separated by ", " and none a name a cell value means otherwise
    (v, n, none, hold) nor a record's; a relative note's sign before the name; a loop row, a
    route's sign and the earlier control mask and route forms; a run spaced from its call; a
    call spaced."""
    assert old in PROGRAMS
    with pytest.raises(CanonicalError):
        parse(PROGRAMS.replace(old, new))


def test_the_definitions_are_top_level_sections_after_the_templates():
    """restart, ins, ctrl, pw, filter and phrase sections, each optional and in that order,
    stand after the mod section and before init, records at one space, each a ``def_KIND`` tree;
    a song row holds its play entries alone."""
    tree = parse(PROGRAMS.replace("song:", "init:[C4.i1]\nsong:"))
    top = [c.data for c in tree.children if isinstance(c, Tree) and c.data.startswith("def_")]
    assert top == [
        "def_mod",
        "def_restart",
        "def_ins",
        "def_ctrl",
        "def_pw",
        "def_filter",
        "def_phrase",
    ]
    assert [t.type for t in first(tree, "def_ins").children if isinstance(t, Token)] == ["INS"]
    rows = [s.data for r in tree.find_data("row") for s in r.children if isinstance(s, Tree)]
    assert rows == ["plays"]
    assert keys(first(tree, "def_phrase")) == ["p1", "phrase"]
    undefined = PROGRAMS.replace("restart:\n hr(h,ad,sr):[{hold:h,gate:0,ad:ad,sr:sr},end]\n", "")
    assert parse(undefined.replace("restart:hr(", "restart:rs("))


@pytest.mark.parametrize(
    "old, new",
    [
        ("pw:\n pt(b)", "pw:\n\tpt(b)"),
        ("ins:\n i1:{", "ins:\n\t    i1:{"),
        ("restart:\n", "filter:\n fl(c):c\nrestart:\n"),
        ("ins:\n", "mod:\n walk(s):v + s\nins:\n"),
        ("song:", "ins:\n i2:{ad:1}\nsong:"),
        ("phrase:\n p1", "phrase:\n\tp1"),
        ("ins:\n", "phrase:\n p0:[C4]\nins:\n"),
    ],
)
def test_other_top_level_definition_spellings_are_refused(old, new):
    """Records at other than 2 spaces and a section out of its order (filter first, mod, ins
    or phrase after another)."""
    text = PROGRAMS.replace(old, new, 1)
    text = text.replace("filter:\n fl(c):c\nsong:", "song:") if "restart" in new else text
    text = text.replace("mod:\n walk(s):v + s\nrestart:", "restart:") if "mod" in new else text
    with pytest.raises(CanonicalError):
        parse(text)


def test_the_note_table_rounds_to_the_nearest_word_or_down():
    """``round`` (the default) and ``floor`` differ where the fraction is a half or more, and
    the table stops at the same overflow."""
    exact = [440 * 2 ** ((k - 57) / 12) * 2**24 / 985240 for k in range(95)]
    assert table(985240, "floor") == [int(x) for x in exact]
    assert table(985240) == [round(x) for x in exact]
    assert frequency(57, 985240, "floor") == 7492 and frequency(57, 985240) == 7493
    assert frequency(-98, rounding="floor") == 0 == frequency(95, 985240, "floor")
    assert frequency(-97, rounding="floor") == 1 and frequency(-1, rounding="floor") == 262


@pytest.mark.parametrize(
    "line, clock",
    [
        (
            "clock:{cycles_per_tick:19656,clock_hz:985240,rounding:floor}\n",
            (19656, 985240, "floor"),
        ),
        ("clock:{cycles_per_tick:19656,clock_hz:985240}\n", (19656, 985240)),
    ],
)
def test_the_clock_line_names_floor_rounding_and_leaves_round_out(line, clock):
    text = doc(line)
    assert read(text).header.clock == clock and printed(read(text)) == text
    assert line in text


def test_round_rounding_is_left_out_and_another_is_refused():
    from unitracker_grammar.document import Header  # pylint: disable=import-outside-toplevel

    assert Header(clock=(1, 2, "round")).clock == (1, 2)
    with pytest.raises(ValueError):
        Header(clock=(1, 2, "ceil"))
    with pytest.raises(CanonicalError):
        parse(doc("clock:{cycles_per_tick:1,clock_hz:2,rounding:round}\n"))
