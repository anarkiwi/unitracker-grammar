"""Modulator expressions: checked, printed in their one text and compiled to Python.

Integer literals, ``+ - *``, ``//`` (floor division), ``%`` (floor modulo), the bitwise ``| ^ &
<< >> ~``, the comparisons ``== != < <= > >=`` and the logic ``&& || !`` (each 1 or 0, the logic
over any integer, 0 false), ``abs``, ``min``, ``max``, the wraps ``lo`` ``hi`` ``u8`` ``u16``
``sx``, ``ite(c,a,b)``, ``v``, ``phi``, ``N`` (the sounding note), ``n`` (the event note), ``F(k)``
(the frequency of note k) and ``T[k]`` for a named table ``T``; a template also reads named
parameters, lowercase names :func:`bind` replaces with integers. The operators have playspec's
precedence, from the loosest ``||``, ``&&``, ``!``, a comparison, ``|``, ``^``, ``&``, the shifts,
``+ -``, ``* // %``, to the unary ``~`` and ``-``. An expression is a stdlib :mod:`ast` node,
read from a text by :func:`tree` or from a canonical parse tree by :class:`Nodes`.
"""

import ast
import copy
import functools
import re

from lark import Token, Transformer, Tree

NAMES = ("v", "phi", "N", "n")
CALLS = {
    "abs": 1,
    "min": 2,
    "max": 2,
    "F": 1,
    "lo": 1,
    "hi": 1,
    "u8": 1,
    "u16": 1,
    "sx": 1,
    "ite": 3,
}
_CALLED = {"F": "_F"}
_WRAPS = {
    "lo": "({0} & 255)",
    "u8": "({0} & 255)",
    "hi": "(({0} >> 8) & 255)",
    "u16": "({0} & 65535)",
    "sx": "((_b := {0} & 255) | 65280 * (_b >> 7))",
    "ite": "({1} if {0} else {2})",
}
_BINARY = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.FloorDiv: "//", ast.Mod: "%"}
_BITWISE = {ast.BitOr: "|", ast.BitXor: "^", ast.BitAnd: "&"}
_SHIFT = {ast.LShift: "<<", ast.RShift: ">>"}
_COMPARE = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
_OPERATOR = {text: op for op, text in (_BINARY | _BITWISE | _SHIFT | _COMPARE).items()}
_OPERATORS = _BINARY | _BITWISE | _SHIFT
_UNARY = {ast.USub: "(-{})", ast.Invert: "(~{})", ast.Not: "(0 if {} else 1)"}
_GUARDED = {"//": "_div", "%": "_mod", "<<": "_shl", ">>": "_shr"}
_PARAMS = "v, phi, N, n=0"
_ATOMS = ("V", "PHI", "N", "EVENT_NOTE")
_LOGIC = re.compile(r"&&|\|\||!(?!=)")
_PYTHONIC = re.compile(r"\b(?:and|or|not)\b")
_SPELLED = {"&&": " and ", "||": " or ", "!": " not "}
_LATER_TOKENS = frozenset("OR AND NOT BOR BXOR BAND SHIFT INVERT LO HI U8 U16 SX ITE".split())
_LATER_TEXT = re.compile(r"[|^&~]|<<|>>|!(?!=)|\b(?:lo|hi|u8|u16|sx|ite)\(")
_COMPARING = re.compile(r"[()\[\]]|[=!<>]=|[<>]")


class ExpressionError(ValueError):
    """A text is not an expression of the modulator grammar."""


def later(node) -> bool:
    """Whether the expression of ``node``, a parse tree, or of text ``node`` is format 2.5's: it
    has an operator or function format 2.4 lacked, or a comparison not in parentheses of its own
    (``(a < b)`` is 2.4's, in parentheses that hold nothing else)."""
    if isinstance(node, str):
        return _later_text(node)
    stack = [(node, None, None)]
    while stack:
        found, parent, grand = stack.pop()
        if found.data == "cmp" and not _grouped(parent, grand):
            return True
        for child in found.children:
            if isinstance(child, Tree):
                stack.append((child, found, parent))
            elif child.type in _LATER_TOKENS:
                return True
    return False


