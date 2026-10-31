"""Format 2.5: every register-driving cell takes bindings, the expression language's operators,
the call pattern of a frame, the events a program pauses on, and the song's filter cells."""

import re

import pytest

from unitracker_grammar import CanonicalError, GRAMMAR, cells, code, parse
from unitracker_grammar.code import CodeError, Call
from unitracker_grammar.document import (
    Code,
    Document,
    Event,
    Expr,
    Header,
    Instrument,
    Once,
    Program,
    Row,
    Section,
    SongRow,
    printed,
    read,
)
from unitracker_grammar.expand import core, expanded
from unitracker_grammar.expr import ExpressionError

NEW = ("ctrl", "ad", "sr", "res", "route", "mode", "vol")
SONG = " - play:[p1]\n - end\n"
MODS = "mod:\n m(d):v + d\n"


def doc(version: str, head: str = "", body: str = "", song: str = SONG) -> str:
    """A document of format ``version`` with header lines ``head``, definitions ``body`` (a
    phrase ``p1`` where it has none) and ``song``."""
    body = body if "phrase:" in body else body + "phrase:\n p1:[C4]\n"
    return f"unitracker:{version}\nmeta:{{title:T}}\n{head}{body}song:\n{song}"


def rows(*keys: str, version: str = "2.5") -> str:
    """A document whose instrument's control program has one row of ``keys``."""
    body = f"{MODS}ins:\n i1:{{ctrl:[{{{','.join(keys)}}},end]}}\n"
    return doc(version, body=body)


def events(*commands: str, version: str = "2.5") -> str:
    """A document whose phrase has one event with ``commands``."""
    return doc(version, body=f"{MODS}phrase:\n p1:[C4{''.join(commands)}]\n")


def refused_as(text: str, older: str):
    """``text`` at format 2.5 reads and prints as it is, and an older version line is refused."""
    assert printed(read(text)) == text and read(text).version == "2.5"
    with pytest.raises(CanonicalError, match="exactly where"):
        parse(text.replace("unitracker:2.5", f"unitracker:{older}"))


# ---- cells --------------------------------------------------------------------------------

BINDINGS = {
    "m(3)": Call("m", (3,)),
    "v + 4": Expr("v + 4"),
    "asm{lda v; rts}": Code.of("lda v\nrts"),
    "none": "none",
    "hold": "hold",
    "reset": "reset",
    "m(3)!": Once(Call("m", (3,))),
    "'v - 1'!": Once(Expr("v - 1")),
}


@pytest.mark.parametrize("cell", NEW)
@pytest.mark.parametrize("binding", BINDINGS)
def test_a_program_row_binds_or_stops_each_cell_as_pw_and_cut_are(cell, binding):
    text = rows(f"{cell}:{binding}")
    refused_as(text, "2.4")
    (row,) = read(text).records("ins")["i1"].get("ctrl").rows
    assert row.keys == ((cell, BINDINGS[binding]),)


@pytest.mark.parametrize("cell", NEW)
def test_a_cell_s_row_key_takes_a_slot_prefix_and_repeats(cell):
    text = rows(f"{cell}:m(2)", f"t.{cell}:none", f"{cell}:reset")
    refused_as(text, "2.3")
    (row,) = read(text).records("ins")["i1"].get("ctrl").rows
    assert [k for k, _ in row.keys] == [cell, f"t.{cell}", cell]
    assert row.keys[2][1] == "reset"


@pytest.mark.parametrize("cell", NEW)
@pytest.mark.parametrize(
    "binding", ["m(3)", "'v - 1'", "asm{lda v; rts}", "none", "hold", "reset", "m(3)!"]
)
def test_an_event_command_binds_or_stops_each_cell(cell, binding):
    text = events(f" {cell}:{binding}", f" t.{cell}:m(1)")
    refused_as(text, "2.4")
    (event,) = read(text).records("phrase")["p1"]
    assert [k for k, _ in event.commands] == [cell, f"t.{cell}"]


@pytest.mark.parametrize("field", ["ad", "sr"])
@pytest.mark.parametrize("binding", ["m(3)", "v + 4", "asm{lda v; rts}", "none", "m(3)!"])
def test_an_instrument_binds_ad_and_sr_and_ends_them_with_none(field, binding):
    text = doc("2.5", body=f"{MODS}ins:\n i1:{{{field}:{binding},t.{field}:m(2)}}\n")
    refused_as(text, "2.4")
    ins = read(text).records("ins")["i1"]
    assert [k for k, _ in ins.fields] == [field, f"t.{field}"]
    with pytest.raises(CanonicalError):
        parse(text.replace(binding, "hold", 1))


