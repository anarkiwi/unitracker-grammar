"""The document model: built directly or read, printed in its one text and read back equal."""

import random

import pytest
import yaml

from unitracker_grammar import CanonicalError, parse
from unitracker_grammar.document import (
    CONT,
    END,
    HOLD,
    NONE,
    Bound,
    Call,
    Code,
    Document,
    Event,
    Expr,
    Header,
    Instrument,
    Play,
    Program,
    Row,
    Run,
    Section,
    Shape,
    Signed,
    Slot,
    SongRow,
    base,
    printed,
    read,
    signature,
)

VIB = Code.of("lda t\nbmi up\nclc\nup:\nadc #c\nsta t\nlda v\nsta v+1,x\nrts")
META = (("title", "'Song, the first'"), ("author", "A"))


def built() -> Document:
    """A 1.23 document of every construct, built directly."""
    header = Header(
        "1.23",
        META,
        clock=(19656, 985248),
        voices=3,
        tempo=(6, 5),
        slots={
            "freq": [
                Slot("wave", Call("note"), reset=("row.note",)),
                Slot("tick", hold=("note-1", "row")),
            ],
            "pw": [Slot("a", Expr("v + 40")), Slot("b", VIB)],
        },
        order=("events", "ctrl", "pulse", "filter", "freq", "pw", "cut", "read"),
        state={"freq": [("t", 1)], "pw": [("r", 2)]},
    )
    ctrl = Program(
        [
            {"ctrl": 65, "note": Signed(0), "tick.freq": Call("vib", (3,)), "freq": NONE},
            {"wait": 2, "hold": 3, "ctrl": "129^8", "gate": 0, "note": "G#5", "ad": 9, "sr": 240},
            {"pw": Expr("16*min(3, φ) + 512"), "cut": 2048, "res": 15, "route": "+ 3", "mode": 16},
            {"run": "pw1", "filter": NONE, "vol": 15, "pw": HOLD, "b.pw": VIB},
            {"run": Run("pw", Program([{"pw": 5}])), "route": "'- 2'"},
        ],
        loop=1,
    )
    ins = Instrument(
        {
            "ad": 9,
            "sr": 240,
            "ctrl": "c1",
            "pw": "pw1",
            "filter": Program([{"cut": 512}, {}], 0),
            "tick.freq": Call("vib", (Signed(-4),)),
            "restart": Program([{"hold": 2, "gate": 0}]),
        }
    )
    events = [
        Event("C4", "i1", {"run": "c1", "tempo": (6, 7), "legato": True}, steps=2),
        Event("-", None, [("pw", Expr("v + 40")), ("filter", NONE), ("set", ("step", Signed(4)))]),
        Event("off", None, {"resfilt": (15, 1), "vtempo": 8, "freq": Signed(-139)}, True, True),
        Event("D#2", Instrument({"ad": 1, "freq": Expr("v + 3")}), {"cut": VIB, "ctrl": 33}),
        Event("on", None, {"run": Run("ctrl", Program([{"ctrl": 64}])), "b.pw": Call("ptab", ())}),
        Event("E1", None, {"freq": 256, "mode": 16, "vol": 15, "ad": 1, "sr": 2, "tempo": 8}),
        Event("-", None, {"run": NONE, "cut": NONE, "pw": "x1"}),
        Event("C4", Instrument({"ctrl": Call("arp", (7, 4)), "restart": Call("hr", (2,))})),
        Event("-", None, {"run": Call("arp", (3, 4))}),
    ]
    defs = {
        "ins": [("i1", ins)],
        "ctrl": [
            ("c1", ctrl),
            (
                signature("arp", ["a", "b"]),
                Program([{"ctrl": 65, "note": "+a", "ad": "b"}, {"pw": Call("walk", ("b",))}]),
            ),
            ("c2", Program([{"run": Run("ctrl", Call("arp", (7, Signed(-4))))}])),
        ],
        "pw": [("pw1", Expr("95*φ + 296")), ("pw2", Bound(Expr("walk"), (("s", 3),)))],
        "restart": [("r1", Program([{"hold": 2, "gate": 0, "ad": 15}, {"ctrl": 9}]))],
        "filter": [("f1", 1024)],
        "phrase": [("p1", events), ("p2", [Event("C4", "i1"), Event("-", steps=3)])],
    }
    return Document(
        header,
        tables={"G": [279, 295, 313], "PL": [0, 128]},
        mods=[
            (signature("vib", ["c"]), VIB),
            (signature("ptab"), Expr("PL[φ]")),
            ("note()", Expr("F(N)")),
        ],
        init=[Event("-", "i1", {"vol": 15}), Event("-", "i1"), Event("-", "i1")],
        rows=[
            SongRow(
                ["p1", Play("p2", Signed(2)), Play([Event("C4"), Event("-", steps=3)], Signed(-1))],
                defs,
            ),
            SongRow([CONT, Play("p2"), END]),
        ],
        loop=0,
    )


