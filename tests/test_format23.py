"""Format 2.3's constructs: read and printed in their one text, at their first use and in their
sections, and expanded to the core they stand for."""

import importlib.util
import sys
from pathlib import Path

import pytest

from unitracker_grammar import CanonicalError, expr, frequency, parse
from unitracker_grammar.chords import CHORDS
from unitracker_grammar.code import CodeError
from unitracker_grammar.document import (
    Call,
    Group,
    Once,
    Part,
    SongRow,
    first_use,
    printed,
    read,
    top_level,
)
from unitracker_grammar.expand import core, expanded, flat
from unitracker_grammar.prelude import NAMES, PRELUDE

HEAD = "unitracker:2.3\nmeta:{title:T}\n"
TOOLS = Path(__file__).resolve().parents[1] / "tools"


def doc(body: str, song: str = " - play:[p1,p1,p1]\n - end\n") -> str:
    """A document of ``body``'s definitions and ``song``'s items."""
    return HEAD + body + "song:\n" + song


def core_text(text: str) -> str:
    """The core of ``text``, printed."""
    return printed(expanded(read(text)))


SUGAR = doc(
    "ins:\n i1:{ad:9}\n arpi(a,b):{ad:a,sr:b,ctrl:ar(a,7)}\nctrl:\n"
    " ar(a,b):[{note:+a},{note:+b},{loop:0}]\nphrase:\n"
    " p1:[C4.i1 run:ar(maj),[E,G]x2,[A|B|C5 pw:800!],-*2,D.arpi(3,4) tick.freq:vibrato(2,3,4)]\n"
    " riff(x,y):[x.i1,-,y tick.freq:'v + 1'!,E4]\nsection:\n"
    " s1:[play:[p1,p1,p1],s2=[play:[p1,~,~]]x3,[play:[p1,p1,p1]|play:[~,p1,~]|play:[p1,~,~]]]\n",
    " - play:[p1,riff(G1,f1)+2,tpl(x)=[x,-](C4)]\n - s1x2\n - s3=[play:[p1,p1,p1]]\n"
    " - [play:[p1,p1,p1]]x2\n - {loop:2}\n",
)


def test_every_construct_reads_and_prints_its_one_text():
    model = read(SUGAR)
    assert printed(model) == SUGAR
    p1 = model.records("phrase")["p1"]
    assert p1[1] == Group((p1[1].body[0], p1[1].body[1]), 2)
    assert p1[2].endings and p1[2].endings[1][0].commands == (("pw", Once(800)),)
    assert model.rows[1] == Part("s1", 2)
    assert model.rows[0].play[1].phrase == Call("riff", ("G1", "F#1"))
    assert isinstance(model.rows[3], Group) and model.rows[3].times == 2


def test_definitions_move_to_their_sections_and_back_to_their_first_use():
    sections = printed(top_level(read(SUGAR)))
    assert " tpl(x):[x,-]\n" in sections and " s2:[play:[p1,~,~]]\n" in sections
    assert " - play:[p1,riff(G1,f1)+2,tpl(C4)]\n" in sections
    used = printed(first_use(read(sections)))
    assert "section:" not in used and "phrase:" not in used
    assert " - s1=[play:[p1,p1,p1],s2=[play:[p1,~,~]]x3," in used
    kinds = [{s.kind: set(s.records) for s in top_level(read(t)).defs} for t in (used, sections)]
    assert kinds[0] == kinds[1]


def test_the_sugar_expands_to_the_core():
    out = core_text(SUGAR)
    assert " i2:{ad:3,sr:4,ctrl:ar(3,7)}\n" in out
    assert (
        " p1:[C4.i1 run:ar(4,7),E,G,E,G,A,B,A,C5 pw:800!,-*2,D.i2 tick.freq:vibrato(2,3,4)]\n"
        in out
    )
    assert " - play:[p1,[G1.i1,-,f tick.freq:'v + 1'!,E4]+2,[C4,-]]\n" in out
    rows = out.split("song:\n")[1].splitlines()
    assert len(rows) == 1 + 2 * (1 + 3 + 2 * 2) + 1 + 2 + 1
    assert rows[-1] == " - {loop:17}"
    assert "section:" not in out and "arpi" not in out and "riff" not in out
    assert core(out) == parse(out) and core(SUGAR) == parse(out)


def test_groups_play_out_in_order():
    a, b, c, d = "abcd"
    assert flat((Group((a, Group((b,), 2)), 2), c)) == (a, b, b, a, b, b, c)
    assert flat((Group((a,), None, ((b,), (c, d))),)) == (a, b, a, c, d)
    with pytest.raises(CanonicalError, match="two endings"):
        flat((Group((a,), None, ((b,),)),))


