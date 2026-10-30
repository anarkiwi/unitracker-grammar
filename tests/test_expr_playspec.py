"""The expression language against playspec's: the same texts, evaluated by this package and by
pysidtracker's spec elaborator and executor, give the same 16-bit results over random operands."""

import numpy as np
import pytest

from unitracker_grammar import frequency
from unitracker_grammar.expr import compile_expr

playspec = pytest.importorskip("pysidtracker.playspec")
pyexec = pytest.importorskip("pysidtracker.playspec.pyexec")

OPERANDS = ("v", "phi", "N", "n")
IN, OUT, TRIALS = 0x1000, 0x1100, 300
WRAPPING = [
    "v + phi",
    "v - phi",
    "v * phi",
    "-v",
    "~v",
    "v & phi",
    "v | phi",
    "v ^ phi",
    "v << 3",
    "(v << 3) | (phi & 7)",
    "v ^ phi & 15 | N",
    "v | phi & N ^ n",
    "~v & 255",
    "~v + 1 & 65535",
    "v + phi << 2 & 255",
    "lo(v)",
    "hi(v)",
    "lo(v) | hi(phi)",
    "hi(v * phi)",
    "u16(v ^ phi)",
    "lo(v + phi) ^ hi(v - phi)",
    "(v & 255) << 8 | hi(phi)",
    "1 << 2 + 1",
    "v - -phi",
]
ORDERED = [
    "v >> 2",
    "(v + phi) >> 1",
    "v >> 1 << 1",
    "v < phi",
    "v <= phi",
    "v > phi",
    "v >= phi",
    "v == phi",
    "v != phi",
    "ite(v < phi, v, phi)",
    "ite(v == phi, 1, v - phi)",
    "ite(v & 1 == 0, v >> 1, v * 3 + 1)",
    "v | phi == 3",
    "v & 1 == 0",
    "v < phi && N != n",
    "v < phi || N == n",
    "!(v < phi)",
    "!(v < phi) && (N >= n || v == 0)",
    "v < phi && N < n || v == phi",
    "v < phi || N < n && v == phi",
    "(v < phi) == (N < n)",
    "sx(lo(v))",
    "sx(lo(v)) + 1",
    "sx(lo(v + 100)) >> 4",
    "u8(v < 3)",
    "u16(v < phi) + 2",
    "u16(!(v < phi)) | N",
]
STATIC = [("17 // 5 + 17 % 5", "17 / 5 + 17 % 5"), ("v + 100 // 7 % 4", "v + 100 / 7 % 4")]


def spec_of(texts: list) -> str:
    cells = "".join(f"cell {x}: u16 @ L.a + {2 * i};\n" for i, x in enumerate(OPERANDS))
    outs = "".join(f"cell o{k}: u16 @ L.a + {0x100 + 2 * k};\n" for k in range(len(texts)))
    body = "".join(f"o{k} := u16({t});\n" for k, t in enumerate(texts))
    head = "spec t;\nlayout { a: addr; }\n"
    return f"{head}{cells}{outs}machine m {{ step {{ {body} }} }}\nschedule {{ m; }}\n"


def results_of(texts: list, operands: np.ndarray) -> np.ndarray:
    """The spec player's 16-bit result of each text, per row of ``operands``."""
    program = playspec.elaborate(playspec.parse(spec_of(texts)), {"a": IN})
    frame = pyexec.compile_program(program)
    out = np.empty((len(operands), len(texts)), dtype=np.uint16)
    for row, values in enumerate(operands):
        memory = bytearray(0x10000)
        memory[IN : IN + 8] = values.astype("<u2").tobytes()
        frame(memory.__getitem__, memory.__setitem__, pyexec.controls(program), None, {})
        out[row] = np.frombuffer(memory, dtype="<u2", count=len(texts), offset=OUT)
    return out


def ours(text: str, operands: np.ndarray) -> np.ndarray:
    fn = compile_expr(text, {"_F": frequency, "_T": {}})
    return np.array([fn(*map(int, row)) & 0xFFFF for row in operands], dtype=np.uint16)


@pytest.mark.parametrize(
    "texts, high",
    [(WRAPPING, 1 << 16), (ORDERED, 1 << 8)],
    ids=["wrapping over u16", "ordered over u8"],
)
def test_the_same_text_has_the_same_result_in_unitracker_and_playspec(texts, high):
    operands = np.random.default_rng(25).integers(0, high, (TRIALS, len(OPERANDS)))
    theirs = results_of(texts, operands)
    wrong = [t for k, t in enumerate(texts) if not (ours(t, operands) == theirs[:, k]).all()]
    assert not wrong


def test_division_and_modulo_agree_where_playspec_has_them_static():
    """Playspec's ``/`` and ``%`` take static operands and floor; ``//`` is its ``/``."""
    operands = np.random.default_rng(7).integers(0, 1 << 8, (20, len(OPERANDS)))
    theirs = results_of([p for _, p in STATIC], operands)
    for k, (text, _) in enumerate(STATIC):
        assert (ours(text, operands) == theirs[:, k]).all()