def _grouped(parent, grand) -> bool:
    """Whether a comparison under ``parent`` and ``grand`` is the whole content of a pair of
    parentheses (an ``expr`` in a ``factor`` that holds nothing else)."""
    return (
        parent is not None
        and parent.data == "expr"
        and grand is not None
        and grand.data == "factor"
        and not isinstance(grand.children[0], Token)
    )


def _later_text(text: str) -> bool:
    """:func:`later` of an expression text."""
    if _LATER_TEXT.search(text):
        return True
    groups = []
    for found in _COMPARING.finditer(text):
        sign = found[0]
        if sign in "([":
            before = text[: found.start()][-1:]
            grouping = sign == "(" and not (before.isalnum() or before == "_")
            groups.append("g" if grouping else sign)
        elif sign in ")]":
            groups.pop()
        elif not groups or groups[-1] != "g":
            return True
    return False


def written(text: str):
    """The written value of an expression text: an integer literal as an int."""
    try:
        return int(text)
    except ValueError:
        return text


def _python(node, tables, zero: bool) -> str:
    """Python source of a parsed expression reading ``tables`` (see :func:`source`)."""
    # pylint: disable=too-many-return-statements,too-many-branches
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    ):
        return str(node.value)
    if isinstance(node, ast.Name):
        if node.id not in NAMES:
            raise ExpressionError(f"unbound parameter {node.id!r}")
        return node.id
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)].format(_python(node.operand, tables, zero))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _binary(node, tables, zero)
    if isinstance(node, ast.BoolOp):
        join = " and " if isinstance(node.op, ast.And) else " or "
        return f"(1 if {join.join(_python(v, tables, zero) for v in node.values)} else 0)"
    if isinstance(node, ast.Compare):
        return _comparison(node, tables, zero)
    if isinstance(node, ast.List):
        raise ExpressionError(f"{ast.unparse(node)!r} is outside the grammar")
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if node.keywords or name not in CALLS:
            raise ExpressionError(f"{ast.unparse(node)!r} calls no grammar function")
        if len(node.args) != CALLS[name]:
            raise ExpressionError(f"{name} takes {CALLS[name]} argument(s)")
        args = [_python(a, tables, zero) for a in node.args]
        if name in _WRAPS:
            return _WRAPS[name].format(*args)
        return f"{_CALLED.get(name, name)}({', '.join(args)})"
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        name = node.value.id
        if name not in tables:
            raise ExpressionError(f"unknown table {name!r}")
        return f"_T[{name!r}]({_python(node.slice, tables, zero)})"
    raise ExpressionError(f"{ast.unparse(node)!r} is outside the grammar")


def _binary(node, tables, zero: bool) -> str:
    """One binary operation; with ``zero``, ``//`` and ``%`` by a divisor and a shift by a count
    that is no literal of a safe sign call a guard returning 0."""
    op = _OPERATORS[type(node.op)]
    left, right = _python(node.left, tables, zero), _python(node.right, tables, zero)
    if zero and op in _GUARDED and not _unguarded(op, node.right):
        return f"{_GUARDED[op]}({left}, {right})"
    return f"({left} {op} {right})"


def _unguarded(op: str, right) -> bool:
    """Whether a literal ``right`` makes ``op`` total: a divisor of 1 or more in absolute value,
    a shift count of 0 or more."""
    if not isinstance(right, ast.Constant):
        return False
    return right.value != 0 if op in ("//", "%") else right.value >= 0


def _comparison(node, tables, zero: bool) -> str:
    """One comparison, 1 when it holds, else 0."""
    if len(node.ops) != 1:
        raise ExpressionError(f"({ast.unparse(node)}) is not one comparison")
    op = _COMPARE.get(type(node.ops[0]))
    if op is None:
        raise ExpressionError(f"({ast.unparse(node)}) compares with no grammar operator")
    left, right = _python(node.left, tables, zero), _python(node.comparators[0], tables, zero)
    return f"(1 if {left} {op} {right} else 0)"


def tree(text: str) -> ast.expr:
    """The node of an expression text, unchecked: ``&&``, ``||`` and ``!`` are read as Python's
    ``and``, ``or`` and ``not`` of the same precedence."""
    if _PYTHONIC.search(text):
        raise ExpressionError(f"bad expression {text!r}: logic is written && || !")
    try:
        return ast.parse(_LOGIC.sub(lambda m: _SPELLED[m[0]], text).strip(), mode="eval").body
    except SyntaxError as exc:
        raise ExpressionError(f"bad expression {text!r}: {exc.msg}") from exc


