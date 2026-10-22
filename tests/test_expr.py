"""The modulator expression language: checked, printed in its one text and compiled."""

import ast

import pytest
from lark import Tree

from unitracker_grammar import frequency, parse
from unitracker_grammar.expr import (
    ExpressionError,
    Nodes,
    canonical,
    compile_expr,
    indexed,
    printed,
    source,
    tree,
    written,
)

NS = {"_F": frequency, "_T": {"W": indexed([5, 6, 7])}}
GRID = [(v, p, n) for v in (-300, -1, 0, 1, 7, 255, 4096) for p in (0, 1, 5, 64) for n in (0, 48)]


def values(fn) -> list:
    return [fn(*args) for args in GRID]


def test_an_expression_compiles_to_floored_python_integers():
    f = compile_expr("(v >= 3)*(F(N) % 7) - abs(-φ) + max(W[2], 1) + min(v, -3)", NS)
    assert f(3, 2, 57) == frequency(57) % 7 - 2 + 7 - 3
    assert f(0, 0, 0) == 7 - 3
    floor = compile_expr("φ // 30 - v // 4", {"_T": {}})
    assert [floor(-5, phi, 0) for phi in (-1, 0, 29, 30, 61)] == [1, 2, 2, 3, 4]
    assert compile_expr("W[3] + W[-1] + W[0]", NS)(0, 0, 0) == 5


def test_a_written_value_is_an_integer_literal_as_an_int():
    assert written("-5") == -5 and written(" 12") == 12 and written("v") == "v"


@pytest.mark.parametrize(
    "text, one",
    [
        ("1024 + 16*min(3, φ)", "16*min(3, φ) + 1024"),
        ("v + v + 2*3", "2*v + 6"),
        ("4*(v + 1) - 4", "4*v"),
        ("(φ + 1)*(v - 2)", "(v - 2)*(φ + 1)"),
        ("max(v, 2) + min(φ, 1)", "max(2, v) + min(1, φ)"),
        ("(v - 3) % 256 + v // 4", "(v - 3) % 256 + v // 4"),
        ("-(v % 8) + 2*(φ // 3)", "-(v % 8) + 2*(φ // 3)"),
        ("v % (φ + 1) - v % 3", "v % (φ + 1) - v % 3"),
        ("((v - 1) < 3)*W[φ + 0]", "(v - 1 < 3)*W[φ]"),
        ("v - v", "0"),
        ("0x10 + F(N)", "F(N) + 16"),
    ],
)
def test_an_expression_has_one_text(text, one):
    assert canonical(text) == one
    assert canonical(one) == one
    assert values(compile_expr(text, NS)) == values(compile_expr(one, NS))


def test_a_node_built_in_code_prints_its_one_text():
    node = ast.BinOp(ast.Call(ast.Name("F"), [ast.Name("N")], []), ast.Add(), ast.Name("v"))
    assert printed(node) == "v + F(N)"


def test_the_source_nests_each_operation_in_parentheses():
    assert source("v + 2*φ - -3", ()) == "((v + (2 * phi)) - (-3))"
    assert source("W[(v == 1)]", ["W"]) == "_T['W']((1 if v == 1 else 0))"


@pytest.mark.parametrize(
    "text, message",
    [
        ("min(v)", "takes 2"),
        ("v +", "bad expression"),
        ("sqrt(v)", "calls no grammar function"),
        ("abs(v, key=1)", "calls no grammar function"),
        ("U[1]", "unknown table 'U'"),
        ("[v < 1]", "a comparison is written"),
        ("(0 < v < 3)", "not one comparison"),
        ("(v in W)", "no grammar operator"),
        ("v ** 2", "outside the grammar"),
        ("True + v", "outside the grammar"),
        ("'v'", "outside the grammar"),
    ],
)
def test_other_texts_are_refused(text, message):
    with pytest.raises(ExpressionError, match=message):
        source(text, ["W"])


def test_a_divisor_of_zero_raises_unless_zero():
    text = "v // (φ - 1) + v % N + v // 0 % 3"
    with pytest.raises(ZeroDivisionError):
        compile_expr(text, NS)(7, 1, 2)
    zero = compile_expr(text, NS, zero=True)
    assert zero(7, 1, 2) == 0 + 7 % 2 + 0
    assert zero(7, 3, 0) == 3 + 0 + 0
    assert values(zero) == [
        (v // (p - 1) if p != 1 else 0) + (v % n if n else 0) for v, p, n in GRID
    ]


def test_a_nonzero_literal_divisor_is_not_guarded():
    assert source("v // 4 + v % -3", (), zero=True) == "((v // 4) + _mod(v, (-3)))"
    assert source(Nodes().transform(_expressions("v // 4 + v % -3")[0]), (), zero=True) == (
        "((v // 4) + (v % -3))"
    )
    assert source("v // 0 + v % φ", (), zero=True) == "(_div(v, 0) + _mod(v, phi))"


def _expressions(*texts: str) -> list:
    """The ``expr`` trees of a document whose expressions are ``texts``."""
    x = "".join(f"        x{k}: {t}\n" for k, t in enumerate(texts))
    text = (
        "unitracker: 1.20\nmeta: {title: T, author: A}\ntables:\n  W: [5, 6, 7]\nsong:\n"
        f"  - def:\n      x:\n{x}      phrase:\n        p1: [C4, -*3]\n    play: [p1, p1, p1]\n"
        "  - end\n"
    )
    (section,) = parse(text).find_pred(lambda t: t.data == "section" and t.children[0].type == "X")
    return [c for c in section.children if isinstance(c, Tree)]


FORMS = [
    "v + 2*φ - N",
    "F(N + 12) - F(N)",
    "W[φ % 3]*abs(v - 64)",
    "min(v, 100) + max(φ, 4) // 2",
    "(v < 3) + (φ >= 2)*(N != 0) + (v == N) - (v <= 1) + (φ > 4)",
    "(v + 1)*(φ - 1) % 7",
    "-(v + 1) + -v",
]


@pytest.mark.parametrize("text", FORMS)
def test_a_parse_tree_expression_is_the_node_of_its_text(text):
    (node,) = (Nodes().transform(t) for t in _expressions(text))
    assert source(node, ["W"]) == source(text, ["W"])
    assert printed(node) == canonical(text)


def test_a_minus_before_a_literal_is_a_negative_literal():
    signed, neg = (Nodes().transform(t) for t in _expressions("+5", "v*-3"))
    assert isinstance(signed, ast.Constant) and signed.value == 5
    assert isinstance(neg.right, ast.Constant) and neg.right.value == -3


def test_an_expression_wrapped_over_lines_is_one_node():
    text = (
        "unitracker: 1.20\nmeta: {title: T, author: A}\nsong:\n  - def:\n      ins:\n"
        "        i1: {freq: 'v\n            + min(φ, 2)'}\n      phrase:\n        p1: [C4.i1]\n"
        "    play: [p1, p1, p1]\n  - end\n"
    )
    (node,) = (Nodes().transform(t) for t in parse(text).find_data("fexpr"))
    assert printed(node) == "v + min(2, φ)"


def test_a_table_reads_zero_outside_its_values():
    w = indexed([5, 6, 7])
    assert [w(k) for k in range(-1, 4)] == [0, 5, 6, 7, 0]


def test_a_text_is_its_node():
    assert ast.dump(tree(" v + 1 ")) == ast.dump(ast.parse("v + 1", mode="eval").body)
