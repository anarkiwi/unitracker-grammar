"""The prelude: modulator templates every document may call without defining them, each an
expression keyed by its signature (README, "Prelude"); a document defines none of their names.
``PROGRAMS`` are format 2.4's: restart programs written by their parameters, which
:func:`unitracker_grammar.expand.expanded` writes as rows; a document's own template of the name
is its own."""

from unitracker_grammar import expr

PRELUDE = {
    key: expr.canonical(text)
    for key, text in (
        ("vibrato(d,s,l)", "F(N) + (phi >= l)*d*(s - abs((phi - l + s) % (4*s) - 2*s))"),
        ("glide(s)", "v + s"),
        ("slide(t,s)", "v + max(min(F(N + t) - v, s), -s)"),
        ("pwm(lo,hi,s)", "lo + (hi - lo) - abs(s*phi % (2*(hi - lo)) - (hi - lo))"),
        ("sweep(a,b,s)", "a + max(min(b - a, s*phi), -s*phi)"),
        ("tremolo(lo,hi,s)", "lo + (hi - lo)*(phi // s % 2)"),
    )
}
NAMES = frozenset(key.partition("(")[0] for key in PRELUDE)
PROGRAMS = {"hr": ("lead", "ad", "sr", "test", "stop")}
