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
(`order: [events, ctrl, pulse, filter, freq, pw, cut, read]`). Format 1.23's `state` line,
after `order`, declares per cell its state variables and their sizes in bytes
(`state: {freq: {t: 1}, pw: {r: 1, q: 2}}`), a copy per voice (one for `cut`), 0 at tick 0, which
only code templates read and write; a `mod` record may be a code block (`vib: |`, then a
statement per line at the record's indentation plus 2) instead of an expression. Its templates
stand in one top-level `mod:` section after `tables:` and before `init`, records at 2 spaces and
code lines at 4, each keyed by its signature (`  vib(l, c, s): |`, `  walk(s): v + s`,
`  note(): F(N)`; parameters separated by `, `); a call binds one wherever a cell is bound, its
integer arguments in the signature's order without spaces (`pw: walk(-2)`,
`!tick.freq:vib(0,4,64)`, `slots: {freq: {base: {mod: note()}}}`). The grammar admits every
version's forms (a row's `mod:` records may also be keyed by a signature): which a version plays
is the player's to say. Format 1.21's
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

## Code templates

`unitracker_grammar.code` owns format 1.23's code templates: NMOS 6502 routines but `brk`, `jsr`
and `rti`, with no indirect modes and no comments, that end in `rts`. A routine is a tuple of
statements, each a `Label(name)` or an `Op(mnemonic, mode, operand)`: `mode` is `implied`
(`lsr` bare is the accumulator's), `immediate` (`Imm(value, byte)`: `#7`, `#p`, `#<p`, `#>p`),
`memory`, `memory,x` or `memory,y` (`Mem(symbol, offset, index)`: `v`, `v+1`, `G.lo+3,x`), or
`label` (a branch's or `jmp`'s label name).

```python
from unitracker_grammar import code, parse
ops = code.read("lda #c\nsta v\nrts\n")   # checked statements, or CodeError
code.printed(ops)                          # 'lda #c\nsta v\nrts\n', its one text
code.params(ops), code.symbols(ops)        # ('c',), ('v',): in first-use order
code.templates(parse(text))                # {name: statements} of a document's code blocks
code.state(parse(text))                    # {cell: ((name, size), ...)} of its state line
```

Memory symbols are `v` (2 bytes: in, the value before the slot; out, the modulator's value),
`phi` (2, φ mod 65536, read-only), `nn` and `ne` (the low bytes of `N` and `n`), the state
variables of the template's cell, and `T.lo` / `T.hi` (each entry's low and high byte) for a table
`T`. A code slot fires where an expression would: `v`, `phi`, `nn`, `ne` and the voice's copy of
its cell's state are set, A, X, Y and the flags (but I) are 0, and the routine runs to an `rts`
on an empty stack, within 4096 instructions; `v` wrapped to the cell's width is its value and the
state is stored back. A symbol that is none of these, or a state variable of another cell, is
refused when the template is bound. `F.lo` / `F.hi` are the note table's bytes, entry k those
of `frequency(k, clock_hz)` for k 0-255.

```python
code.signature("vib(l, c, s)")            # ('vib', ('l', 'c', 's')), CodeError on a repeat
code.declare("vib(c)", ("c",), {"t"})      # the signature, if it declares what the body reads
code.call("vib(0,-4,32)")                  # Call(name='vib', args=(0, -4, 32))
code.signatures(parse(text))               # {name: parameters} of its signed templates, checked
```

In the parse tree a signed record's key is a `SIGNATURE` token (`vib(l, c, s)`) where a plain
one's is a `NAME`, a call is one `CALL` token (`vib(0,-4,32)`) where a binding may be a name or
an expression, and the top-level section is a `mods` tree of `SIGNATURE` tokens each followed by
its `expr` or `code` tree; `code.templates` keys each by its bare name.

## Grammar

[`src/unitracker_grammar/canonical.lark`](src/unitracker_grammar/canonical.lark); the document
format and the meaning of each construct are described in unitracker's
[docs/format](https://github.com/anarkiwi/unitracker/blob/main/docs/format/document.md).