def source(expr: str | ast.expr, tables=(), zero: bool = False) -> str:
    """Python source over ``v``, ``phi``, ``N``, ``n``, ``_F`` and ``_T`` of an expression text or
    node; ``zero``: ``//`` and ``%`` by a divisor that is no nonzero literal call ``_div`` and
    ``_mod``, 0 by a divisor of 0, and a shift by a count that is no literal of 0 or more call
    ``_shl`` and ``_shr``, 0 by a negative count; else they raise ZeroDivisionError and
    ValueError."""
    return _python(tree(expr) if isinstance(expr, str) else expr, set(tables), zero)


def canonical(text: str) -> str:
    """The one text of expression ``text`` (see :func:`printed`)."""
    return printed(tree(text))


def printed(node) -> str:
    """The one text of expression node ``node``: sums and products as linear forms (constant
    terms and factors folded, like terms merged), the operands of ``|``, ``^``, ``&``, ``&&``,
    ``||`` in one order, terms in one order, parentheses only where the
    precedence needs them, and decimal literals."""
    return _text(node, 0)


_LEVELS = {ast.Or: 0, ast.And: 1, ast.Not: 2, ast.Compare: 3, ast.BitOr: 4, ast.BitXor: 5}
_LEVELS |= {ast.BitAnd: 6, ast.LShift: 7, ast.RShift: 7}
_LOGICAL = {ast.Or: " || ", ast.And: " && "}
_CHAINED = {ast.BitOr: " | ", ast.BitXor: " ^ ", ast.BitAnd: " & "}
_SUMMED = 8


def _text(node, prec: int) -> str:
    """The text of ``node``, in parentheses where it binds looser than level ``prec``."""
    wide = _wide(node)
    level, text = wide if wide else (_SUMMED, _sum(*_linear(node)))
    return f"({text})" if level < prec else text


def _flatten(node) -> list:
    """The operands of a chain of ``node``'s operator, nested ones included."""
    operands = node.values if isinstance(node, ast.BoolOp) else [node.left, node.right]
    out = []
    for operand in operands:
        same = isinstance(operand, type(node)) and type(operand.op) is type(node.op)
        out += _flatten(operand) if same else [operand]
    return out


def _wide(node) -> tuple[int, str] | None:
    """``(level, text)`` of a logic, comparison, bitwise or shift node, None for another."""
    # pylint: disable=too-many-return-statements
    if isinstance(node, ast.BoolOp):
        op = type(node.op)
        texts = [_text(v, _LEVELS[op] + 1) for v in _flatten(node)]
        return _LEVELS[op], _LOGICAL[op].join(sorted(texts, key=_order))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _LEVELS[ast.Not], "!" + _tight(node.operand, ast.Not)
    if isinstance(node, ast.Compare):
        op = _COMPARE[type(node.ops[0])]
        left, right = _text(node.left, 4), _text(node.comparators[0], 4)
        return _LEVELS[ast.Compare], f"{left} {op} {right}"
    if isinstance(node, ast.BinOp) and type(node.op) in _BITWISE:
        op = type(node.op)
        texts = [_text(v, _LEVELS[op] + 1) for v in _flatten(node)]
        return _LEVELS[op], f" {_BITWISE[op]} ".join(sorted(texts, key=_order))
    if isinstance(node, ast.BinOp) and type(node.op) in _SHIFT:
        level = _LEVELS[type(node.op)]
        left, right = _text(node.left, level), _text(node.right, level + 1)
        return level, f"{left} {_SHIFT[type(node.op)]} {right}"
    return None


def _linear(node) -> tuple[int, dict]:
    """``(constant, {factors: coefficient})`` of ``node`` as a sum of products."""
    if isinstance(node, ast.Constant):
        return int(node.value), {}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        const, terms = _linear(node.operand)
        return -const, {f: -c for f, c in terms.items()}
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        sign = 1 if isinstance(node.op, ast.Add) else -1
        (a, at), (b, bt) = _linear(node.left), _linear(node.right)
        terms = dict(at)
        for f, c in bt.items():
            terms[f] = terms.get(f, 0) + sign * c
        return a + sign * b, {f: c for f, c in terms.items() if c}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _product(_linear(node.left), _linear(node.right))
    return 0, {(_factor(node),): 1}