def test_the_plain_integer_forms_of_the_new_cells_are_format_2_3():
    keys = [f"{c}:{k}" for k, c in enumerate(NEW, 1)]
    text = doc("2.3", body=f"ins:\n i1:{{ad:9,sr:240,ctrl:[{{{','.join(keys)}}},end]}}\n")
    phrases = doc("2.3", body="phrase:\n p1:[C4 ad:1 sr:2 ctrl:3 res:4 route:5 mode:6 vol:7]\n")
    for plain in (text, phrases):
        assert printed(read(plain)) == plain and read(plain).version == "2.3"
    (row,) = read(text).records("ins")["i1"].get("ctrl").rows
    assert dict(row.keys) == {c: k for k, c in enumerate(NEW, 1)}


def test_a_program_template_reads_its_parameters_in_the_new_cells():
    text = doc(
        "2.3",
        body=(
            "ins:\n i1:{ctrl:arp(2,9)}\n"
            "ctrl:\n arp(a,b):[{ctrl:a,ad:b,sr:b,res:a,route:b,mode:a,vol:b},end]\n"
        ),
    )
    assert code.programs(parse(text))["arp"] == ("ctrl", ("a", "b"))
    (row,) = read(text).records("ctrl")["arp(a,b)"].rows
    assert dict(row.keys) == {"ctrl": "a", "ad": "b", "sr": "b", "res": "a", "route": "b"} | {
        "mode": "a",
        "vol": "b",
    }
    assert printed(read(text)) == text and read(text).version == "2.3"


@pytest.mark.parametrize(
    "row, version, error",
    [
        ("{ad:b + 1}", "2.5", "whole cell value"),
        ("{vol:min(b,3)}", "2.5", "whole cell value"),
        ("{vol:b}", "2.3", None),
        ("{vol:walk(b)}", "2.5", None),
    ],
)
def test_a_parameter_is_a_whole_cell_value_or_a_call_argument(row, version, error):
    text = doc(version, body=f"mod:\n walk(s):v + s\nctrl:\n arp(b):[{row},end]\n")
    if error is None:
        assert code.programs(parse(text))["arp"][1] == ("b",)
        assert printed(read(text)) == text and read(text).version == version
    else:
        with pytest.raises(CodeError, match=error):
            parse(text)


def test_a_parameter_outside_a_template_is_refused_in_the_new_cells():
    for text in (rows("ad:b", version="2.3"), events(" vol:b", version="2.3")):
        with pytest.raises((CodeError, CanonicalError, ExpressionError)):
            parse(text)
    with pytest.raises(CodeError, match="reads"):
        parse(doc("2.3", body="ctrl:\n c1:[{ctrl:b},end]\n"))


def test_an_inline_program_reads_no_parameter_in_the_new_cells():
    text = doc("2.3", body="ctrl:\n a(b):[{run:ctrl[{vol:b},end]},end]\n")
    with pytest.raises(CodeError, match="inline program reads no parameter"):
        parse(text)


def test_slots_and_state_name_the_new_cells():
    head = (
        "slots:{vol:{fade:{mod:m(1),hold:[step],reset:[note]},tail:{}},ad:{a:{mod:'v + 1'}}}\n"
        "state:{ctrl:{t:1},sr:{u:2},vol:{q:2}}\n"
    )
    text = doc("2.5", head, MODS)
    refused_as(text, "2.3")
    parsed = read(text).header
    assert [c for c, _ in parsed.slots] == ["vol", "ad"]
    assert [s.name for s in parsed.slot("vol")] == ["fade", "tail"]
    assert [s.name for s in parsed.slot("pw")] == ["pw"]
    assert code.state(parse(text)) == {"ctrl": (("t", 1),), "sr": (("u", 2),), "vol": (("q", 2),)}
    with pytest.raises(CanonicalError, match="declared twice"):
        parse(text.replace("sr:{u:2}", "sr:{t:2}"))
    with pytest.raises(CanonicalError):
        parse(text.replace("state:{ctrl:{t:1},sr", "state:{sr:{u:1},ctrl:{t:1},sr"))


