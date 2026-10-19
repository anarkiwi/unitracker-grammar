# unitracker-grammar

The canonical [unitracker](https://github.com/anarkiwi/unitracker) document as a
[Lark](https://github.com/lark-parser/lark) grammar, with an LALR parser for it and the note
table its expressions read as `F(k)`.

A document names no player. It holds everything it plays: instruments, programs, expressions,
phrases and the tables its expressions index. Its only constants are the note table at its clock
and the header defaults (PAL clock, 3 voices, tempo 6).

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

## Grammar

[`src/unitracker_grammar/canonical.lark`](src/unitracker_grammar/canonical.lark); the document
format and the meaning of each construct are described in unitracker's
[docs/format](https://github.com/anarkiwi/unitracker/blob/main/docs/format/document.md).