def _product(left: tuple, right: tuple) -> tuple[int, dict]:
    (a, at), (b, bt) = left, right
    if not at or not bt:
        const, terms, k = (b, bt, a) if not at else (a, at, b)
        return const * k, {f: c * k for f, c in terms.items() if c * k}
    factors = []
    coef = 1
    for const, terms in (left, right):
        if not const and len(terms) == 1:
            ((f, c),) = terms.items()
            factors += f
            coef *= c
        else:
            factors.append(f"({_sum(const, terms)})")
    return 0, {tuple(sorted(factors, key=_order)): coef}


def _factor(node) -> str:
    """The text of a node that is no sum or product, as a factor."""
    # pylint: disable=too-many-return-statements
    if isinstance(node, ast.Name):
        return node.id
    if wide := _wide(node):
        return f"({wide[1]})"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
        return "~" + _tight(node.operand)
    if isinstance(node, ast.Call):
        args = [printed(a) for a in node.args]
        if node.func.id in ("min", "max"):
            args.sort(key=_order)
        return f"{node.func.id}({','.join(args)})"
    if isinstance(node, ast.Subscript):
        return f"{node.value.id}[{printed(node.slice)}]"
    if isinstance(node, ast.BinOp):
        left, right = _linear(node.left), _linear(node.right)
        return f"{_operand(*left, True)} {_BINARY[type(node.op)]} {_operand(*right)}"
    raise ExpressionError(f"{ast.unparse(node)!r} is outside the grammar")


def _tight(node, *prefixes) -> str:
    """The text of the operand of the prefix operator ``~`` (or ``!``, with ``ast.Not`` among
    ``prefixes``): an atom, a call or another prefix operation, else parenthesised."""
    text = _text(node, 0)
    prefixed = isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Invert, *prefixes))
    atom = isinstance(node, (ast.Name, ast.Call, ast.Subscript)) or prefixed
    atom = atom or isinstance(node, ast.Constant) and node.value >= 0
    return text if atom else f"({text})"


def _operand(const: int, terms: dict, left: bool = False) -> str:
    """An operand of ``%`` or ``//``: a term on the left, a factor on the right."""
    text = _sum(const, terms)
    if not terms or (len(terms) == 1 and not const and (left or _atomic(terms))):
        return text
    return f"({text})"


def _sum(const: int, terms: dict) -> str:
    out = []
    for factors, coef in sorted(terms.items(), key=lambda t: _order("*".join(t[0]))):
        body = "*".join(
            f"({f})" if _divides(f) and (len(factors) > 1 or abs(coef) != 1) else f for f in factors
        )
        if abs(coef) != 1:
            body = f"{abs(coef)}*{body}"
        if not out:
            lead = "-" if coef < 0 else ""
            if coef == -1 and len(factors) == 1 and _divides(factors[0]):
                body = f"({body})"
            out.append(lead + body)
        else:
            out.append((" - " if coef < 0 else " + ") + body)
    if const or not out:
        out.append(str(const) if not out else (" - " if const < 0 else " + ") + str(abs(const)))
    return "".join(out)


def _divides(factor: str) -> bool:
    """Whether a factor's text is a ``%`` or ``//`` at its top level."""
    depth = 0
    for k, ch in enumerate(factor):
        depth += {"(": 1, "[": 1, ")": -1, "]": -1}.get(ch, 0)
        if not depth and factor[k : k + 3] in (" % ", " //"):
            return True
    return False


def _atomic(terms: dict) -> bool:
    ((factors, coef),) = terms.items()
    return coef == 1 and len(factors) == 1 and not _divides(factors[0])


def _order(text: str) -> tuple:
    """The order of terms and factors: integers, names, then the rest, each by its text."""
    return (0 if text.lstrip("-").isdigit() else 1 if text in NAMES else 2, text)


def _div(a: int, b: int) -> int:
    return a // b if b else 0


