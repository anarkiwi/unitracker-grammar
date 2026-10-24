# unitracker-grammar

The canonical [unitracker](https://github.com/anarkiwi/unitracker) document as a
[Lark](https://github.com/lark-parser/lark) grammar, with an LALR parser for it and the note
table its expressions read as `F(k)`, and the modulator expression language: checked, printed
in its one text and compiled to Python.

A document names no player. It holds everything it plays: instruments, programs, expressions,
code, phrases and the tables they index. Its only constants are the note table at its clock and
the header defaults (PAL clock, 3 voices, tempo 6). The grammar is format 2.2's, and refuses
every other version.

```text
unitracker:2.2
meta:{title:T,author:A}
mod:
 vib(c):|
	lda v
	clc
	adc #c
	sta v
	rts
ins:
 i1:{ad:9,sr:240,ctrl:[{ctrl:65},end],tick.freq:vib(3)}
phrase:
 p1:[C4.i1,E,g legato*2,-*3,C5 pw:'v + 40',a]
song:
 - play:[p1,p1+12,~]
 - {loop:0}
```

The text: no line wraps, a block line holds its whole value; no space after a key's colon nor a
flow comma; records and song rows indented by one space, a code block's lines by a tab; an
event's commands and flags each introduced by a space (` run:c1`, ` tick.freq:none`,
` legato`, ` pw`). A note is its letter, a sharp's in lower case (`c4` is C#4), and its octave.
In a phrase a note leaves out its octave where it is the previous note's in that phrase (rests,
`off` and `on` between them keep it): `[C4,E,-*2,g,C5]` is C4, E4, G#4, C5. The first note of a
phrase always carries its octave, each phrase (a record, an inline phrase, a first-use one) is
its own context, and a play entry's transpose applies after; `init`'s notes and a program row's
`note:` always carry theirs. `read` also accepts a repeated octave; `printed` leaves it out.

After `meta`, each optional and in this order: `clock` (`{cycles_per_tick:C,clock_hz:H}`,
and `rounding:floor` where the note table's words are rounded down rather than to the nearest),
`voices`, `tempo`; `slots`, per cell its modulator slots in firing order, each with its default
binding and the events it holds and resets on
(`slots:{freq:{wave:{mod:note(),reset:[row.note]},tick:{hold:[step-1,row]}}}`); `order`, the
phases of a tick (`order:[events,ctrl,pulse,filter,freq,pw,cut,read]`); `state`, per cell its
state variables and their sizes in bytes (`state:{freq:{t:1},pw:{r:1,q:2}}`); `regs`, the 25 SID
registers' values before tick 0 (`regs:[0,0,...,15]`); `tables`; then the definitions that are
not song content, each kind a top-level section: `mod:` (templates keyed by their signature, an
expression or a code block: `vib(l,c,s):|`, `walk(s):v + s`, `note():F(N)`), `restart:`,
`ins:`, `ctrl:`, `pw:`, `filter:`, `phrase:`; then `init`, and `song:`, whose rows hold only
their play entries (` - play:[p1,p2+2,~]`). A `slot.` prefix on a cell's row key, instrument
field or command (`tick.freq:vib(0,4,64)`, ` tick.freq:none`) names the slot it binds or stops; a
call binds a template wherever a cell is bound, its integer arguments in the signature's order.
A modulated cell's stops are `none`, `hold` and `reset` (`phi` back to 0, the binding kept), as a
row key's value and a command (`{pw:ptab(3),pw:reset}`, ` pw:ptab(3) pw:reset`); a cell's keys
may repeat, and the model keeps them in the order written.

A `pw` or `filter` record that is one binding is written as that binding (`pw1:ptab(3)`, never
`pw1:[{pw:ptab(3)},end]`). A program record (`restart`, `ctrl`, `pw`, `filter`) may be a
template keyed by its signature (`arp(a,b):[{ctrl:65,note:+a},{wait:a,note:-b},{loop:0}]`), its
rows reading its parameters where they take an integer, as a relative note (`+a`, `-a`), as a
cell value alone (`pw:b`) and as a call's argument (`pw:walk(b)`); a call binds it wherever a
program's name stands (`ctrl:arp(7,4)`, `restart:hr(2,9,220)`, `run:arp(7,4)`,
` run:arp(7,4)`), its section giving its kind. Any definition may also stand inline at its use:
a program after its kind in a row's `run:` and a ` run:` command (`run:pw[{pw:5},end]`), an
instrument after an event's note (`C4.{ad:9,sr:240}`), a phrase with its transpose in a play
entry (`play:[[C4,-*3]+2,~]`) and, wherever a cell is bound, an anonymous code body
(`asm{lda v; up:; adc #1; sta v; bne up; rts}`); a command and a slot's default also bind a
quoted expression (` pw:'v + 40'`).