def test_the_cells_masks_and_phases_are_the_grammar_s():
    grammar = GRAMMAR.read_text(encoding="utf-8")

    def alternatives(terminal: str) -> tuple:
        (line,) = re.findall(rf"^{terminal}: (.*(?:\n     .*)*)", grammar, re.M)
        return tuple(re.findall(r'"([a-z]+)"', line))

    assert alternatives("CELL") == cells.CELLS
    assert alternatives("PHASE") == cells.PHASES
    assert set(cells.MASKS) == set(cells.CELLS)
    assert [bin(cells.MASKS[c]).count("1") for c in cells.CELLS] == [
        16,
        12,
        11,
        8,
        8,
        8,
        4,
        4,
        4,
        4,
    ]
    assert cells.MASKS["mode"] == 0xF0 and cells.MASKS["res"] == cells.MASKS["vol"] == 0xF
    assert cells.PHASES[:4] + cells.PHASES[-1:] == ("events", "ctrl", "pulse", "filter", "read")
    assert cells.PHASES[4:-1] == tuple(cells.PHASE_OF[c] for c in cells.CELLS)
    assert set(cells.LATER_CELLS) == set(cells.CELLS) - {"freq", "pw", "cut"}
    assert set(cells.VOICE_CELLS) | set(cells.SONG_CELLS) == set(cells.CELLS)


def test_the_new_phases_are_named_in_the_order_line_and_default_after_the_cutoff():
    full = "order:[events,ctrl,pulse,filter,freq,pw,cut,ctl,ad,sr,res,route,mode,vol,read]\n"
    text = doc("2.5", full)
    refused_as(text, "2.3")
    assert read(text).header.order == tuple(cells.PHASES)
    swapped = doc("2.5", "order:[events,vol,ctrl,pulse,filter,freq,pw,cut,read]\n")
    refused_as(swapped, "2.4")
    old = doc("2.3", "order:[events,ctrl,pulse,filter,freq,pw,cut,read]\n")
    assert printed(read(old)) == old and read(old).version == "2.3"
    with pytest.raises(CanonicalError):
        parse(doc("2.5", "order:[events,ctl2]\n"))


# ---- calls --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line, calls",
    [
        ("calls:{frame:1}", (1, None)),
        ("calls:{frame:3}", (3, None)),
        ("calls:{frame:3,full:[1,0,0]}", (3, (1, 0, 0))),
        ("calls:{frame:2,full:[0,1,1,0,1]}", (2, (0, 1, 1, 0, 1))),
        ("calls:{frame:1,full:[1,0]}", (1, (1, 0))),
    ],
)
def test_the_calls_line_gives_the_calls_of_a_frame_and_which_are_full(line, calls):
    text = doc("2.5", f"lag:2\n{line}\nglobal:[cut]\n")
    refused_as(text, "2.3")
    assert read(text).header.calls == calls
    assert printed(read(text)).splitlines()[2:5] == ["lag:2", line, "global:[cut]"]


@pytest.mark.parametrize(
    "line",
    [
        "calls:{full:[1]}",
        "calls:{frame:0}",
        "calls:{frame:2,full:[]}",
        "calls:{frame:2,full:[1,2]}",
        "calls:{frame:2,full:[1,0],frame:2}",
        "calls:{frame:2, full:[1]}",
        "calls:{frame:-1}",
        "calls:{frame:2,full:[0,01]}",
    ],
)
def test_other_calls_lines_are_refused(line):
    with pytest.raises((CanonicalError, ValueError)):
        read(doc("2.5", f"{line}\n"))


@pytest.mark.parametrize(
    "calls",
    [(0, None), (-1, (1,)), (2, ()), (2, (0, 0)), (2, (1, 2)), (1.5, None), (2, (True, False, 7))],
)
def test_a_calls_model_needs_a_frame_and_a_pattern_with_a_full_call(calls):
    with pytest.raises(ValueError, match="calls"):
        Header(calls=calls)
    assert Header(calls=(2, [1, 0])).calls == (2, (1, 0))


def test_the_calls_line_sits_between_lag_and_global_and_after_regs():
    text = doc(
        "2.5", "regs:[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,15]\ncalls:{frame:2}\n"
    )
    assert read(text).header.regs[-1] == 15
    with pytest.raises(CanonicalError):
        parse(doc("2.5", "calls:{frame:2}\nlag:1\n"))


# ---- holds --------------------------------------------------------------------------------


def test_the_holds_line_lists_per_kind_and_layer_the_events_a_program_pauses_on():
    head = (
        "layers:{ctrl:[a,b],pw:[x]}\n"
        "holds:{pw:[read,note-1],ctrl:[step,last-2],b:[legato],x:[row,row.freq]}\n"
    )
    text = doc("2.5", head)
    refused_as(text, "2.4")
    assert read(text).header.holds == (
        ("pw", ("read", "note-1")),
        ("ctrl", ("step", "last-2")),
        ("b", ("legato",)),
        ("x", ("row", "row.freq")),
    )


