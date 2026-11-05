"""Numeric grounding check for LLM-written report text.

Every number in the narrative must equal a number in facts.json up to the rounding the text implies:
a token with d decimals (e.g. 0.457) matches a fact v when |x - v| <= 0.5 * 10^-d; in e-notation
(e.g. 3.24e-10) the unit is 10^(exponent - mantissa decimals). Percentages also match fractions
(42% ~ 0.42). Absolute values are compared so that ranges like '0.85-4.61' do not create false negatives.
Numbers glued to letters or HLA notation (hg18, DRB1, Node4, 15:01, AA_DRB1_96) are identifiers, not values.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

# small counts, CI level, alpha, GWAS threshold, MHC window (29-34 Mb) and build names
ALWAYS_OK = {
    0.0,
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
    7.0,
    8.0,
    9.0,
    10.0,
    95.0,
    100.0,
    0.05,
    5e-8,
    29.0,
    34.0,
    18.0,
    19.0,
    38.0,
}

_NUM = re.compile(r"(?<![\w*:.])(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(%?)(?![\w*:]|\.\d)")


def _unit(tok: str) -> float:
    t = tok.lstrip("-")
    if "e" in t.lower():
        mant, exp = re.split(r"[eE]", t)
        dec = len(mant.split(".")[1]) if "." in mant else 0
        return 10.0 ** (int(exp) - dec)
    dec = len(t.split(".")[1]) if "." in t else 0
    return 10.0 ** (-dec)


def numbers_in_text(text: str) -> list[tuple[str, float, bool]]:
    """(token, value, is_percent) for each standalone number."""
    out = []
    for m in _NUM.finditer(text):
        tok = m.group(1)
        try:
            out.append((tok, float(tok), m.group(2) == "%"))
        except ValueError:
            continue
    return out


def unsupported_numbers(text: str, fact_values: Iterable[float]) -> list[str]:
    vals = sorted({abs(v) for v in fact_values if isinstance(v, (int, float)) and math.isfinite(v)})
    bad = []
    for tok, x, pct in numbers_in_text(text):
        ax = abs(x)
        if ax in ALWAYS_OK:
            continue
        half = _unit(tok) / 2 * (1 + 1e-9)
        cands = [ax] + ([ax / 100] if pct else [])
        hpct = [half] + ([half / 100] if pct else [])
        if any(any(abs(c - v) <= h for v in vals) for c, h in zip(cands, hpct, strict=True)):
            continue
        bad.append(tok + ("%" if pct else ""))
    return list(dict.fromkeys(bad))