def test_a_built_document_prints_its_canonical_text_and_reads_back_equal():
    doc = built()
    text = printed(doc)
    parse(text)
    assert read(text) == doc
    assert printed(read(text)) == text
    assert "        c1: [{ctrl: 65, note: +0, tick.freq: vib(3), freq: none}," in text
    assert "!pw:'v + 40'!filter:none!set step +4" in text
    assert "        arp(a, b): [{ctrl: 65, note: +a, ad: b}, {pw: walk(b)}, end]\n" in text
    assert "c2: [{run: ctrl:arp(7,-4)}, end]" in text and "-!run:arp(3,4)" in text
    assert (
        "slots: {freq: {wave: {mod: note(), reset: [row.note]}, tick: {hold: [note-1, row]}}"
        in text
    )
    assert "  vib(c): |\n    lda t\n    bmi up\n    clc\n    up:\n" in text
    assert "    play: [p1, p2+2, [C4, -*3]-1]\n  - play: [~, p2, end]\n  - {loop: 0}\n" in text


def test_a_constructor_orders_keys_as_the_grammar_and_stores_tuples():
    row = Row({"freq": 1, "wait": 2, "tick.pw": 3, "pw": 4})
    assert row.keys == (("wait", 2), ("tick.pw", 3), ("pw", 4), ("freq", 1))
    assert row.get("pw") == 4 and row.get("cut") is None
    assert Instrument({"restart": "r1", "ad": 1}).fields == (("ad", 1), ("restart", "r1"))
    assert Instrument({"ad": 1}).get("ad") == 1
    assert Program([{"ctrl": 1}]).rows == (Row({"ctrl": 1}),)
    assert Event("C4", commands={"legato": True, "run": "c1"}).commands[0] == ("run", "c1")
    assert base("tick.freq") == "freq" and signature("f", ("a", "b")) == "f(a, b)"
    with pytest.raises(ValueError):
        Row({"bogus": 1})
    with pytest.raises(ValueError):
        Section("bogus")


def test_a_document_s_records_and_slots_are_looked_up_by_kind_and_cell():
    doc = built()
    assert set(doc.records("mod")) == {"vib(c)", "ptab()", "note()"}
    assert list(doc.records("phrase")) == ["p1", "p2"]
    assert [i for i, _ in doc.sections("ins")] == [0]
    assert doc.header.slot("cut") == (Slot("cut"),)
    assert [s.name for s in doc.header.slot("freq")] == ["wave", "tick"]
    assert Header().slot("freq") == (Slot("freq"),)


def test_signed_and_expressions_print_as_written():
    assert str(Signed(3)) == "+3" and repr(Signed(-2)) == "-2" and Signed(0) == 0
    assert str(Expr("v + 1")) == "v + 1" and Expr("v", quoted=True) == Expr("v")


V122 = """unitracker: 1.22
meta: {title: T, author: A}
hold: {freq: [step-1, row.freq], ctrl.pw: [note]}
song:
  - def:
      mod:
        porta: v + s
      x:
        x1: porta {s: 32}
        x2: 512
        x3: v - 263
      ins:
        i1: {pw: x2, freq: x1, mod: ramp {step: 2, skip: [1, 3]}}
        i2: {freq: porta {s: 1}, mod: set}
      phrase:
        p1: [C4.i1!cut:'2048'!freq:x3, -.i2!pw:2048!freq:hold, -*3]
    play: [p1, p1, p1]
  - end
"""