def _mod(a: int, b: int) -> int:
    return a % b if b else 0


def _shl(a: int, b: int) -> int:
    return a << b if b >= 0 else 0


def _shr(a: int, b: int) -> int:
    return a >> b if b >= 0 else 0


def compile_expr(expr: str | ast.expr, namespace: dict, zero: bool = False):
    """A function ``(v, phi, N, n=0) -> int`` of an expression text or node (``zero`` as in
    :func:`source`).

    ``namespace``, the function's globals, holds ``_F(k)``, the frequency of format note k, and
    ``_T``, each named table's function of its index.
    """
    body = source(expr, namespace["_T"], zero)
    if zero:
        guards = "_div, _mod, _shl, _shr"
        # pylint: disable-next=eval-used
        return eval(f"lambda {guards}: lambda {_PARAMS}: {body}", namespace)(_div, _mod, _shl, _shr)
    return eval(f"lambda {_PARAMS}: {body}", namespace)  # pylint: disable=eval-used


def _named(node) -> list:
    """The parameter nodes of an expression node: its names but ``v``, ``phi``, ``N``, ``n`` and
    the names of its calls and tables."""
    skip = {id(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)}
    skip |= {id(n.value) for n in ast.walk(node) if isinstance(n, ast.Subscript)}
    return [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Name) and n.id not in NAMES and id(n) not in skip
    ]


def params(node) -> set[str]:
    """The names of the parameters a template node reads."""
    return {n.id for n in _named(node)}


def bind(node, values: dict) -> ast.expr:
    """Template node ``node`` with each parameter replaced by its integer in ``values``, which
    names each parameter and no other."""
    node = copy.deepcopy(node)
    named = _named(node)
    names = {n.id for n in named}
    if names != set(values):
        missing, extra = sorted(names - set(values)), sorted(set(values) - names)
        raise ExpressionError(f"parameters: missing {missing}, unknown {extra}")
    ids = {id(n) for n in named}

    class _Bind(ast.NodeTransformer):
        def visit_Name(self, name):  # pylint: disable=invalid-name,missing-function-docstring
            return ast.Constant(values[name.id]) if id(name) in ids else name

    return _Bind().visit(node)


def _at(values: tuple, k: int) -> int:
    return values[k] if 0 <= k < len(values) else 0


def indexed(values) -> functools.partial:
    """A table's function of its index: ``values[k]``, 0 outside them."""
    return functools.partial(_at, tuple(values))


class Nodes(Transformer):
    """The expressions of a canonical parse tree (rules ``fexpr``, ``expr`` and the rules of its
    operators down to ``factor``) as nodes; ``-`` before a literal is a negative literal."""

    # pylint: disable=missing-function-docstring

    def fexpr(self, children):
        return children[0]

    def _chain(self, children):
        out = children[0]
        for op, operand in zip(children[1::2], children[2::2]):
            out = ast.BinOp(out, _OPERATOR[op.strip()](), operand)
        return out

    term = sum = shift = band = bxor = bor = _chain

    def _logic(self, children):
        if len(children) == 1:
            return children[0]
        return ast.BoolOp(ast.Or() if children[1].strip() == "||" else ast.And(), children[::2])

    expr = land = _logic

    def lnot(self, children):
        return ast.UnaryOp(ast.Not(), children[1])

    def cmp(self, children):
        return ast.Compare(children[0], [_OPERATOR[children[1].strip()]()], [children[2]])

    def factor(self, children):
        # pylint: disable=too-many-return-statements
        head, *rest = children
        if not isinstance(head, Token):
            return head
        if head.type in ("INT", "SIGNED"):
            return ast.Constant(int(head))
        if head.type in _ATOMS or head.type == "PARAM":
            return ast.Name(str(head))
        if head.type == "XTABLE":
            return ast.Subscript(ast.Name(str(head)), rest[0])
        if head.type == "NEG":
            (inner,) = rest
            if isinstance(inner, ast.Constant):
                return ast.Constant(-inner.value)
            return ast.UnaryOp(ast.USub(), inner)
        if head.type == "INVERT":
            return ast.UnaryOp(ast.Invert(), rest[0])
        return ast.Call(ast.Name(head[:-1]), rest, [])
