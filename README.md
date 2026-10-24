# unitracker-grammar

The canonical [unitracker](https://github.com/anarkiwi/unitracker) document as a
[Lark](https://github.com/lark-parser/lark) grammar, with an LALR parser for it and the note
table its expressions read as `F(k)`, and the modulator expression language: checked, printed
in its one text and compiled to Python.

A document names no player. It holds everything it plays: instruments, programs, expressions,
phrases and the tables its expressions index. Its only constants are the note table at its clock
and the header defaults (PAL clock, 3 voices, tempo 6). Format 1.22's `slots` line names, per
cell, the modulator slots that fire in order, each with its default binding and the voice
events it holds and resets on (`slots: {freq: {wave: {mod: note, reset: [row.note]}, tick:
{hold: [step-1, row]}}}`); its `mod` records are templates over named parameters and its `x`
records instances (`x1: porta {s: 32}`); a `slot.` prefix on a cell's row key, instrument field
or command (`tick.freq: x3`, `!tick.freq:x3`) names the slot it binds or stops; its `order`
line names the phases of a tick in the order they run
(`order: [events, ctrl, pulse, filter, freq, pw, cut, read]`). Format 1.21's
`hold` line names, per cell, the events its modulators hold on (unitracker-player's
[semantics](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md)).

## Install

```sh
pip install "unitracker-grammar @ git+https://github.com/anarkiwi/unitracker-grammar"
```

## Use

```python
from unitracker_grammar import parse, CanonicalError, frequency, table
tree = parse(text)        # a lark.Tree, or CanonicalError naming the line and column
frequency(57)             # F(57): A4 at the PAL clock
table(clock_hz=1022727)   # F(k) for every note whose word fits, from C0, at NTSC
```

`parser()` is the cached `lark.Lark` parser and `GRAMMAR` the grammar file resource.

## Expressions

`unitracker_grammar.expr` owns the modulator expression language. An expression is a stdlib
`ast` node, read from a text by `tree` or from a parse tree's `expr` and `fexpr` rules by the
`Nodes` transformer.

```python
from unitracker_grammar import expr, frequency
expr.canonical("1024 + 16*min(3, φ)")       # '16*min(3, φ) + 1024', its one text
fn = expr.compile_expr("v + W[φ]", {"_F": frequency, "_T": {"W": expr.indexed([1, 2])}})
fn(10, 1, 48)                               # (v, φ, N, n=0) -> 12
```

`v` is the cell's value, `φ` the modulator's tick count, `N` the sounding note and `n` the event
note; a template's other lowercase names are its parameters, which `params` lists and `bind`
replaces with integers. `source` is the Python source of an expression (`ExpressionError` outside the grammar),
`printed` the one text of a node and `written` an integer literal as an int. `//` and `%` raise
`ZeroDivisionError` on a divisor of 0; with `zero=True` they are 0.

## Grammar

[`src/unitracker_grammar/canonical.lark`](src/unitracker_grammar/canonical.lark); the document
format and the meaning of each construct are described in unitracker's
[docs/format](https://github.com/anarkiwi/unitracker/blob/main/docs/format/document.md).
