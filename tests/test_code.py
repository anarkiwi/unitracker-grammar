"""Code templates: read from a text or a document, checked and printed in their one text."""

import re

import pytest

from unitracker_grammar import CanonicalError, parse
from unitracker_grammar.code import (
    LEGAL,
    MNEMONICS,
    NOTES,
    Call,
    CodeError,
    Imm,
    Label,
    Mem,
    Op,
    call,
    canonical,
    check,
    declare,
    line,
    op,
    params,
    printed,
    read,
    signature,
    signatures,
    state,
    symbols,
    templates,
)

VIB = (
    "lda t\nbmi up\ncmp #c\nbeq up\nbcc up\neor #255\nup:\nclc\nadc #2\nsta t\n"
    "lda G.lo+3,x\nldx #<p\nldy #>p\nstx v+1\nsta v,y\nlsr\njmp out\nout:\nrts\n"
)


def document(head: str, block: str) -> str:
    body = "".join(f"          {s}\n" for s in block[:-1].split("\n"))
    return (
        f"unitracker: 1.23\nmeta: {{title: T}}\n{head}song:\n  - def:\n      mod:\n"
        f"        vib: |\n{body}        porta: v + s\n      x:\n        x1: vib {{c: 3, p: 9}}\n"
        "      phrase:\n        p1: [C4.i1]\n    play: [p1]\n  - end\n"
    )


def test_a_routine_is_its_statements_in_order():
    code = read(VIB)
    assert code[:8] == (
        Op("lda", "memory", Mem("t")),
        Op("bmi", "label", "up"),
        Op("cmp", "immediate", Imm("c")),
        Op("beq", "label", "up"),
        Op("bcc", "label", "up"),
        Op("eor", "immediate", Imm(255)),
        Label("up"),
        Op("clc", "implied"),
    )
    assert code[10:16] == (
        Op("lda", "memory,x", Mem("G.lo", 3, "x")),
        Op("ldx", "immediate", Imm("p", "<")),
        Op("ldy", "immediate", Imm("p", ">")),
        Op("stx", "memory", Mem("v", 1)),
        Op("sta", "memory,y", Mem("v", 0, "y")),
        Op("lsr", "implied"),
    )
    assert code[16] == Op("jmp", "label", "out")
    assert params(code) == ("c", "p")
    assert symbols(code) == ("t", "G.lo", "v")


def test_a_routine_prints_its_one_text():
    assert printed(read(VIB)) == canonical(VIB) == VIB
    assert line(Op("lda", "memory,x", Mem("v", 1, "x"))) == "lda v+1,x"
    assert read(printed((op("rts"),))) == (Op("rts", "implied"),)


def test_the_legal_table_is_the_nmos_6502_s_documented_opcodes_less_three():
    assert len(MNEMONICS) == 53 and not MNEMONICS & {"brk", "jsr", "rti"}
    assert {("stx", "memory,y"), ("ldx", "memory,y"), ("jmp", "label"), ("asl", "implied")} < LEGAL
    assert not {("stx", "memory,x"), ("sta", "immediate"), ("jmp", "memory")} & LEGAL
    assert {m for m, how in LEGAL if how == "label"} == {
        "bcc",
        "bcs",
        "beq",
        "bmi",
        "bne",
        "bpl",
        "bvc",
        "bvs",
        "jmp",
    }


@pytest.mark.parametrize(
    "text, why",
    [
        ("lda t\n", "no rts"),
        ("foo\nrts\n", "unknown mnemonic 'foo'"),
        ("brk\nrts\n", "unknown mnemonic 'brk'"),
        ("jsr t\nrts\n", "unknown mnemonic 'jsr'"),
        ("rti\nrts\n", "unknown mnemonic 'rti'"),
        ("jmp t+1\nrts\n", "jmp has no memory mode"),
        ("jmp t,x\nrts\n", "jmp has no memory,x mode"),
        ("jmp #1\nrts\n", "jmp has no immediate mode"),
        ("bne T.lo\nrts\n", "bne has no memory mode"),
        ("bne out\nrts\n", "undefined label 'out'"),
        ("jmp out\nrts\n", "undefined label 'out'"),
        ("up:\nup:\nrts\n", "duplicate label 'up'"),
        ("phi:\nrts\n", "label 'phi' is a symbol"),
        ("x:\nrts\n", "label 'x' is a symbol"),
        ("nn:\nrts\n", "label 'nn' is a symbol"),
        ("lsr a\nrts\n", "'a' is a register, not a memory symbol"),
        ("ldx y,y\nrts\n", "'y' is a register"),
        ("lda #256\nrts\n", "immediate 256 is not a byte"),
        ("stx t,x\nrts\n", "stx has no memory,x mode"),
        ("lda up\nup:\nrts\n", "'up' is a label, not a memory symbol"),
        ("sta #1\nrts\n", "sta has no immediate mode"),
        ("clc #1\nrts\n", "clc has no immediate mode"),
        ("lda\nrts\n", "lda has no implied mode"),
        ("rts", "newline"),
    ],
)
def test_a_routine_outside_the_template_rules_is_refused(text, why):
    with pytest.raises(CodeError, match=why):
        read(text)