def test_a_note_after_a_group_or_parameter_keeps_the_written_octave_rule():
    text = doc("phrase:\n p1:[C4,[E,G5]x2,A|x]\n".replace("|x", ""))
    assert core_text(text).count("p1:[C4,E,G5,E4,G5,A]") == 1
    text = doc("phrase:\n p1:[C4]\n t(x):[C4,x,E4]\n", " - play:[t(D2),p1,p1]\n - end\n")
    assert "[C4,D2,E4]" in core_text(text)
    with pytest.raises(CanonicalError, match="without its octave"):
        read(doc("phrase:\n p1:[C4]\n t(x):[C4,x,E]\n", " - play:[t(D2),p1,p1]\n - end\n"))


@pytest.mark.parametrize(
    "text, error, match",
    [
        (doc("phrase:\n p1:[C4,x]\n"), CodeError, "outside a phrase template"),
        (doc("phrase:\n p1:[C4]\n t(x,y):[x]\n"), CodeError, r"unread \['y'\]"),
        (doc("ins:\n t(a):{ad:9}\nphrase:\n p1:[C4]\n"), CodeError, r"unread \['a'\]"),
        (doc("ins:\n i1:{ad:a}\nphrase:\n p1:[C4]\n"), CodeError, "declares no parameter"),
        (doc("mod:\n glide(s):v + s\nphrase:\n p1:[C4]\n"), CodeError, "prelude"),
        (doc("ctrl:\n sweep(a):[{wait:a},end]\nphrase:\n p1:[C4]\n"), CodeError, "prelude"),
        (doc("phrase:\n p1:[C4]\n", " - s1\n - end\n"), CanonicalError, "unknown section"),
    ],
)
def test_constructs_outside_their_rules_are_refused(text, error, match):
    with pytest.raises(error, match=match):
        core_text(text)


@pytest.mark.parametrize(
    "body, song, match",
    [
        ("phrase:\n p1:[C4]\nsection:\n s1:[s1]\n", " - s1\n - end\n", "plays itself"),
        ("ins:\n t(a):{ad:a}\nphrase:\n p1:[C4.t(1,2)]\n", None, "takes 1 argument"),
        ("phrase:\n p1:[C4.t(1)]\n", None, "no instrument template"),
        ("phrase:\n p1:[C4]\n", " - play:[t(C4),p1,p1]\n - end\n", "no phrase template"),
    ],
)
def test_calls_and_sections_that_do_not_fit_are_refused(body, song, match):
    with pytest.raises(CanonicalError, match=match):
        core_text(doc(body, *([song] if song else [])))


def test_a_chord_name_is_its_intervals_but_a_template_parameter():
    text = doc(
        "ctrl:\n ar(a,b,c):[{note:+a},{note:+b},{note:+c},end]\n t(maj):[{run:ar(maj,1,2)},end]\n"
        " c1:[{run:ar(min7)},{run:t(oct)},end]\nphrase:\n p1:[C4]\n"
    )
    out = core_text(text)
    assert "c1:[{run:ar(3,7,10)},{run:t(12)},end]" in out
    assert "t(maj):[{run:ar(maj,1,2)},end]" in out


def test_once_reads_in_commands_rows_and_fields():
    text = doc(
        "ins:\n i1:{ad:9,pw:800!,freq:'v + 2'!}\nctrl:\n c1:[{pw:'v + 1'!,cut:7!},end]\n"
        "phrase:\n p1:[C4.i1 pw:9! tick.freq:snap()!]\n"
    )
    model = read(text)
    assert printed(model) == text
    assert model.records("ins")["i1"].get("pw") == Once(800)


def test_lag_and_global_header_lines():
    text = HEAD + "regs:" + str([0] * 25).replace(" ", "") + "\nlag:1\nglobal:[cut]\n"
    text += "phrase:\n p1:[C4]\nsong:\n - play:[p1,p1,p1]\n - end\n"
    model = read(text)
    assert (model.header.lag, model.header.global_cells) == (1, ("cut",))
    assert printed(model) == text


def test_the_song_form_and_its_loop_play_out():
    text = doc(
        "phrase:\n p1:[C4]\n p2:[D4]\nsection:\n s1:[play:[p1,p1,p1],play:[p2,p2,p2]]\n",
        " - s1\n - [s1|play:[p1,p2,p1]|play:[p2,p1,p2]]\n - {loop:1}\n",
    )
    rows = core_text(text).split("song:\n")[1].splitlines()
    assert rows[-1] == " - {loop:2}" and len(rows) == 2 + 2 * 3 + 1
    assert read(text).rows[0] == Part("s1")
    assert isinstance(read(core_text(text)).rows[0], SongRow)