def test_the_holds_line_without_layers_names_the_kinds_alone():
    text = doc("2.5", "holds:{filter:[read]}\n")
    refused_as(text, "2.3")
    assert read(text).header.holds == (("filter", ("read",)),)
    with pytest.raises(CanonicalError):
        parse(doc("2.5", "holds:{}\n"))
    with pytest.raises(CanonicalError):
        parse(doc("2.5", "holds:{pw:[]}\n"))
    with pytest.raises(CanonicalError):
        parse(doc("2.5", "holds:{pw:[bogus]}\n"))
    with pytest.raises(CanonicalError):
        parse(doc("2.5", "holds:{pw:[step-0]}\n"))


@pytest.mark.parametrize(
    "layers, holds, message",
    [
        (None, (("pw", ("read",)), ("pw", ("note",))), "name a key twice"),
        (None, (("b", ("read",)),), "neither a program kind nor a layer"),
        ({"ctrl": ["a", "b"]}, (("c", ("read",)),), "neither a program kind nor a layer"),
        ({"ctrl": ["pw"]}, (("pw", ("read",)),), "both a program kind and a layer"),
        (None, (("pw", ("bogus",)),), "no event"),
        (None, (("pw", ("row.nokey",)),), "no event"),
        (None, (("pw", ("step-0",)),), "no event"),
        (None, (("ctrl", ("row",)),), "the rows it applies"),
        (None, (("ctrl", ("row.ad",)),), "the rows it applies"),
        ({"ctrl": ["a", "b"]}, (("b", ("row.gate",)),), "the rows it applies"),
    ],
)
def test_a_holds_model_names_known_keys_and_events_and_pauses_no_control_program_on_its_rows(
    layers, holds, message
):
    with pytest.raises(ValueError, match=message):
        Header(layers=layers, holds=holds)


def test_a_holds_model_takes_row_events_for_the_other_kinds_and_layers():
    head = Header(
        layers={"ctrl": ["a"], "pw": ["x", "y"]},
        holds=[("pw", ["row", "row.ctrl"]), ("y", ["note-3"]), ("ctrl", ["read"])],
    )
    assert head.holds == (
        ("pw", ("row", "row.ctrl")),
        ("y", ("note-3",)),
        ("ctrl", ("read",)),
    )
    assert head.layers == (("ctrl", ("a",)), ("pw", ("x", "y")))


# ---- global -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cells_, version",
    [
        ("cut", "2.3"),
        ("cut,res", "2.5"),
        ("res", "2.5"),
        ("route,mode,vol", "2.5"),
        ("cut,res,route,mode,vol", "2.5"),
        ("mode", "2.5"),
        ("vol", "2.5"),
    ],
)
def test_the_song_cells_a_global_line_names_make_format_2_5_unless_only_the_cutoff(cells_, version):
    text = doc(version, f"global:[{cells_}]\n")
    assert printed(read(text)) == text and read(text).version == version
    assert read(text).header.global_cells == tuple(cells_.split(","))
    other = "2.4" if version == "2.3" else "2.3"
    with pytest.raises(CanonicalError, match="exactly where"):
        parse(text.replace(f"unitracker:{version}", f"unitracker:{other}"))


@pytest.mark.parametrize(
    "line",
    ["global:[]", "global:[res,cut]", "global:[cut,cut]", "global:[freq]", "global:[vol,res]"],
)
def test_the_global_line_names_song_cells_once_each_in_order(line):
    with pytest.raises(CanonicalError):
        parse(doc("2.5", f"{line}\n"))
    names = tuple(re.findall(r"[a-z]+", line[7:]))
    with pytest.raises(ValueError, match="global"):
        Header(global_cells=names)


# ---- the model ----------------------------------------------------------------------------


def test_a_model_is_format_2_5_where_it_binds_a_new_cell_and_prints_its_version():
    plain = Document(
        Header(meta={"title": "T"}),
        defs=[Section("phrase", [("p1", [Event("C4", None, {"vol": 5, "ad": "a"})])])],
        rows=[SongRow(["p1"])],
    )
    assert plain.version == "2.3"
    bound = {
        "vol": Expr("v - 1"),
        "t.ad": 3,
        "res": Call("m", (1,)),
        "route": Once(Call("m", (4,))),
        "mode": "none",
        "ctrl": "hold",
        "sr": Code.of("rts"),
    }
    for key, value in bound.items():
        event = Event("C4", None, {key: value})
        doc_ = Document(plain.header, defs=[Section("phrase", [("p1", [event])])], rows=plain.rows)
        assert doc_.version == "2.5", key
        assert printed(doc_).startswith("unitracker:2.5\n")
        assert read(printed(doc_)) == doc_
    row = Row({"ad": Expr("v ^ 1")})
    ins = Instrument({"ctrl": Program([row])})
    assert (
        Document(plain.header, defs=[Section("ins", [("i1", ins)])], rows=plain.rows).version
        == "2.5"
    )
    for cut in ("pw", "freq", "cut"):
        event = Event("C4", None, {cut: Expr("v + 1")})
        defs = [Section("phrase", [("p1", [event])])]
        assert Document(plain.header, defs=defs, rows=plain.rows).version == "2.3"


