"""Format 2.4's layers: the header line, a layer's prefix on an instrument's program field and on
a run, read and printed in their one text."""

import pytest

from unitracker_grammar import CanonicalError, parse
from unitracker_grammar.document import (
    Def,
    Document,
    Event,
    Header,
    Instrument,
    Program,
    Section,
    SongRow,
    first_use,
    printed,
    read,
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
    assert doc.header.version == "2.4"
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
    assert Header(meta={"title": "T"}).version == "2.3"
    with pytest.raises(ValueError, match="restart"):
        Header(layers={"restart": ["a"]})