A named definition may also be written at its first reference instead of in its section, its
name and `=` before its value, and is referenced by name after: an instrument
`C4.i3={ad:9,ctrl:c1=[{ctrl:65},end]}` then `D.i3`, a program `run:c3=[...]`,
`restart:r2=[...]`, `pw:pw2=v + 3`, a phrase `p3=[C4.i3,-*3]+2` in a play entry; a template
its signature and `=` before its body, then its call's arguments: ` tick.freq:vib(c)=asm{...}(4)`,
` pw:walk(s)='v + s'(2)` (an expression body always quoted), a program template
`ctrl:arp(a,b)=[{ctrl:65,note:+a},end](7,4)`, after its kind in a run
(` run:arp(a,b)=ctrl[...](7,4)`), then `vib(3)`, `arp(0,7)`. It is the same definition as in
its section; a section's records are defined throughout, one at its first use from there on: a
reference before it, and a name defined twice, are refused. `document.top_level(doc)` moves every
such definition to its section and `document.first_use(doc)` every definition the song reaches
(from the slots, `init` and the rows, in reading order) to its first reference; the model keeps
each where it is written (`Def(name, value, args)` at a use), so `printed` writes either.

A
modulator's and a program's signature take the same parameter names: lowercase names but `v`,
`phi`, `n`, `nn`, `ne`, `none`, `hold`, `reset` and a record's name (`c1`, `pw2`). A table is
named by a capitalised name but `F` and `N`. A row's control mask is its own key (`{ctrl:65,
mask:8}`), as are the routing's forms (`route:m` sets it, `route_on:m` and `route_off:m` add
and remove this voice's bit and `m`); ` res:r` and ` route:m` set the resonance and the
routing. What each
construct plays is unitracker-player's
[semantics](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md).

## Install

```sh
pip install "unitracker-grammar @ git+https://github.com/anarkiwi/unitracker-grammar"
```

## Use

```python
from unitracker_grammar import parse, CanonicalError, frequency, table
tree = parse(text)        # a checked lark.Tree, or CanonicalError naming the line and column
frequency(57)             # F(57): A4 at the PAL clock
frequency(-24)            # F(-24): C-2, notes below C0 too (0 where the word rounds to 0)
table(clock_hz=1022727)   # F(k) for every note whose word fits, from C0, at NTSC
frequency(57, 985240, "floor")  # F(k) = R(440 * 2**((k - 57)/12) * 2**24 / clock_hz), R round or floor
```

`parse` also checks what the grammar cannot say (`code.check_document`): templates, state
names, anonymous bodies, the tables read, no parameter read outside a template, and a pulse or
filter record of one binding in its short form, raising `CanonicalError`, `CodeError` or
`ExpressionError`. `parser()` is the cached `lark.Lark` parser (trees with positions, unchecked)
and `GRAMMAR` the grammar file resource.

## Expressions

`unitracker_grammar.expr` owns the modulator expression language. An expression is a stdlib
`ast` node, read from a text by `tree` or from a parse tree's `expr` and `fexpr` rules by the
`Nodes` transformer.

```python
from unitracker_grammar import expr, frequency
expr.canonical("1024 + 16*min(3, phi)")     # '16*min(3, phi) + 1024', its one text
fn = expr.compile_expr("v + W[phi]", {"_F": frequency, "_T": {"W": expr.indexed([1, 2])}})
fn(10, 1, 48)                               # (v, phi, N, n=0) -> 12
```

`v` is the cell's value, `phi` the modulator's tick count, `N` the sounding note and `n` the event
note; a template's other lowercase names are its parameters, which `params` lists and `bind`
replaces with integers. `source` is the Python source of an expression (`ExpressionError` outside the grammar),
`printed` the one text of a node and `written` an integer literal as an int. `//` and `%` raise
`ZeroDivisionError` on a divisor of 0; with `zero=True` they are 0.

## Code templates

