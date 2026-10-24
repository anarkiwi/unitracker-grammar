"""The size of a canonical grammar and the time to build its LALR parser.

``size.py [GRAMMAR.lark] [--runs N]``: lines, rules and terminals as written and as Lark compiles
them, and the best of ``N`` parser builds (the installed ``canonical.lark`` by default).
"""

import argparse
import re
import sys
import time
from pathlib import Path

from lark import Lark
from tqdm import tqdm


def measure(text: str, runs: int) -> dict:
    """The grammar's sizes and its best parser build time in seconds over ``runs`` builds."""
    best, lark = float("inf"), None
    for _ in tqdm(range(runs), unit="build", disable=runs < 2):
        start = time.perf_counter()
        lark = Lark(text, parser="lalr", lexer="contextual")
        best = min(best, time.perf_counter() - start)
    written = [line for line in text.splitlines() if line.strip()]
    return {
        "lines": len(text.splitlines()),
        "comment lines": sum(line.lstrip().startswith("//") for line in written),
        "rules written": len(re.findall(r"^[?!]?_?[a-z][a-z0-9_]*(?:\.\d+)?:", text, re.M)),
        "terminals written": len(re.findall(r"^_?[A-Z][A-Z0-9_]*(?:\.\d+)?:", text, re.M)),
        "rules": len({r.origin.name for r in lark.rules}),
        "productions": len(lark.rules),
        "terminals": len(lark.terminals),
        "lalr states": len(lark.parser.parser.parser.parse_table.states),
        "build s": round(best, 3),
    }


def main(argv=None) -> int:
    """The command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("grammar", nargs="?", type=Path)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    if args.grammar is None:
        from unitracker_grammar import GRAMMAR  # pylint: disable=import-outside-toplevel

        text = GRAMMAR.read_text(encoding="utf-8")
    else:
        text = args.grammar.read_text(encoding="utf-8")
    for key, value in measure(text, args.runs).items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
