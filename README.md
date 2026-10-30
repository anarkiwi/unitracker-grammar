# unitracker-grammar

The canonical [unitracker](https://github.com/anarkiwi/unitracker) document as a
[Lark](https://github.com/lark-parser/lark) grammar, with an LALR parser for it and the note
table its expressions read as `F(k)`, and the modulator expression language: checked, printed
in its one text and compiled to Python.

A document names no player. It holds everything it plays: instruments, programs, expressions,
code, phrases and the tables they index. Its only constants are the note table at its clock and
the header defaults (PAL clock, 3 voices, tempo 6). The grammar is formats 2.3 to 2.5, and
refuses every other version.

```text
unitracker:2.3
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
`H` the machine's clock the note table is computed at), `voices`, `tempo`; `slots`, per cell its modulator slots in firing order, each with its default
binding and the events it holds and resets on
(`slots:{freq:{wave:{mod:note(),reset:[row.note]},tick:{hold:[step-1,row]}}}`); `layers`
(format 2.4, below); `holds` (format 2.5, below); `order`, the
phases of a tick (`order:[events,ctrl,pulse,filter,freq,pw,cut,read]`); `state`, per cell its
state variables and their sizes in bytes (`state:{freq:{t:1},pw:{r:1,q:2}}`); `regs`, the 25 SID
registers' values before tick 0 (`regs:[0,0,...,15]`); `lag`; `calls` (format 2.5); `global`; `tables`; then the definitions that are
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

## Format 2.3

Sugar that `expand.expanded(doc)` writes in the core (no templates of instruments or phrases, no
groups, sections, chord names or definitions at their first use), which a player plays; a prelude
call stays a call.

| construct | text | plays as |
|---|---|---|
| prelude | `tick.freq:vibrato(2,3,4)` | a call of the template of `prelude.PRELUDE` (below); a document defines none of their names |
| chord name | `run:arp(min7)`, `f(2,maj)` | the chord's intervals among the call's arguments, `arp(3,7,10)`, `f(2,4,7)` (`chords.CHORDS`), but a template's own parameter of that name |
| instrument template | ` arpi(a,b):{ad:a,sr:b,ctrl:arp(a,7)}`, `C4.arpi(9,240)` | each distinct call an instrument `iK`, the next free number in reading order |
| phrase template | ` riff(x,y):[x.i1,-,y,E4]`, `play:[riff(G1,f1)+2,...]` | the phrase with each parameter its note; a note after a parameter carries its octave |
| group | `[E,G]x2`, `[A|B|C5]` (a volta), in a phrase and among song items | its body twice; its body before each ending in turn (`A,B,A,C5`) |
| section | ` s1:[play:[p1,p2,p3],s2x2,[...]x2]` after `phrase:`; song items ` - s1`, ` - s1x3`, ` - play:[...]` | its items in place, the song's `{loop:k}` naming its `k`th item |
| a record a call | ` i14:arpi(9,240)`, ` p14:riff(G1,f1)` | the record its template's instance |
| first use | `C4.arpi(a,b)={...}(9,240)`, `riff(x,y)=[...](G1,f1)`, ` - s1=[...]x2` | the definition in its section |

Core constructs a player reads: a binding written with `!` after it (`tick.freq:snap()!`,
`pw:800!`, `{pw:'v + 3'!}`, an instrument's field) fires once, then leaves its slot unbound; `lag:k`
(after `regs`) outputs each frame's registers `k` calls late; `global:[cut]` makes the
cutoff, its bindings and the filter program the song's, not the voice's that set them.

| prelude template | drives the cell to |
|---|---|
| `vibrato(d,s,l)` | `F(N)`, then from tick `l` a triangle `d` a tick up to `d*s`, down to `-d*s` and back, period `4*s` |
| `glide(s)` | its value plus `s` a tick |
| `slide(t,s)` | its value moved toward `F(N + t)` by at most `s` a tick, held there |
| `pwm(lo,hi,s)` | `lo`, rising `s` a tick to `hi`, falling back to `lo`, repeating |
| `sweep(a,b,s)` | `a`, moving toward `b` by `s` a tick, held at `b` |
| `tremolo(lo,hi,s)` | `lo` for `s` ticks, `hi` for `s`, repeating |

`chords.CHORDS` is music21's chord types within an octave, by their longest lowercase
abbreviation, and `oct` (12): `tools/chords.py` writes it and a test checks it against music21.

## Format 2.4

Layers: a voice runs several programs of one kind at once, each by its own cursor. The header's
`layers` line, after `slots`, names per program kind (`ctrl`, `pw`, `filter`, in that order) its
layers in the order each tick runs them: `layers:{ctrl:[a,b]}`. A kind it leaves out has one
layer. A layer's prefix names it where a program starts, as a slot's prefix names a slot:

| site | text |
|---|---|
| an instrument's program field, repeating per layer | `{ctrl:c1,b.ctrl:c7}`, `b.pw:pw2`, `b.filter:f1` |
| a program row's `run`, repeating | `{b.run:c7,run:c1}`, `b.run:arp(7,4)`, `b.run:ctrl[...]` |
| a ` run:` command, repeating | ` b.run:c7 run:c1`, ` b.run:none` |

An unprefixed field or run names the kind's first layer.

Voice orderlists: a song may instead be one orderlist per voice, each with its own ending, so
voices that loop independently need not be written out to the common multiple of their loops:

```text
song:
 - voice:[p1,[p2,p1+2]x2,[p1|p2|p1+1]|loop:1]
 - voice:[p2+1,p3=[E4,-]|end]
```

A voice's entries are play entries (a phrase's name, a phrase template's call or a phrase at its
first use, each with its transpose) and groups of them (`[...]x2`, a volta); an inline phrase is
not one, and neither is `~` or `end`. After `|`, `end` or `loop:k`, the top-level entry `k` it
continues at (`expand` maps it to the first entry that entry plays). A song is rows or
orderlists, not both; a document with orderlists has no `{loop:k}` or `end` line
(`Voice(play, loop)` in `Document.rows`, `Document.voiced`).

Hard restart: an instrument's `restart` may call the prelude program
`hr(lead,ad,sr,test,stop)` (`prelude.PROGRAMS`; `test` and `stop` optional, 0 or 1), which
`expand` writes as the rows it stands for (`expand.hr`):

| call | rows |
|---|---|
| `restart:hr(2,15,0)` | `[{hold:2,gate:0,ad:15,sr:0},{},end]` |
| `restart:hr(1,15,0,1)` | `[{mask:8,gate:0,ad:15,sr:0},{mask:0},end]`: TEST set until the note |
| `restart:hr(6,15,0,0,1)` | `[{hold:6,gate:0,ad:15,sr:0,run:ctrl[end]},{},end]`: the control program stopped |

`lead` ticks (1 or more) before the note the gate goes off with the restart envelope; the note's
row, the last, falls on the note. A document that defines its own `hr` template calls its own.

A document is format 2.4 exactly where it has a `layers` line, orderlists or a call of a
prelude program it does not define (`Document.version`), so every 2.3 document reads and prints
as before. What they play is unitracker-player's
[semantics](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md#layers).

## Format 2.5

Every register-driving cell takes bindings, a stop and a slot prefix where an integer stood; the
expression language gains playspec's operators; a frame may be several play calls; a program may
pause on events; the song's filter cells are global. Each construct, its widths, defaults and
firing order is in [docs/format-2.5.md](docs/format-2.5.md).

| construct | text |
|---|---|
| a bound cell: `ctrl ad sr res route mode vol` as `freq`, `pw` and `cut` | `{ctrl:vib(3),ad:v + 4,vol:none}`, ` vol:'v - 1'`, `{ad:m(2),sr:9}` (instrument) |
| slots, state and a phase for them | `slots:{vol:{fade:{mod:m(1)}}}`, `state:{ctrl:{t:1}}`, `order:[...,cut,ctl,ad,sr,res,route,mode,vol,read]` |
| expression operators | `\| ^ & << >> ~ == != < <= > >= && \|\| !`, `lo hi u8 u16 sx ite` |
| the calls of a frame | `calls:{frame:3,full:[1,0,0]}` |
| programs pausing | `holds:{pw:[read,note-1],ctrl:[step],b:[legato]}` |
| global song cells | `global:[cut,res,route,mode,vol]` |

| operator | meaning |
|---|---|
| `\|\|` `&&` `!` | logic over any integer, 1 or 0 |
| `==` `!=` `<` `<=` `>` `>=` | one comparison, 1 or 0, in parentheses only as an operand |
| `\|` `^` `&` `<<` `>>` `~` | bitwise, shifts and not |
| `+ - * // %` | floored, as before |

A document is 2.5 exactly where it has any of these; `Document.version` says so. Without
`calls` a frame is one full call.

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
frequency(57, 985248)     # F(k) = round(440 * 2**((k - 57)/12) * 2**24 / clock_hz), 0 outside 1-65535
from unitracker_grammar.expand import core, expanded
core(text)                # the parse tree of text's core (parsed once where it has no sugar)
```

`parse` also checks what the grammar cannot say (`code.check_document`): templates, state
names, anonymous bodies, the tables read, no parameter read outside a template, and a pulse or
filter record of one binding in its short form, each template's parameters (a phrase template's
note parameters only in it), no prelude name defined, raising `CanonicalError`, `CodeError` or
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
`ZeroDivisionError` on a divisor of 0 and a shift `ValueError` on a negative count; with
`zero=True` they are 0. `later` says whether a text or parse tree needs format 2.5.

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
of `frequency(k, clock_hz)` for k -128-255, so `F.lo-24,y` reads entry y - 24.

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
| `Document(header, tables, mods, defs, init, rows, loop)` | `tables` `{name: ints}`; `mods` the templates `(signature, Expr \| Code)`; `defs` the `restart`, `ins`, `ctrl`, `pw`, `filter`, `phrase` and `section` sections in that order (`Section`s, or `{kind: [(name, value)]}`); `init` events or None; `rows` song items (SongRows, or play entry lists, Parts and Groups); `loop` the item it loops to, None for `end` |
| `Header(meta, clock, voices, tempo, slots, layers, holds, order, state, regs, lag, calls, global_cells)` | each line, None where not written (the version line is `Document.version`: `VERSION_2_5`, `"2.5"`, with a construct of format 2.5, else `VERSION_2_4`, `"2.4"`, with layers, orderlists or a prelude program, else `VERSION`, `"2.3"`); `layers` `{kind: names}` in `LAYERED_KINDS` order; `clock` `(cycles_per_tick, clock_hz)`; `holds` `(key, events)` pairs; `calls` `(frame, full)`; `meta` texts as written (`"'A, B'"` quoted); `slots` `{cell: [Slot]}`, `state` `{cell: [(name, size)]}`; `slot(cell)` its Slots |
| `Slot(name, mod, hold, reset)` | a slot's default binding and its events (`"note-1"`, `"row.freq"`) |
| `SongRow(play)` | play entries (`Play(phrase, transpose)`, `"~"`, `"end"`; a phrase is a name or inline events) |
| `Section(kind, records)` | `(name, value)` records of one kind; a template's name is its `signature` (`arp(a,b)`), its rows reading parameters as strings (`ad: "a"`, `note: "+a"`, `Call("walk", ("b",))`); a `pw` or `filter` record `Program([{"pw": b}])` (`cut` for `filter`) is stored as `b` |
| `Instrument(fields)`, `Row(keys)` | `{key: value}`, `slot.key` for a slot's, kept in the grammar's order |
| `Program(rows, loop)` | Rows (or dicts), then `end` (`loop` None) or `{loop:k}` |
| `Event(note, ins, commands, keep_pw, keep_filter, steps)` | `note` absolute (`"C#4"`, `"-"`, `"off"`, `"on"`) or a phrase template's parameter; `ins` a name, an Instrument or an instrument template's Call; commands `{key: value}`, `("legato", True)`; `steps` the `*k` |
| `Expr(text)`, `Call(name, args)`, `Code(statements)` | an expression, a call, a routine (an `asm{...}` body where it binds) |
| `Run(kind, program)` | an inline program after its kind in `run:` or ` run:` |
| `Group(body, times, endings)`, `Part(section, times)` | a group of events or song items; a song item playing a section |
| `Once(value)` | a binding that fires once (`value!`) |
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
