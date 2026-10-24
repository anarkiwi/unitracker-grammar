# unitracker-grammar

The canonical [unitracker](https://github.com/anarkiwi/unitracker) document as a
[Lark](https://github.com/lark-parser/lark) grammar, with an LALR parser for it and the note
table its expressions read as `F(k)`, and the modulator expression language: checked, printed
in its one text and compiled to Python.

A document names no player. It holds everything it plays: instruments, programs, expressions,
code, phrases and the tables they index. Its only constants are the note table at its clock and
the header defaults (PAL clock, 3 voices, tempo 6). The grammar is format 2.0's, and refuses
every other version.

After `meta`, each optional and in this order: `clock`, `voices`, `tempo`; `slots`, per cell
its modulator slots in firing order, each with its default binding and the events it holds and
resets on (`slots: {freq: {wave: {mod: note(), reset: [row.note]}, tick: {hold: [step-1, row]}}}`);
`order`, the phases of a tick (`order: [events, ctrl, pulse, filter, freq, pw, cut, read]`);
`state`, per cell its state variables and their sizes in bytes (`state: {freq: {t: 1}, pw: {r: 1,
q: 2}}`); `regs`, the 25 SID registers' values before tick 0 (`regs: [0, 0, ..., 15]`); `tables`; then the definitions that are not song content, each kind a top-level
section with records at 2 spaces: `mod:` (templates keyed by their signature, an expression or a
code block at 4 spaces: `vib(l, c, s): |`, `walk(s): v + s`, `note(): F(N)`), `restart:`,
`ins:`, `ctrl:`, `pw:`, `filter:`; then `init`, and `song:`, whose rows' `def:` holds their
phrases. A `slot.` prefix on a cell's row key, instrument field or command (`tick.freq: vib(0,4,
64)`, `!tick.freq:none`) names the slot it binds or stops; a call binds a template wherever a cell
is bound, its integer arguments in the signature's order without spaces. A modulated cell's
stops are `none`, `hold` and `reset` (φ back to 0, the binding kept), as a row key's value and a
command (`{pw: ptab(3), pw: reset}`, `!pw:ptab(3)!pw:reset`); a cell's keys may repeat, and the
model keeps them in the order written.

A program record (`restart`, `ctrl`, `pw`, `filter`) may be a template keyed by its signature
(`arp(a, b): [{ctrl: 65, note: +a}, {wait: a, note: -b}, {loop: 0}]`), its rows reading its
parameters where they take an integer, as a relative note (`+a`, `-a`), as a cell value alone
(`pw: b`) and as a call's argument (`pw: walk(b)`); a call binds it wherever a program's name
stands (`ctrl: arp(7,4)`, `restart: hr(2,9,220)`, `run: arp(7,4)`, `!run:arp(7,4)`), its
section giving its kind. Any definition may also stand inline at its use: a program after its
kind in `run:` and `!run:` (`run: pw[{pw: 5}, end]`), an instrument after an event's note
(`C4.{ad: 9, sr: 240}`), a phrase with its transpose in a play entry (`play: [[C4, -*3]+2, ~]`)
and, wherever a cell is bound, an anonymous code body (`asm{lda v; up:; adc #1; sta v; bne up;
rts}`); a command and a slot's default also bind a quoted expression (`!pw:'v + 40'`). What each
construct plays is unitracker-player's
[semantics](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md).

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

`unitracker_grammar.code` owns the code templates: NMOS 6502 routines but `brk`, `jsr`
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
code.inline(code.read("lda v\nrts\n"))     # 'asm{lda v; rts}', an anonymous body's one text
code.signatures(parse(text))               # {name: parameters} of its signed templates, checked
code.programs(parse(text))                 # {name: (kind, parameters)} of its program templates
```

`code.programs` checks a document's program templates: each signature declares exactly what
its rows read (`code.program_reads(body, declared)`, in first-use order), a program keyed by its
name and everything outside the program records read no parameter, a parameter is never part of
a larger cell expression nor read by an inline program, and no name is two templates', of
programs or modulators. `code.call` reads a parameter argument as its name
(`call("pt(b,2)")` is `Call("pt", ("b", 2))`).

In the parse tree each definition section is a `def_KIND` tree (`def_mod`, `def_restart`,
`def_ins`, `def_ctrl`, `def_pw`, `def_filter`, `def_phrase`) of key tokens each followed by its
value: a template's key a `SIGNATURE` token and its value an `expr` or `code` tree, a program
template's a `PROGRAM_SIG`. A call is one `CALL` token (`vib(0,-4,32)`), a parameter a row reads
a `PARAM` (a `REL_PARAM`, `+a`, in a note) outside any `factor`, an inline program a
`run_program` (a `PROGRAM_KIND` token, then its `program`), an inline instrument an
`instrument` where an `INS` token may stand, an inline phrase a `phrase` where a `PHRASE` token
may, an anonymous body an `asm` tree of `code_*` statements (`code.Statements` reads it as a
`code`), and a command's quoted expression an `fexpr`.

## Documents

`unitracker_grammar.document` is the document as typed, frozen dataclasses: `read` builds one from
a text, its classes build one directly, and `printed` writes its one canonical text, so
`printed(read(text)) == text` and `read(printed(doc)) == doc`.

```python
from unitracker_grammar.document import (
    Call, Code, Document, Event, Expr, Header, Instrument, Play, Program, Signed, Slot, SongRow,
    printed, read, replace, signature,
)
vib = Code.of("lda v\nclc\nadc #c\nsta v\nrts")              # checked statements
doc = Document(
    Header(meta={"title": "T", "author": "A"}, slots={"freq": [Slot("wave", Call("note")), Slot("tick")]}),
    mods=[(signature("vib", ["c"]), vib), ("note()", Expr("F(N)"))],
    defs={"ins": [("i1", Instrument({"ad": 9, "sr": 240, "ctrl": Program([{"ctrl": 65}])}))]},
    rows=[SongRow(
        [Play("p1"), Play("p1", Signed(12)), "~"],
        {"phrase": [("p1", [Event("C4", "i1", {"tick.freq": Call("vib", (3,))}), Event("-", steps=3)])]},
    )],
    loop=0,
)
text = printed(doc)
doc = replace(doc, loop=None)                                # edits are dataclasses.replace
```

| class | holds |
|---|---|
| `Document(header, tables, mods, defs, init, rows, loop)` | `tables` `{name: ints}`; `mods` the top-level templates `(signature, Expr \| Code)`; `defs` the top-level `restart`, `ins`, `ctrl`, `pw` and `filter` sections (`Section`s, or `{kind: [(name, value)]}`); `init` events or None; `loop` the row it loops to, None for `end` |
| `Header(version, meta, clock, voices, tempo, slots, order, state, regs)` | each line, None where not written; `version` `VERSION`, `"2.0"`; `meta` texts as written (`"'A, B'"` quoted); `slots` `{cell: [Slot]}`, `state` `{cell: [(name, size)]}`; `slot(cell)` its Slots |
| `Slot(name, mod, hold, reset)` | a slot's default binding and its events (`"note-1"`, `"row.freq"`) |
| `SongRow(play, defs)` | play entries (`Play(phrase, transpose)`, `"~"`, `"end"`; a phrase is a name or inline events) and its `phrase` Section |
| `Section(kind, records)` | `(name, value)` records of one kind; a template's name is its `signature` (`arp(a, b)`), its rows reading parameters as strings (`ad: "a"`, `note: "+a"`, `Call("walk", ("b",))`) |
| `Instrument(fields)`, `Row(keys)` | `{key: value}`, `slot.key` for a slot's, kept in the grammar's order |
| `Program(rows, loop)` | Rows (or dicts), then `end` (`loop` None) or `{loop: k}` |
| `Event(note, ins, commands, keep_pw, keep_filter, steps)` | `ins` a name or an Instrument; commands `{key: value}`, `("legato", True)`; `steps` the `*k` |
| `Expr(text)`, `Call(name, args)`, `Code(statements)` | an expression, a call, a routine (an `asm{...}` body where it binds) |
| `Run(kind, program)` | an inline program after its kind in `run:` or `!run:` |
| `Signed` | an int written with its sign: `note: +0`, a transpose, `!freq:-3` |

A leaf is otherwise an `int` or a `str` as written (a name, a note, `none`, `hold`, `129^8`, `+ 3`).
`printed` wraps flow collections and plain scalars as PyYAML's emitter does at width 100 (a break
before an item, or at a scalar's space, once a line is past the width; continuing at the
collection's indentation, a scalar's 2 deeper) but never the `slots`, `order` and `state`
lines, and quotes an expression in a flow collection that holds a comma, and in a command or a
slot's default always, and nowhere else. That is a document's one canonical text: the grammar also admits other
line wraps, which `read` accepts and `printed` writes canonically.

`tests/roundtrip.py` is a pytest plugin that checks every document a test parses is its one
canonical text, `printed(read(text)) == text` (a test marked `noncanonical` reads other spellings);
over unitracker-player's suite: `PYTHONPATH=$GRAMMAR/tests pytest -p roundtrip` in its checkout.
`tools/size.py` measures the grammar and the time to build its parser.

## Grammar

[`src/unitracker_grammar/canonical.lark`](src/unitracker_grammar/canonical.lark); the document
format and the meaning of each construct are described in unitracker's
[docs/format](https://github.com/anarkiwi/unitracker/blob/main/docs/format/document.md).
