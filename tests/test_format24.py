"""Format 2.4: layers (the header line, a layer's prefix on an instrument's program field and on
a run) and voice orderlists, read and printed in their one text and expanded."""

import pytest

from unitracker_grammar import CanonicalError, parse
from unitracker_grammar.document import (
    Def,
    Document,
    Event,
    Header,
    Instrument,
    Program,
    Play,
    Section,
    SongRow,
    Voice,
    first_use,
    printed,
    read,
    replace,
    top_level,
)
from unitracker_grammar.expand import expanded

LAYERED = (
    "unitracker:2.4\n"
    "meta:{title:T}\n"
    "voices:1\n"
    "slots:{pw:{sw:{}}}\n"
    "layers:{ctrl:[a,b],filter:[x,y]}\n"
    "ins:\n"
    " i1:{ad:9,ctrl:c1,b.ctrl:c2,y.filter:f1}\n"
    "ctrl:\n"
    " c1:[{ctrl:65,b.run:c2,b.run:arp(3),run:c1},end]\n"
    " c2:[{note:+12},{note:+0},{loop:0}]\n"
    " arp(a):[{note:+a},end]\n"
    "filter:\n"
    " f1:800\n"
    "phrase:\n"
    " p1:[C4.i1 b.run:c2 run:c1 b.run:none,D b.run:ctrl[{note:+7},end] sw.pw:9]\n"
    "song:\n"
    " - play:[p1]\n"
    " - end\n"
)


def test_a_layered_document_reads_and_prints_its_one_text():
    doc = read(LAYERED)
    assert printed(doc) == LAYERED
    assert doc.header.layers == (("ctrl", ("a", "b")), ("filter", ("x", "y")))
    assert doc.version == "2.4"
    assert doc.records("ins")["i1"].fields[1:3] == (("ctrl", "c1"), ("b.ctrl", "c2"))
    first = doc.records("phrase")["p1"][0]
    assert first.commands == (("b.run", "c2"), ("run", "c1"), ("b.run", "none"))
    keys = doc.records("ctrl")["c1"].rows[0].keys
    assert [k for k, _ in keys] == ["ctrl", "b.run", "b.run", "run"]


def test_a_layer_prefixed_definition_moves_to_its_section_and_back():
    used = LAYERED.replace(" c2:[{note:+12},{note:+0},{loop:0}]\n", "").replace(
        "b.ctrl:c2,", "b.ctrl:c2=[{note:+12},{note:+0},{loop:0}],"
    )
    assert printed(read(used)) == used
    sections = top_level(read(used))
    assert sections.records("ctrl")["c2"] == read(LAYERED).records("ctrl")["c2"]
    assert "b.run:c2=[{note:+12},{note:+0},{loop:0}]" in printed(first_use(sections))


def test_a_layered_document_expands_with_its_layers():
    assert printed(expanded(read(LAYERED))).startswith("unitracker:2.4\n")


def test_the_version_is_2_4_exactly_where_layers_are_declared():
    with pytest.raises(CanonicalError, match="exactly where"):
        parse(LAYERED.replace("2.4", "2.3"))
    without = LAYERED.replace("layers:{ctrl:[a,b],filter:[x,y]}\n", "")
    with pytest.raises(CanonicalError, match="exactly where"):
        parse(without)
    with pytest.raises(CanonicalError):
        parse(LAYERED.replace("2.4", "2.5"))


def test_a_header_prints_its_layers_in_kind_order_and_its_version():
    head = Header(meta={"title": "T"}, layers={"filter": ["x"], "ctrl": ["a", "b"]})
    assert head.layers == (("ctrl", ("a", "b")), ("filter", ("x",)))
    doc = Document(
        head,
        defs=[Section("ins", [("i1", Instrument({"b.ctrl": Program([{"sr": 0}])}))])],
        rows=[SongRow([[Event("C4", "i1", {"b.run": Def("c1", Program([{"ad": 1}]))})]])],
    )
    text = printed(doc)
    assert text.startswith("unitracker:2.4\nmeta:{title:T}\nlayers:{ctrl:[a,b],filter:[x]}\n")
    assert " i1:{b.ctrl:[{sr:0},end]}\n" in text and "C4.i1 b.run:c1=[{ad:1},end]" in text
    assert read(text) == doc
    assert replace(doc, header=Header(meta={"title": "T"})).version == "2.3"
    with pytest.raises(ValueError, match="restart"):
        Header(layers={"restart": ["a"]})