@pytest.mark.parametrize("key", sorted(PRELUDE))
def test_each_prelude_template_is_a_canonical_expression(key):
    name, _, params = key.partition("(")
    assert name in NAMES
    assert sorted(expr.params(expr.tree(PRELUDE[key]))) == sorted(params[:-1].split(","))
    assert expr.canonical(PRELUDE[key]) == PRELUDE[key]


def _prelude(key: str, args: dict, v=0, phis=range(12), note=57):
    node = expr.bind(expr.tree(PRELUDE[key]), args)
    fn = expr.compile_expr(node, {"_F": frequency, "_T": {}}, zero=True)
    return [fn(v, phi, note) for phi in phis]


def test_the_prelude_templates_play_their_shapes():
    a4 = frequency(57)
    vib = _prelude("vibrato(d,s,l)", {"d": 2, "s": 2, "l": 1}, phis=range(10))
    assert [x - a4 for x in vib] == [0, 0, 2, 4, 2, 0, -2, -4, -2, 0]
    assert _prelude("glide(s)", {"s": -3}, v=10, phis=[0]) == [7]
    up = [_prelude("slide(t,s)", {"t": 0, "s": 100}, v=v, phis=[0])[0] for v in (a4 - 250, a4 - 50)]
    assert up == [a4 - 150, a4]
    assert _prelude("pwm(lo,hi,s)", {"lo": 10, "hi": 16, "s": 2}, phis=range(7)) == [
        10,
        12,
        14,
        16,
        14,
        12,
        10,
    ]
    assert _prelude("sweep(a,b,s)", {"a": 9, "b": 3, "s": 2}, phis=range(5)) == [9, 7, 5, 3, 3]
    assert _prelude("tremolo(lo,hi,s)", {"lo": 1, "hi": 5, "s": 2}, phis=range(5)) == [
        1,
        1,
        5,
        5,
        1,
    ]


def test_the_chord_table_is_music21s():
    pytest.importorskip("music21")
    spec = importlib.util.spec_from_file_location("chords_tool", TOOLS / "chords.py")
    tool = importlib.util.module_from_spec(spec)
    sys.modules["chords_tool"] = tool
    spec.loader.exec_module(tool)
    assert tool.table() == CHORDS
    assert (Path(__file__).resolve().parents[1] / "src/unitracker_grammar/chords.py").read_text(
        encoding="utf-8"
    ) == tool.text()


def test_an_instrument_or_phrase_record_may_be_a_template_call():
    text = doc(
        "ins:\n i1:arpi(9,min)\n arpi(a,b,c):{ad:a,ctrl:ar(b,c)}\nctrl:\n"
        " ar(a,b):[{note:+a},{note:+b},end]\nphrase:\n p1:riff(C4)\n riff(x):[x.i1,-]\n",
        " - play:[p1,p2=riff(D4),p3=[C4.i2=arpi(1,maj)]]\n - end\n",
    )
    assert printed(read(text)) == text
    out = core_text(text)
    assert " i1:{ad:9,ctrl:ar(3,7)}\n" in out and " i2:{ad:1,ctrl:ar(4,7)}\n" in out
    assert " p1:[C4.i1,-]\n" in out and " p2:[D4.i1,-]\n" in out


def test_an_integer_template_body_at_its_first_use_stays_quoted():
    text = doc("phrase:\n p1:[C4 pw:k()='2048'()]\n")
    assert printed(read(text)) == text


def test_a_count_of_two_digits_reads():
    text = doc("phrase:\n p1:[C4,[D]x23]\nsection:\n s1:[play:[p1,p1,p1]]\n", " - s1x23\n - end\n")
    model = read(text)
    assert printed(model) == text and model.rows[0] == Part("s1", 23)


@pytest.mark.parametrize(
    "body, song",
    [
        ("ins:\n i1:t(40,8)\n t(s,q):{ad:9,sr:q,pw:glide(s)}\nphrase:\n p1:[C4.i1,-,E.i1]\n", None),
        (
            "phrase:\n p1:[C4]\n t(x,y):[x.i1,-,y,E4]\n p2:t(G1,f1)\n",
            " - play:[p2,p1,p2]\n - end\n",
        ),
    ],
)
def test_a_call_record_and_its_template_both_at_their_first_use(body, song):
    text = doc(body, *([song] if song else []))
    used = printed(first_use(read(text)))
    assert "=t(" in used and printed(read(used)) == used
    assert sorted(core_text(used).splitlines()) == sorted(core_text(text).splitlines())


def test_a_chord_whose_name_ends_in_a_digit_is_no_note():
    text = doc(
        "ctrl:\n ar(a,b,c):[{note:+a},{note:+b},{note:+c},end]\n c1:[{run:ar(dom7)},end]\n"
        "phrase:\n p1:[C4]\n"
    )
    assert "c1:[{run:ar(4,7,10)},end]" in core_text(text)