def test_a_1_22_document_s_instances_bags_and_shapes_round_trip():
    doc = read(V122)
    assert printed(doc) == V122
    ins = doc.records("ins")
    assert ins["i1"].get("mod") == Shape("ramp", (("step", 2), ("skip", (1, 3))))
    assert ins["i2"].get("freq") == Bound(Expr("porta"), (("s", 1),))
    assert doc.records("x")["x2"] == 512
    p1 = doc.records("phrase")["p1"]
    assert p1[0].commands == (("cut", Expr("2048")), ("freq", "x3"))
    assert p1[1].commands == (("pw", 2048), ("freq", HOLD))
    assert doc.header.hold == (("freq", ("step-1", "row.freq")), ("ctrl.pw", ("note",)))


class _Dumper(yaml.SafeDumper):  # pylint: disable=too-many-ancestors
    """PyYAML as writers use it: block sequences indented, every string plain."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)

    def choose_scalar_style(self):
        return ""


def _plain(dumper, data):
    if isinstance(data, list) and getattr(data, "flow", False):
        return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)
    return dumper.represent_list(data)


class _Flow(list):
    flow = True


_Dumper.add_representer(_Flow, _plain)

ATOMS = ["C4.i1", "-", "-*3", "C#-1", "D#2!tick.freq:vib(1,-4,32)", "-!pw:'v + 40'", "B1!run:c12"]


@pytest.mark.parametrize("seed", range(40))
def test_lines_wrap_as_pyyaml_wraps_them_at_width_100(seed):
    rng = random.Random(seed)
    tables = [rng.randrange(70000) for _ in range(rng.randrange(1, 120))]
    atoms = [rng.choice(ATOMS) for _ in range(rng.randrange(1, 90))]
    events = [read_event(a) for a in atoms]
    doc = Document(
        Header("1.23", META),
        tables={"T": tables},
        rows=[SongRow(["p1"], {"phrase": [("p1", events)]})],
    )
    tree = {
        "tables": {"T": _Flow(tables)},
        "song": [{"def": {"phrase": {"p1": _Flow(atoms)}}, "play": _Flow(["p1"])}, "end"],
    }
    expected = yaml.dump(tree, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)
    text = printed(doc)
    assert text.split("tables:\n", 1)[1] == expected.split("tables:\n", 1)[1]
    assert read(text) == doc


def read_event(atom: str) -> Event:
    """The event of an atom, read from a one-event phrase."""
    text = printed(Document(Header("1.23", META), rows=[SongRow(["p1"])]))
    text = text.replace(
        "  - play: [p1]\n", f"  - def:\n      phrase:\n        p1: [{atom}]\n    play: [p1]\n"
    )
    return read(text).records("phrase")["p1"][0]


HAND = """unitracker: 1.21
meta: {title: T, author: A}
song:
  - def:
      ins:
        i1: {pw: 95*φ
            + 296, restart: [{hold: 3, ctrl: ^8, gate: 0}, {},
            end]}
        i2: {pw: 95*φ
            + 296, restart: [{hold: 3, ctrl: ^8, gate: 0}, {},
            end]}
      phrase:
        p1: [
          C4.i1, -*3]
    play: [p1, p1, p1]
  - {loop: 0}
"""


@pytest.mark.noncanonical
def test_a_text_read_wrapped_otherwise_prints_its_one_canonical_text():
    doc = read(HAND)
    out = printed(doc)
    assert out != HAND and read(out) == doc and printed(read(out)) == out
    assert "        i1: {pw: 95*φ + 296, restart: [{hold: 3, ctrl: ^8, gate: 0}, {}, end]}\n" in out


def test_a_text_outside_the_grammar_is_refused_at_its_place():
    with pytest.raises(CanonicalError, match="line 1"):
        read("unitracker 1.23\n")
    with pytest.raises(Exception):
        Code.of("lda v\n")


def test_top_level_definitions_print_after_the_templates_at_two_spaces():
    doc = Document(
        Header("1.23", META),
        mods=[("note()", Expr("F(N)"))],
        defs={"ins": [("i1", Instrument({"ad": 9}))], "ctrl": [("c1", Program([{"ctrl": 65}]))]},
        init=[Event("-", "i1")],
        rows=[SongRow(["p1"], {"phrase": [("p1", [Event("C4", "i1")])]})],
    )
    text = printed(doc)
    assert "  note(): F(N)\nins:\n  i1: {ad: 9}\nctrl:\n  c1: [{ctrl: 65}, end]\ninit:" in text
    assert list(doc.records("ins")) == ["i1"] and doc.sections("ctrl")[0][0] is None
    assert read(text) == doc and printed(read(text)) == text
