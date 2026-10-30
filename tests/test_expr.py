"""The modulator expression language: checked, printed in its one text and compiled."""

import ast

import pytest
from lark import Tree

from unitracker_grammar import expr, frequency, parser
from unitracker_grammar.expr import (
    ExpressionError,
    Nodes,
    bind,
    canonical,
    compile_expr,
    indexed,
    params,
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
    f = compile_expr("(v >= 3)*(F(N) % 7) - abs(-phi) + max(W[2],1) + min(v,-3)", NS)
    assert f(3, 2, 57) == frequency(57) % 7 - 2 + 7 - 3
    assert f(0, 0, 0) == 7 - 3
    floor = compile_expr("phi // 30 - v // 4", {"_T": {}})
    assert [floor(-5, phi, 0) for phi in (-1, 0, 29, 30, 61)] == [1, 2, 2, 3, 4]
    assert compile_expr("W[3] + W[-1] + W[0]", NS)(0, 0, 0) == 5


def test_a_written_value_is_an_integer_literal_as_an_int():
    assert written("-5") == -5 and written(" 12") == 12 and written("v") == "v"


@pytest.mark.parametrize(
    "text, one",
    [
        ("1024 + 16*min(3,phi)", "16*min(3,phi) + 1024"),
        ("v + v + 2*3", "2*v + 6"),
        ("4*(v + 1) - 4", "4*v"),
        ("(phi + 1)*(v - 2)", "(phi + 1)*(v - 2)"),
        ("max(v,2) + min(phi,1)", "max(2,v) + min(1,phi)"),
        ("(v - 3) % 256 + v // 4", "(v - 3) % 256 + v // 4"),
        ("-(v % 8) + 2*(phi // 3)", "2*(phi // 3) - v % 8"),
        ("v % (phi + 1) - v % 3", "v % (phi + 1) - v % 3"),
        ("((v - 1) < 3)*W[phi + 0]", "(v - 1 < 3)*W[phi]"),
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
    assert source("v + 2*phi - -3", ()) == "((v + (2 * phi)) - (-3))"
    assert source("W[(v == 1)]", ["W"]) == "_T['W']((1 if v == 1 else 0))"


@pytest.mark.parametrize(
    "text, message",
    [
        ("min(v)", "takes 2"),
        ("v +", "bad expression"),
        ("sqrt(v)", "calls no grammar function"),
        ("abs(v, key=1)", "calls no grammar function"),
        ("U[1]", "unknown table 'U'"),
        ("[v < 1]", "outside the grammar"),
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
    text = "v // (phi - 1) + v % N + v // 0 % 3"
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
    assert source("v // 0 + v % phi", (), zero=True) == "(_div(v, 0) + _mod(v, phi))"


def _expressions(*texts: str) -> list:
    """The ``expr`` trees of a document whose expressions are ``texts``."""
    mods = "".join(f" e{k}():{t}\n" for k, t in enumerate(texts))
    text = (
        "unitracker:2.3\nmeta:{title:T,author:A}\ntables:\n W:[5,6,7]\n"
        f"mod:\n{mods}song:\n - play:[[C4,-*3]]\n - end\n"
    )
    (section,) = parser().parse(text).find_data("def_mod")
    return [c for c in section.children if isinstance(c, Tree)]


FORMS = [
    "v + 2*phi - N",
    "F(N + 12) - F(N)",
    "W[phi % 3]*abs(v - 64)",
    "min(v,100) + max(phi,4) // 2",
    "(v < 3) + (phi >= 2)*(N != 0) + (v == N) - (v <= 1) + (phi > 4)",
    "(v + 1)*(phi - 1) % 7",
    "-(v + 1) + -v",
    "F(n + 12) - F(N) + n*phi",
    "v | phi & N ^ n",
    "~v & 255",
    "!v && phi || N",
    "!v == 0 && phi",
    "v < phi",
    "v + 1 == N << 2",
    "ite(v < 3,v << 2,phi >> 1)",
    "sx(lo(v)) + hi(u16(phi)) - u8(v > 1)",
    "v << 1 + 2",
    "(v | phi) << 2",
    "-~v + ~~v",
    "min(v < 3,2)",
    "W[v & 3] | (v == 1)",
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


@pytest.mark.noncanonical
def test_a_table_reads_zero_outside_its_values():
    w = indexed([5, 6, 7])
    assert [w(k) for k in range(-1, 4)] == [0, 5, 6, 7, 0]


def test_a_text_is_its_node():
    assert ast.dump(tree(" v + 1 ")) == ast.dump(ast.parse("v + 1", mode="eval").body)


def test_n_is_the_event_note_a_fourth_argument_0_when_left_out():
    """``n`` compiles to the function's fourth argument, which defaults to 0, and orders with the
    other names."""
    fn = compile_expr("F(n) + N - n", NS, zero=True)
    assert fn(0, 0, 50, 48) == frequency(48) + 2
    assert fn(0, 0, 50) == frequency(0) + 50
    assert canonical("n + N + v + 2*n") == "N + 3*n + v"
    assert source("n", ()) == "n"


def test_a_template_s_parameters_bind_to_integers():
    """A template reads lowercase parameters, not the names of its calls and tables; binding
    every one of them, and no other, closes it, and an unbound one does not compile."""
    node = tree("W[o + min(phi,a)]*v + abs(a - n) + N")
    assert params(node) == {"o", "a"}
    closed = bind(node, {"o": 1, "a": 2})
    assert printed(closed) == "N + abs(-n + 2) + v*W[min(2,phi) + 1]"
    assert compile_expr(closed, NS)(3, 0, 7, 4) == 7 + 3 * 6 + 2
    assert params(node) == {"o", "a"} and printed(bind(tree("v + 1"), {})) == "v + 1"
    for bag in ({"o": 1}, {"o": 1, "a": 2, "b": 3}):
        with pytest.raises(ExpressionError, match="parameters"):
            bind(node, bag)
    with pytest.raises(ExpressionError, match="unbound parameter 'o'"):
        source(node, ["W"])


def test_a_parameter_in_a_parse_tree_is_a_name():
    (node,) = (Nodes().transform(t) for t in _expressions("v + s*2"))
    assert params(node) == {"s"} and printed(node) == "v + 2*s"


TEXTS = [
    ("phi | v | N", "N | phi | v"),
    ("v & (phi | N)", "v & (N | phi)"),
    ("v | (phi | N)", "N | phi | v"),
    ("N ^ phi ^ v", "N ^ phi ^ v"),
    ("(v && phi) && N || n", "n || N && phi && v"),
    ("v < phi && N >= 2 || !n", "!n || N >= 2 && v < phi"),
    ("!(v && phi)", "!(phi && v)"),
    ("!(v < phi)", "!(v < phi)"),
    ("!v < phi", "!(v < phi)"),
    ("(!v) < phi", "(!v) < phi"),
    ("!!v", "!!v"),
    ("!(v + 1)", "!(v + 1)"),
    ("~(v + 1) & 255", "255 & ~(v + 1)"),
    ("~~v", "~~v"),
    ("-~v", "-~v"),
    ("2*~v", "2*~v"),
    ("~(-3)", "~(-3)"),
    ("~(!v)", "~(!v)"),
    ("v << 3 + 1", "v << 4"),
    ("(v << 3) + 1", "(v << 3) + 1"),
    ("v << (phi << 1)", "v << (phi << 1)"),
    ("(v << 1) << 2", "v << 1 << 2"),
    ("v - (phi >> 1)", "v - (phi >> 1)"),
    ("1 + (v < 3)*5", "5*(v < 3) + 1"),
    ("(v < 3) + (phi >= 2)*(N != 0)", "(N != 0)*(phi >= 2) + (v < 3)"),
    ("v == phi", "v == phi"),
    ("(v < phi) == (N < n)", "(v < phi) == (N < n)"),
    ("(v + 1) < phi*2", "v + 1 < 2*phi"),
    ("v < (phi | 1)", "v < 1 | phi"),
    ("(v & 1) == 0", "1 & v == 0"),
    ("ite(v < 3, 1 + v, 2)", "ite(v < 3,v + 1,2)"),
    ("ite(!v, sx(lo(v)), hi(phi))", "ite(!v,sx(lo(v)),hi(phi))"),
    ("min(v < 3, 2)", "min(2,v < 3)"),
    ("v | phi & N", "v | N & phi"),
    ("(v | phi) & N", "N & (phi | v)"),
    ("v != 0 || phi != 0", "phi != 0 || v != 0"),
]


@pytest.mark.parametrize("text, one", TEXTS)
def test_the_operators_have_one_text_with_the_parentheses_precedence_needs(text, one):
    assert canonical(text) == one
    assert canonical(one) == one
    assert values(compile_expr(text, NS)) == values(compile_expr(one, NS))


def test_the_precedence_is_playspec_s_from_loosest_to_tightest():
    """``|| && ! cmp | ^ & shift +- */ unary``: each pair reads as its parenthesised form."""
    pairs = [
        ("a || b && c", "a || (b && c)"),
        ("!a && b", "(!a) && b"),
        ("!a == b", "!(a == b)"),
        ("a == b | c", "a == (b | c)"),
        ("a | b ^ c", "a | (b ^ c)"),
        ("a ^ b & c", "a ^ (b & c)"),
        ("a & b << c", "a & (b << c)"),
        ("a << b + c", "a << (b + c)"),
        ("a + b*c", "a + (b*c)"),
        ("a*~b", "a*(~b)"),
        ("-a*b", "(-a)*b"),
        ("a << b << c", "(a << b) << c"),
        ("a - b - c", "(a - b) - c"),
    ]
    for loose, tight in pairs:
        assert ast.dump(tree(loose)) == ast.dump(tree(tight)), loose


def test_the_logic_operators_give_1_or_0_over_any_integer():
    fn = compile_expr("(v && phi) + 2*(v || phi) + 4*(!v) + 8*(!!v)", NS)
    assert [fn(a, b, 0) for a, b in ((0, 0), (5, 0), (0, 3), (-2, 7))] == [4, 10, 6, 11]
    assert compile_expr("(v < phi) + (v >= phi)", NS)(3, 3, 0) == 1


@pytest.mark.parametrize(
    "text, v, expected",
    [
        ("~v", 0, -1),
        ("~v & 255", 5, 250),
        ("-v & 255", 1, 255),
        ("v << 4 | 3", 5, 83),
        ("v >> 2", -9, -3),
        ("lo(v)", 0x1234, 0x34),
        ("lo(v)", -1, 255),
        ("hi(v)", 0x1234, 0x12),
        ("hi(v)", 0x12345, 0x23),
        ("u8(v)", 0x1FF, 0xFF),
        ("u16(v)", -1, 0xFFFF),
        ("u16(v)", 0x12345, 0x2345),
        ("sx(v)", 0x7F, 0x7F),
        ("sx(v)", 0x80, 0xFF80),
        ("sx(v)", 0x1FF, 0xFFFF),
        ("sx(sx(v))", 0x80, 0xFF80),
        ("ite(v, 7, 9)", 0, 9),
        ("ite(v, 7, 9)", -3, 7),
        ("ite(v > 2, v*2, -v)", 3, 6),
    ],
)
def test_the_wraps_and_ite_follow_playspec_for_any_integer(text, v, expected):
    assert compile_expr(text, NS)(v, 0, 0) == expected


def test_a_shift_by_a_negative_count_raises_unless_zero():
    with pytest.raises(ValueError):
        compile_expr("v << phi", NS)(1, -1, 0)
    zero = compile_expr("(v << phi) + (v >> phi)*8 + (v << 2)", NS, zero=True)
    assert zero(1, -1, 0) == 4 and zero(8, 2, 0) == 32 + 16 + 32
    assert source("v << 2 >> phi", (), zero=True) == "_shr((v << 2), phi)"
    assert source("v << -1", (), zero=True) == "_shl(v, (-1))"


@pytest.mark.parametrize(
    "text, message",
    [
        ("v and phi", "logic is written"),
        ("v or phi", "logic is written"),
        ("not v", "logic is written"),
        ("v if phi else N", "outside the grammar"),
        ("v / 2", "outside the grammar"),
        ("lo(v, 1)", "takes 1"),
        ("ite(v, 1)", "takes 3"),
        ("sx(1,2)", "takes 1"),
        ("v & & phi", "bad expression"),
        ("v < !phi", "bad expression"),
        ("v @ phi", "outside the grammar"),
        ("+v", "outside the grammar"),
        ("(v < 1) < 2 < 3", "not one comparison"),
    ],
)
def test_other_operator_texts_are_refused(text, message):
    with pytest.raises(ExpressionError, match=message):
        source(text, ["W"])


@pytest.mark.parametrize(
    "text, later",
    [
        ("v + 2*phi - N", False),
        ("(v < 3)*5 + abs((phi >= 2))", False),
        ("min((v == 1),2)", False),
        ("((v != 1))", False),
        ("W[(v == 1)]", False),
        ("F(N + (v <= 2))", False),
        ("v < 3", True),
        ("(v < 3) + (phi < 2 + 1)", False),
        ("min(v < 1,2)", True),
        ("W[v < 1]", True),
        ("F(v > 1)", True),
        ("(v < 3) < 1", True),
        ("v != 3", True),
        ("v & 1", True),
        ("v | 1", True),
        ("v ^ 1", True),
        ("v << 1", True),
        ("v >> 1", True),
        ("~v", True),
        ("!v", True),
        ("v && 1", True),
        ("v || 1", True),
        ("lo(v)", True),
        ("hi(v)", True),
        ("u8(v)", True),
        ("u16(v)", True),
        ("sx(v)", True),
        ("ite(v,1,2)", True),
    ],
)
def test_an_expression_is_format_2_5_where_it_has_what_2_4_lacked(text, later):
    """The text's answer and its parse tree's are one: both are checked against the document's
    format by its version line."""
    assert expr.later(text) is later
    (found,) = _expressions(text)
    assert expr.later(found) is later