@pytest.mark.parametrize(
    "text",
    [
        "lda #007\nrts\n",
        "lda #$10\nrts\n",
        "lda #-1\nrts\n",
        "lda t+0\nrts\n",
        "lda t+01\nrts\n",
        "lda (t),y\nrts\n",
        "lda t,z\nrts\n",
        "lda  t\nrts\n",
        "lda t ; comment\nrts\n",
        "LDA t\nrts\n",
        "lda #<5\nrts\n",
        "lda T.mid\nrts\n",
        "lda Fo.lo\nrts\n",
        "lda N.lo\nrts\n",
        "up :\nrts\n",
        " up:\nrts\n",
        "\nrts\n",
        "rts\n\n",
    ],
)
def test_other_statement_spellings_are_refused(text):
    """A non-decimal or zero-padded integer, an offset of 0, indirect modes, other indexes,
    spacing, comments, capitals, a byte of an integer and blank lines."""
    with pytest.raises(CodeError, match="line"):
        read(text)


def test_check_refuses_an_op_whose_mode_is_not_its_operand_s_and_labels_of_names():
    with pytest.raises(CodeError, match="not in mode"):
        check((Op("lda", "immediate", Mem("t")), Op("rts", "implied")))
    with pytest.raises(CodeError, match="label 'up' is a symbol"):
        read("up:\nrts\n", {"up"})


STATE = "state: {freq: {t: 1, w: 2}, cut: {k: 1}}\n"


def test_a_document_s_templates_are_its_code_blocks_checked():
    tree = parse(document(STATE, VIB))
    assert templates(tree) == {"vib": read(VIB)}
    assert state(tree) == {"freq": (("t", 1), ("w", 2)), "cut": (("k", 1),)}
    assert state(parse(document("", VIB))) == {}
    with pytest.raises(CodeError, match="label 't' is a symbol"):
        templates(parse(document(STATE, "t:\nrts\n")))
    with pytest.raises(CodeError, match="no rts"):
        templates(parse(document(STATE, "clc\n")))


def test_a_state_variable_is_declared_once_across_cells():
    with pytest.raises(CanonicalError, match="twice"):
        state(parse(document("state: {freq: {t: 1}, pw: {t: 1}}\n", VIB)))


def test_a_call_is_its_name_and_integer_arguments():
    assert call("vib(0,-4,+32)") == Call("vib", (0, -4, 32))
    assert call("note()") == Call("note") and str(Call("vib", (0, -4))) == "vib(0,-4)"


def test_a_signature_declares_the_parameters_the_body_reads():
    assert signature("vib(l, c, s)") == ("vib", ("l", "c", "s")) and signature("n()") == ("n", ())
    assert declare("vib(s, c)", ("c", "s")) == ("vib", ("s", "c"))
    with pytest.raises(CodeError, match="declared twice"):
        signature("vib(c, c)")
    with pytest.raises(CodeError, match=r"undeclared \['s'\], unread \[\]"):
        declare("vib(c)", ("c", "s"))
    with pytest.raises(CodeError, match=r"undeclared \[\], unread \['d'\]"):
        declare("vib(c, d)", ("c",))
    with pytest.raises(CodeError, match=r"\['t'\] are state variables"):
        declare("vib(t)", ("t",), {"t"})


TOP = (
    "unitracker: 1.23\nmeta: {title: T}\nstate: {freq: {t: 1}}\nmod:\n  walk(s): v + s*n\n"
    "  note(): F(N)\n  vib(c, p): |\n    lda t\n    cmp #c\n    lda #>p\n    lda F.lo,x\n"
    "    rts\nsong:\n  - def:\n      mod:\n        add(d): |\n          adc #d\n          rts\n"
    "        old: v\n      phrase:\n        p1: [C4]\n    play: [p1]\n  - end\n"
)


def test_a_document_s_signatures_and_templates_are_in_its_rows_and_its_mod_section():
    tree = parse(TOP)
    assert signatures(tree) == {"walk": ("s",), "note": (), "vib": ("c", "p"), "add": ("d",)}
    assert set(templates(tree)) == {"vib", "add"}
    assert templates(tree)["vib"][3] == Op("lda", "memory,x", Mem("F.lo", 0, "x"))
    assert NOTES == ("F.lo", "F.hi")
    with pytest.raises(CodeError, match="are state variables"):
        signatures(parse(TOP.replace("walk(s): v + s*n", "walk(t): v + t*n")))


@pytest.mark.parametrize(
    "wrong, right, read_with",
    [
        ("walk(s)", "walk()", signatures),
        ("vib(c, p)", "vib(c)", templates),
        ("vib(c, p)", "vib(c, p, q)", signatures),
        ("add(d)", "add()", templates),
    ],
)
def test_a_signature_other_than_the_body_s_parameters_is_refused(wrong, right, read_with):
    with pytest.raises(CodeError, match=re.escape(f"{right}: undeclared")):
        read_with(parse(TOP.replace(wrong, right)))
