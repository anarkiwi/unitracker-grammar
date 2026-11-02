# Format 2.5

What each construct of format 2.5 plays, for a player to implement from this page and
[unitracker-player's semantics](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md),
which every rule not restated here keeps. A document is format 2.5 exactly where it has any of:

- a `calls` or a `holds` line;
- the hold event `event`, in a slot's `hold` or `reset`, or in `holds`;
- a `global` line naming a cell but `cut`;
- a `slots` or `state` line naming `ctrl`, `ad`, `sr`, `res`, `route`, `mode` or `vol`, or an
  `order` line naming `ctl` or one of those cells' phases;
- a binding or a stop of `ctrl`, `ad`, `sr`, `res`, `route`, `mode` or `vol`, as a row key, an
  event command or (`ad`, `sr`) an instrument field, or a slot prefix on one;
- an expression with an operator or function of [Expressions](#expressions) below that 2.4 lacked,
  or a comparison that is not in parentheses of its own;
- an expression that reads a cell by name ([Reading cells](#reading-cells));
- a prefix `mask` on a key ([Terms](#terms));
- a tempo of more than two entries ([Tempo lists](#tempo-lists)).

Otherwise it is 2.4 where it has layers, orderlists or a call of a prelude program, else 2.3. The
version line states it and a document whose line differs is refused. `Document.version` and
`code.check_document` find the same constructs in the model and in the parse tree.

## Standard notes

`clock:{cycles_per_tick:C,clock_hz:H}` has no rounding. `clock_hz` is the machine's clock, and
`F(k) = round(440 * 2**((k - 57)/12) * 2**24 / clock_hz)` for every integer `k` (`round` to the
nearest integer, ties to even), 0 where it is 0 or at least 65536. `unitracker_grammar.frequency`
is that function; `F.lo` and `F.hi` are its bytes. `cycles_per_tick` plays nothing.

## Cells

A cell is a register-driving value a modulator slot, a program row, an event command or an
instrument field sets. Every cell takes the bindings of [Bindings](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md#bindings),
its stops, and slots and state lines.

| cell | scope | mask (bits kept) | register | phase | row key and command | instrument field |
|---|---|---|---|---|---|---|
| `freq` | voice | `$FFFF` | `$D400+7(i-1)`, `+1` | `freq` | `freq` | `freq` |
| `pw` | voice | `$0FFF` | `+2`, `+3` | `pw` | `pw` | `pw` (a program) |
| `ctrl` | voice | `$FF` | `+4` | `ctl` | `ctrl` | |
| `ad` | voice | `$FF` | `+5` | `ad` | `ad` | `ad` |
| `sr` | voice | `$FF` | `+6` | `sr` | `sr` | `sr` |
| `cut` | song | `$07FF` | `$D415`, `$D416` | `cut` | `cut` | |
| `res` | song | `$0F` | `$D417` bits 4-7 | `res` | `res` | |
| `route` | song | `$0F` | `$D417` bits 0-3 | `route` | `route` | |
| `mode` | song | `$F0` | `$D418` bits 4-7 | `mode` | `mode` | |
| `vol` | song | `$0F` | `$D418` bits 0-3 | `vol` | `vol` | |

`unitracker_grammar.cells` holds the table (`CELLS`, `MASKS`, `VOICE_CELLS`, `SONG_CELLS`,
`PHASES`). `mode` is `$D418`'s high nibble in its register position (`$10` low-pass, `$20`
band-pass, `$40` high-pass, `$80` voice 3 off). The
`ctrl` cell is the control byte; the gate and the mask keep their meaning (`$D404 + 7(i-1)` is
`((ctrl ^ mask) & $FE) | (ctrl & gate & 1)`), and the cell is neither the control program (the
kind `ctrl`, run in the `ctrl` phase) nor an instrument's `ctrl` field, which is that program.
`route_on` and `route_off` stay integer row keys; they set and clear bits of the `route` cell.

### Values

A plain integer is a write, on every cell and wherever a cell is set: a row, an event, an
instrument or a slot default. In the cell's phase on the tick it applies, the cell takes that
value wrapped to its mask, and the write ends the binding of the slot it is written to (a key
without a prefix writes the cell's first slot), so it fires once and leaves that slot unbound.
The cell's other slots keep their bindings and fire on the new value. `ad:9`, `ctrl:65`, `vol:15`,
`pw:800` and `cut:7` are writes; `ad:9 + 0` is a binding, a constant one that fires every tick.
Anything that is to keep firing is an expression or a call. A template parameter stands for an
integer where one is written as the whole value (`ad:a`). There is no `n!` form: `!` follows a
call, an expression or an `asm` block alone.

On `freq` the integer forms (`freq:n`, `freq:+n`) mean `F(N) + n`, with `N` the voice's note at
the tick the write applies, and that tick only; the slot is then unbound.

Any other value binds or stops:

| value | meaning |
|---|---|
| `m(3)`, `v + 4`, `asm{...}`, and in a command `'v + 4'` | binds the cell's slot to that modulator |
| `...!` | a once binding: fires once, then leaves its slot unbound |
| `none`, `hold`, `reset` | the stops, as a row key and as a command; an instrument's field takes `none` alone |
| `s.ad:...` | the slot `s` of the cell; a key without a prefix is the cell's first slot |

`hold` ends the binding of every slot of the cell. It stops no program: the cell has no program
slot (`cut`'s is the filter program, `pw`'s the pulse program). `row.KEY` events (`row`,
`row.ad`, ...) name a row that has the key `KEY` as an integer, a binding or a stop.

### Hold events

| event | occurs |
|---|---|
| `event` | on the tick of the first step of each event of a voice's pattern: a note, a legato note, a rest `-`, `off`, `on`, or an event carrying commands; not on the other steps of a `*k` event |

`event-k` is the call `k` calls before it. The other hold events are those of
[Semantics](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md).

### Firing

A modulator fires as in [Modulators](https://github.com/anarkiwi/unitracker-player/blob/main/docs/semantics.md#modulators):
each slot in order takes phi 0 on its reset events, then, but on its hold events, sets
`v' = e(v, phi, N, n)` wrapped to the cell's mask (`v` the value the slot before left, the cell's
for the first), then phi + 1; the cell takes the last slot's value; a cell with no bound slot
holds its value. `N` and `n` are of the voice that bound the slot. A code modulator's `v` wrapped
to the mask is its value; its state is the voice's copy of the cell's `state` variables for a
voice cell, the song's one copy for a song cell. `freq` alone plays `F(N)` with no bound slot.

Per tick, after the programs and events have applied and before the registers are written, the
phases of the cells run in the order of the `order` line. The phases are

```text
events ctrl pulse filter freq pw cut ctl ad sr res route mode vol read
```

`ctl` fires the `ctrl` cell (`ctrl` itself is the control programs' phase). The default order is
`[events,ctrl,pulse,filter,freq,pw,cut,ctl,ad,sr,res,route,mode,vol]`, `read` within `events`.
An `order` line names each of `events ctrl pulse filter freq pw cut read` exactly once and each of
`ctl ad sr res route mode vol` at most once; any other line is refused. A phase of a cell that
the line leaves out runs immediately after the nearest earlier phase of the sequence
`cut ctl ad sr res route mode vol`, wherever the line puts that one. A voice cell's phase visits
the voices in voice order and fires the voice's cell. A song cell's phase is below.

### Song cells and `global`

`cut`, `res`, `route`, `mode` and `vol` are one cell each for the song, with their own slots;
a slot is bound by a voice, whose `N` and `n` it reads, and a voice's `none` and `hold` end the
bindings that voice made. `global:[cut,res,...]` names the song cells, in the order
`cut res route mode vol`, each once, that belong to the song: a `none` or `hold` of the cell
from any voice ends the bindings whichever voice made them, a `hold` of `cut` stops the filter
program whichever voice started it, and the cell fires at its owner's place.

The owner of a cell is the voice that last bound a slot of it: by a row key, an instrument
field or an event command, in the order the binds apply, a bind that keeps phi counting, and
voice 1 for a slot's default binding at tick 0. A stop does not change it. A cell with no owner
has no bound slot and fires nothing.

In the cell's phase the voices are visited in voice order. A global cell fires, once, at the
visit of its owner, all its slots in order, each reading the notes of the voice that bound it. A
song cell that is not global fires once after the last voice's visit. A filter program a voice
starts ends the cutoff's bindings other voices made, as before; it ends no other cell's.

## Expressions

An expression is a Python-compatible `ast` after rewriting `&&`, `||` and `!` to `and`, `or` and
`not`; `unitracker_grammar.expr` compiles it, with `zero=True` in a player. Integers are
unbounded; a cell wraps its value at its write, and `lo hi u8 u16 sx` wrap explicitly. The
operators, loosest first (the precedence of playspec):

| level | operators | result |
|---|---|---|
| 1 | `a \|\| b` | 1 if either is nonzero, else 0 |
| 2 | `a && b` | 1 if both are nonzero, else 0 |
| 3 | `!a` | 1 if `a` is 0, else 0 |
| 4 | `a == b`, `!=`, `<`, `<=`, `>`, `>=` | 1 or 0; one comparison, not chained |
| 5 | `a \| b` | bitwise or |
| 6 | `a ^ b` | bitwise xor |
| 7 | `a & b` | bitwise and |
| 8 | `a << b`, `a >> b` | shifts, `>>` arithmetic; a negative count is an error, 0 with `zero` |
| 9 | `a + b`, `a - b` | |
| 10 | `a * b`, `a // b`, `a % b` | `//` and `%` floored; an error on a divisor of 0, 0 with `zero` |
| 11 | `~a`, `-a` | bitwise not (`-a - 1`), negation |
| 12 | `v phi N n`, a cell's name, literals, `(e)`, `F(k)`, `T[k]`, `abs min max`, `lo hi u8 u16 sx ite` | |

| function | value |
|---|---|
| `lo(x)`, `u8(x)` | `x & 255` |
| `hi(x)` | `(x >> 8) & 255` |
| `u16(x)` | `x & 65535` |
| `sx(x)` | the byte `x & 255` sign-extended to 16 bits: `b \| 65280` if `b & 128`, else `b` |
| `ite(c, a, b)` | `a` if `c` is nonzero, else `b` |

A comparison needs no parentheses of its own (`phi >= l`, `min(v < 3,2)`), and a logic or
comparison operand of an arithmetic operator does (`(phi >= l)*d`). `!` is the loosest prefix: it
takes a whole comparison (`!v < phi` is `!(v < phi)`) and is written in parentheses as an operand
(`4*(!v)`). Decimal literals only. The differences from playspec are the integers' width and what
they allow: a playspec value is 8 or 16 bits and wraps at every operation, and an expression here
wraps at the cell; `/` and `%` take any operands here and `//` is playspec's `/`; `!`, `&&`,
`||` and `ite`'s condition take any integer; `u8` and `sx` wrap any integer; hexadecimal and
binary literals, `true` and `false`, and memory access are playspec's alone. Over operands in
range for a playspec expression to agree (no wrap before a shift or a comparison) the results are
equal modulo 2^16; `tests/test_expr_playspec.py` checks it against pysidtracker.

A cell's name (`freq pw ctrl ad sr cut res route mode vol`) reads that cell's value
([Reading cells](#reading-cells)). `expr.canonical` prints one text: the operands of `|`, `^`, `&`, `&&` and `||` in one order, sums
and products as linear forms, parentheses where the precedence needs them.

## Calls

`calls:{frame:F,full:[p0,p1,...]}`, after `lag` and before `global`. `F` is 1 or more; `full`
is optional, a non-empty list of 0 and 1 with a 1 in it, and leaving it out is every call full.
Without a `calls` line a frame is one call and every call is full.

A call is one run of the phases of a tick (the unit the other pages call a tick). Calls are
numbered 0, 1, 2, ...; call `c` is full if `full[c mod len(full)]` is 1. A frame is `F`
consecutive calls, frame `f` the calls `F*f` to `F*f + F - 1`, and the output has one row of 25
registers per frame: the registers after the frame's last call (with `lag:k`, those the cells
made `k` calls before that call, the `regs` values for a call before 0).

A reduced call runs every phase but `events` and `read`. A full call runs all as before. What
the sequencer owns counts the full calls only; the rest counts all calls:

| counts full calls (sequencer ticks) | counts calls |
|---|---|
| the `events` and `read` phases; init (at sequencer tick 0, the first full call); `tempo`, `vtempo` and the steps, an event's `*k`, the timeline and the song's end; a restart's rows, their `hold` and `wait` and the lookahead before the note | programs' `wait` and `hold` (control, pulse, filter); a modulator's phi; once bindings; the `-k` of a slot's hold and reset events and of `holds`; `lag`; the registers' sampling |

An event whose tick is sequencer tick `s` happens on the `s`th full call (from 0). The events
of a slot, `step`, `last`, `read`, `note`, `legato` and `event`, are on such calls, so never on a reduced one;
`row` and `row.KEY` are on any call a control program row applies; `e-k` is the call `k` calls
before a call of `e` (none before call 0). The song ends at the sequencer tick every voice has
stopped: the calls before that full call are played and a trailing part of a frame is not output.

## Env

`env:S/S/...` in a program row, and ` env:S/S/...` as an event command, writes a voice's envelope
registers as up to four segments in one call. A segment is `sr.ad.ctrl`, each value an integer
or `_`, the value the call's phases left. The call writes each segment's registers in the order
`sr`, `ad`, `ctrl`, the segments in order, and the voice's `sr`, `ad` and `ctrl` cells hold the
last segment's values. A segment ends at a gate or TEST edge: the commanded envelope is the
gate edges and the `sr` and `ad` in force at each edge and at the call's end, so the order of
writes between two edges carries nothing. `env:_._.65` is `ctrl:65`.

A TEST pulse is an ordinary `ctrl` write when the call has one TEST edge. A call that pulses TEST
repeatedly (sample playback) writes `ctrl:[a,b,...]`, two integers or more, a program row's key or
an event command: the control register is written each value in this order, and the cell holds
the last. Between such writes `sr` and `ad` are as the call left them. `mask` holds bits over the
`ctrl` cell between calls (the TEST bit of a restart, a lift's ring and sync bits), and is not
a part of an env or a list.

## Holds

`holds:{pw:[read,note-1],ctrl:[step],b:[legato]}`, after `layers` and before `order`. Each key is
a program kind (`ctrl`, `pw`, `filter`: all its layers) or a layer's name from the `layers` line
(that layer alone); a key twice, a name that is neither, a layer named as a kind, an event that
is no `HOLD_EVENT` and `row` or `row.KEY` for the control program or a control layer are refused
(a control program cannot pause on the rows it applies). A kind and its layer both naming events
hold on their union. The events are those of a slot's `hold`, of the voice that started the
program.

On a call at which a listed event occurs for a program's voice that program is held: its slot is
not visited, no row applies, and the call does not count in the program's timing. Each program
slot (a voice's, a layer's) has a clock that advances on the calls it is not held. A program
started at clock `t` applies its first row when its clock is `t + wait`, each next row at the
clock its previous row applied plus its `hold` plus its `wait`, and `{loop:k}` as before; a row due
on a held call applies on the next call that is not held, with a clock equal to its due clock. A
program started on a held call counts from that call's clock. The filter program, one per layer
for the song, is held on the events of the voice that started it. A held call changes nothing
else: modulators fire, other kinds run and events apply as usual.

## Tempo lists

`tempo` is a list of ticks per step, `t0, t1, ...`, of one entry or more. The header takes
`tempo:n` (one entry) or `tempo:[t0,t1,...]` (two or more; a list of one is written bare), the
commands ` tempo:t0/t1/...` and ` vtempo:t0/t1/...` (` tempo:n` for one entry). Step `k` of a
voice, counted from the last `tempo` or `vtempo` that applied to it (from the start of the song,
at the header's list), starting at 0, lasts `t[k mod len]` ticks. `tempo` restarts every voice
at entry 0, `vtempo` its own voice only; an entry of 0 is refused. `n` and `a/b` are the lists
of one and two entries and play as before. The model holds a tuple (`Header.tempo`, the value of
an `Event`'s `tempo` and `vtempo`; an int given is the list of one).

## Terms

Every cell has an output term, a second value the register takes combined with the cell and
that is never fed back into the cell's `v`:

| cell | register | combine | wrap |
|---|---|---|---|
| `ctrl` | `$D404 + 7(i-1)` | xor, `((ctrl ^ term) & $FE) \| (ctrl & gate & 1)` | |
| `freq` | `+0`, `+1` | `freq + term` | `$FFFF` |
| `pw` | `+2`, `+3` | `pw + term` | `$0FFF` |
| `cut` | `$D415`, `$D416` | `cut + term` | `$07FF` |

The terms of `ad`, `sr`, `res`, `route`, `mode` and `vol` are not defined: a nibble pair or
sharing a register with another cell, they have neither a plain sum nor a plain xor (a carry
across the nibbles of `ad`, `sr`, `mode`/`vol` or `res`/`route`) a document could mean, and a
sum or an xor of the whole register gives a different byte from the term of a field. A prefix
`mask` on any of them is refused.

The term is named by the reserved slot prefix `mask`: `mask.freq:b`, `mask.pw:b`, `mask.cut:b`
and `mask.ctrl:b`, as a program row key, an event command and an instrument field (`cut`'s is
the `filter` field, `mask.filter:b`; `ctrl` has no instrument field). `mask` names no slot nor
layer. `b` is

| value | meaning |
|---|---|
| an expression, a call, `asm{...}` (in a command `'v + 1'`) | binds the term: from the tick it applies, in the cell's phase after the cell's slots, the term takes `e(v, phi, N, n)` wrapped to the cell's mask, `v` the term's own previous value, `phi` counting from the bind (a rebind to the same modulator keeps it), `N` and `n` of the voice that bound it |
| an integer | a write that holds: in the cell's phase the term takes the value, and stays there |
| `none` | ends the binding; the term holds its value |

`hold`, `reset`, a once binding (`!`), a program or a list of writes are refused. The term
starts at 0, so a document without it plays as before, and the registers' initial state
(`regs`) is the cells', the terms 0. A song cell's term (`cut`) follows the cell's owner and
`global` rules: a bind of the term counts as a bind of the cell for its owner, and the term
fires with the cell's slots.

`ctrl`'s term is the control mask of earlier formats: `mask:m` (an integer row key, immediate
and holding until changed, only the bits `$FE`) is its integer write and keeps its text; a
binding or a stop of it is `mask.ctrl:b`, and `mask.ctrl:m` with an integer is refused. A
`mask:m` takes effect when the row applies, as before; an integer on another term in the cell's
phase.

## Reading cells

An expression reads another cell by name, `freq pw ctrl ad sr cut res route mode vol`, the
cell's current value: the voice's own cell for a voice cell, the song's for a song cell, of the
voice that bound the slot (the term is not part of it). A cell's phase reads whatever value the
other cell holds at that point of the tick's phase order: a cell whose phase has not yet run in
the tick reads its value from the previous tick, so the `order` line decides it. An expression
that names its own cell reads the cell's value as the tick began, not `v`. The names are no
template parameters (a signature naming one is refused) and a code modulator cannot read a
cell. `unitracker_grammar.expr.compile_expr` compiles the names as reads: the function takes a
fifth argument, a mapping from each name in its `reads` to that cell's value.