def test_a_header_makes_a_model_format_2_5():
    rows_ = [SongRow(["p1"])]
    defs = [Section("phrase", [("p1", [Event("C4")])])]
    for head in (
        Header(meta={"title": "T"}, calls=(2, None)),
        Header(meta={"title": "T"}, holds=[("pw", ["read"])]),
        Header(meta={"title": "T"}, global_cells=["cut", "vol"]),
        Header(meta={"title": "T"}, order=["ctl"]),
        Header(meta={"title": "T"}, state={"mode": [("q", 1)]}),
    ):
        assert Document(head, defs=defs, rows=rows_).version == "2.5"
    layered = Header(meta={"title": "T"}, layers={"ctrl": ["a"]})
    assert Document(layered, defs=defs, rows=rows_).version == "2.4"
    both = Header(meta={"title": "T"}, layers={"ctrl": ["a"]}, calls=(2, None))
    assert Document(both, defs=defs, rows=rows_).version == "2.5"


def test_layers_and_a_2_5_construct_are_format_2_5_together():
    text = doc("2.5", "layers:{ctrl:[a,b]}\ncalls:{frame:2}\n")
    refused_as(text, "2.4")


# ---- sugar --------------------------------------------------------------------------------


def test_an_instrument_template_binds_ad_and_sr_by_a_parameter_or_a_call():
    text = doc(
        "2.5",
        body=(
            f"{MODS}ins:\n arpi(a,b):{{ad:a,t.ad:m(a),sr:b}}\nphrase:\n"
            " p1:[C4.arpi(9,240),D.arpi(1,2) vol:m(1)]\n"
        ),
    )
    assert printed(read(text)) == text
    expanded_ = printed(expanded(read(text)))
    assert (
        " i1:{ad:9,t.ad:m(9),sr:240}\n" in expanded_ and " i2:{ad:1,t.ad:m(1),sr:2}\n" in expanded_
    )
    assert expanded_.startswith("unitracker:2.5\n")
    assert printed(read(expanded_)) == expanded_ and core(text) is not None


def test_the_core_of_a_2_5_document_keeps_its_constructs():
    text = doc(
        "2.5",
        "holds:{pw:[read]}\ncalls:{frame:2,full:[1,0]}\nglobal:[cut,vol]\n",
        f"{MODS}phrase:\n p1:[[C4 vol:m(1),D vol:none]x2]\n",
    )
    out = printed(expanded(read(text)))
    head = "holds:{pw:[read]}\ncalls:{frame:2,full:[1,0]}\nglobal:[cut,vol]\n"
    assert out.startswith(f"unitracker:2.5\nmeta:{{title:T}}\n{head}")
    assert out.count(" vol:") == 4 and parse(out) is not None
    assert printed(read(out)) == out


@pytest.mark.parametrize("cell", ["pw", "cut", "freq", *NEW])
def test_an_integer_has_no_once_form(cell):
    with pytest.raises(CanonicalError):
        parse(rows(f"{cell}:9!", version="2.3"))
    (row,) = read(rows(f"{cell}:9", version="2.3")).records("ins")["i1"].get("ctrl").rows
    assert row.keys == ((cell, 9),)


# ---- event --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "head",
    [
        "holds:{pw:[event,event-2]}\n",
        "holds:{ctrl:[step,event-1]}\n",
        "slots:{freq:{a:{hold:[event-1],reset:[event]}}}\n",
        "slots:{pw:{pulse:{hold:[event]}}}\n",
    ],
)
def test_the_event_hold_event_is_format_25_in_slots_and_holds(head):
    text = doc("2.5", head)
    refused_as(text, "2.4")
    assert printed(read(text)) == text


def test_the_event_hold_event_takes_an_offset_but_not_a_row_key_or_zero():
    for bad in ("event-0", "event.freq", "events"):
        with pytest.raises(CanonicalError):
            parse(doc("2.5", f"holds:{{pw:[{bad}]}}\n"))
    assert read(doc("2.5", "holds:{pw:[event-3]}\n")).header.holds == (("pw", ("event-3",)),)