`unitracker_grammar.code` owns the code templates: NMOS 6502 routines but `brk`, `jsr`
and `rti`, with no indirect modes and no comments, that end in `rts`. A routine is a tuple of
statements, each a `Label(name)` or an `Op(mnemonic, mode, operand)`: `mode` is `implied`
(`lsr` bare is the accumulator's), `immediate` (`Imm(value, byte)`: `#7`, `#p`, `#<p`, `#>p`),
`memory`, `memory,x` or `memory,y` (`Mem(symbol, offset, index)`: `v`, `v+1`, `G.lo+3,x`, and
a negative offset on a table's bytes only, `F.lo-24,y`), or
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
`phi` (2, `phi` mod 65536, read-only), `nn` and `ne` (the low bytes of `N` and `n`), the state
variables of the template's cell, and `T.lo` / `T.hi` (each entry's low and high byte) for a table
`T`. A code slot fires where an expression would: `v`, `phi`, `nn`, `ne` and the voice's copy of
its cell's state are set, A, X, Y and the flags (but I) are 0, and the routine runs to an `rts`
on an empty stack, within 4096 instructions; `v` wrapped to the cell's width is its value and the
state is stored back. A symbol that is none of these, or a state variable of another cell, is
refused when the template is bound. `F.lo` / `F.hi` are the note table's bytes, entry k those
of `frequency(k, clock_hz, rounding)` for k -128-255, so `F.lo-24,y` reads entry y - 24.

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
value: a template's key, a modulator's or a program's, a `SIGNATURE` token and its value an `expr` or
`code` tree. A call is one `CALL` token (`vib(0,-4,32)`), a parameter a row reads
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
    defs={
        "ins": [("i1", Instrument({"ad": 9, "sr": 240, "ctrl": Program([{"ctrl": 65}])}))],
        "phrase": [("p1", [Event("C4", "i1", {"tick.freq": Call("vib", (3,))}), Event("-", steps=3)])],
    },
    rows=[SongRow([Play("p1"), Play("p1", Signed(12)), "~"])],
    loop=0,
)
text = printed(doc)
doc = replace(doc, loop=None)                                # edits are dataclasses.replace
```

| class | holds |
|---|---|
| `Document(header, tables, mods, defs, init, rows, loop)` | `tables` `{name: ints}`; `mods` the templates `(signature, Expr \| Code)`; `defs` the `restart`, `ins`, `ctrl`, `pw`, `filter` and `phrase` sections in that order (`Section`s, or `{kind: [(name, value)]}`); `init` events or None; `rows` SongRows (or play entry lists); `loop` the row it loops to, None for `end` |
| `Header(meta, clock, voices, tempo, slots, order, state, regs)` | each line, None where not written (the version line is always `VERSION`, `"2.2"`); `clock` `(cycles_per_tick, clock_hz)`, or with `"floor"` third; `meta` texts as written (`"'A, B'"` quoted); `slots` `{cell: [Slot]}`, `state` `{cell: [(name, size)]}`; `slot(cell)` its Slots |
| `Slot(name, mod, hold, reset)` | a slot's default binding and its events (`"note-1"`, `"row.freq"`) |
| `SongRow(play)` | play entries (`Play(phrase, transpose)`, `"~"`, `"end"`; a phrase is a name or inline events) |
| `Section(kind, records)` | `(name, value)` records of one kind; a template's name is its `signature` (`arp(a,b)`), its rows reading parameters as strings (`ad: "a"`, `note: "+a"`, `Call("walk", ("b",))`); a `pw` or `filter` record `Program([{"pw": b}])` (`cut` for `filter`) is stored as `b` |
| `Instrument(fields)`, `Row(keys)` | `{key: value}`, `slot.key` for a slot's, kept in the grammar's order |
| `Program(rows, loop)` | Rows (or dicts), then `end` (`loop` None) or `{loop:k}` |
| `Event(note, ins, commands, keep_pw, keep_filter, steps)` | `note` absolute (`"C#4"`, `"-"`, `"off"`, `"on"`); `ins` a name or an Instrument; commands `{key: value}`, `("legato", True)`; `steps` the `*k` |
| `Expr(text)`, `Call(name, args)`, `Code(statements)` | an expression, a call, a routine (an `asm{...}` body where it binds) |
| `Run(kind, program)` | an inline program after its kind in `run:` or ` run:` |
| `Def(name, value, args)` | a definition at its first use: `name` (a template's signature), its value, a template's call's arguments (None for a named one) |
| `Signed` | an int written with its sign: `note:+0`, a transpose, ` freq:-3` |

A leaf is otherwise an `int` or a `str` as written (a name, an absolute note, `none`, `hold`).
`printed` writes each block line whole, leaves out a phrase note's octave where it repeats the
previous note's, writes a sharp's letter in lower case, and quotes an expression in a flow
collection that holds a comma, and in a command or a slot's default always, and nowhere else.
That is a document's one canonical text. `printed` raises
`CanonicalError` for a model the grammar refuses: no meta, no row or a row of no play entry, a
section of no records, twice or out of order.

`tests/roundtrip.py` is a pytest plugin that checks every document a test parses is its one
canonical text, `printed(read(text)) == text` (a test marked `noncanonical` reads other spellings);
over unitracker-player's suite: `PYTHONPATH=$GRAMMAR/tests pytest -p roundtrip` in its checkout.
`tools/size.py` measures the grammar and the time to build its parser.

## Grammar

[`src/unitracker_grammar/canonical.lark`](src/unitracker_grammar/canonical.lark); the document
format and the meaning of each construct are described in unitracker's
[docs/format](https://github.com/anarkiwi/unitracker/blob/main/docs/format/document.md).