VOICED = (
    "unitracker:2.4\n"
    "meta:{title:T}\n"
    "voices:2\n"
    "phrase:\n"
    " p1:[C4,-]\n"
    " p2:[D4]\n"
    "song:\n"
    " - voice:[p1,[p2,p1+2]x2,[p1|p2|p1+1]|loop:1]\n"
    " - voice:[p2+1,p3=[E4,-]|end]\n"
)


def test_voice_orderlists_read_and_print_their_one_text():
    doc = read(VOICED)
    assert printed(doc) == VOICED and doc.version == "2.4" and doc.loop is None
    assert doc.rows[0].loop == 1 and doc.rows[1].loop is None
    assert doc.rows[1].play[0] == Play("p2", 1)
    assert "p3:[E4,-]" in printed(top_level(doc))


def test_voice_orderlists_expand_their_groups_and_their_loop_to_its_first_entry():
    out = expanded(read(VOICED))
    assert out.rows[0] == Voice(
        ("p1", "p2", Play("p1", 2), "p2", Play("p1", 2), "p1", "p2", "p1", Play("p1", 1)), 1
    )
    looped = read(VOICED.replace("|loop:1]", "|loop:2]"))
    assert expanded(looped).rows[0].loop == 5


@pytest.mark.parametrize(
    "old, new",
    [
        ("unitracker:2.4", "unitracker:2.3"),
        ("|end]\n", "|end]\n - end\n"),
        (" - voice:[p2+1", " - play:[p2+1"),
        ("[p2+1,", "[[C4]+1,"),
        ("|end]", "]"),
    ],
)
def test_an_orderlist_is_2_4_alone_in_its_song_of_entries_and_groups(old, new):
    with pytest.raises(CanonicalError):
        parse(VOICED.replace(old, new))


def test_a_song_of_orderlists_prints_only_voices():
    doc = read(VOICED)
    with pytest.raises(CanonicalError, match="one Voice per voice"):
        printed(replace(doc, rows=doc.rows + (SongRow(["p1", "p1"]),)))
    with pytest.raises(CanonicalError, match="one Voice per voice"):
        printed(replace(doc, loop=0))


RESTART = (
    "unitracker:2.4\n"
    "meta:{title:T}\n"
    "ins:\n"
    " i1:{ad:9,restart:hr(2,15,0)}\n"
    " i2:{restart:hr(1,15,0,1,1)}\n"
    " hri(a):{sr:a,restart:hr(6,a,0,0,1)}\n"
    "phrase:\n"
    " p1:[C4.i1,D.i2,E.hri(3)]\n"
    "song:\n"
    " - play:[p1]\n"
    " - end\n"
)


def core_text(text: str) -> str:
    return printed(expanded(read(text)))


def test_a_prelude_restart_reads_prints_and_expands_to_its_rows():
    assert printed(read(RESTART)) == RESTART and read(RESTART).version == "2.4"
    out = printed(expanded(read(RESTART)))
    assert out.startswith("unitracker:2.3\n")
    assert " i1:{ad:9,restart:[{hold:2,gate:0,ad:15,sr:0},{},end]}\n" in out
    assert " i2:{restart:[{mask:8,gate:0,ad:15,sr:0,run:ctrl[end]},{mask:0},end]}\n" in out
    assert " i3:{sr:3,restart:[{hold:6,gate:0,ad:3,sr:0,run:ctrl[end]},{},end]}\n" in out


def test_a_document_s_own_hr_is_its_own_and_2_3():
    own = RESTART.replace("ins:\n", "restart:\n hr(h,a,s):[{hold:h,ad:a,sr:s},{},end]\nins:\n")
    own = own.replace("hr(1,15,0,1,1)", "hr(1,15,0)").replace("hr(6,a,0,0,1)", "hr(6,a,0)")
    own = own.replace("2.4", "2.3")
    assert read(own).version == "2.3" and " i1:{ad:9,restart:hr(2,15,0)}\n" in core_text(own)
    for text in (own.replace("2.3", "2.4"), RESTART.replace("2.4", "2.3")):
        with pytest.raises(CanonicalError, match="exactly where"):
            parse(text)


@pytest.mark.parametrize("call", ["hr(2,15)", "hr(2,15,0,0,0,0)", "hr(0,15,0)"])
def test_a_prelude_restart_takes_a_lead_of_a_tick_or_more_and_3_to_5_integers(call):
    with pytest.raises(CanonicalError, match="hr"):
        expanded(read(RESTART.replace("hr(2,15,0)", call)))
