# unitracker-grammar

The canonical [unitracker](https://github.com/anarkiwi/unitracker) document as a
[Lark](https://github.com/lark-parser/lark) grammar, with an LALR parser for it.

## Install

```sh
pip install "unitracker-grammar @ git+https://github.com/anarkiwi/unitracker-grammar"
```

## Use

```python
from unitracker_grammar import parse, CanonicalError
tree = parse(text)  # a lark.Tree, or CanonicalError naming the line and column
```

`parser()` is the cached `lark.Lark` parser and `GRAMMAR` the grammar file resource.

## Grammar

[`src/unitracker_grammar/canonical.lark`](src/unitracker_grammar/canonical.lark); the document
format is described in unitracker's
[docs/format/document.md](https://github.com/anarkiwi/unitracker/blob/main/docs/format/document.md#canonical-form).
