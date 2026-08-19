"""Fabrication guard.

Aggressive rewriting is only safe if we can prove the model didn't invent
anything. Every number in a rewritten bullet must trace back to the bullet it
came from; anything else is flagged for the user rather than silently shipped.
"""

import difflib
import re

# Numbers, percentages, money, multiples, and years.
_NUM_RE = re.compile(
    r"[€$£]?\s?\d[\d,.]*(?:\s?(?:bn|billion|m|million|k|thousand|x|×)(?![a-z])|\s?%)?",
    re.I,
)


def _is_significant(token: str) -> bool:
    """Is this a claim worth policing, or incidental prose?

    A figure carrying a unit, percentage, or currency is a claim ("EUR 1.5bn",
    "61%", "3x"), as is any 4-digit number (a year). Bare small integers are
    ordinary prose — "a team of 11", "the next 18 months" — and flagging them
    buries the real warnings in noise.
    """
    digits = re.sub(r"[^\d]", "", token)
    has_unit = bool(re.search(r"[^\d.,]", token))
    return has_unit or len(digits) >= 4


def _numbers(text: str) -> set[str]:
    """Extract comparable numeric tokens from a string."""
    out = set()
    for raw in _NUM_RE.findall(text or ""):
        token = re.sub(r"[\s,]", "", raw.lower()).rstrip(".")
        # Normalise currency and unit spellings so €1.5bn == EUR 1.5 billion.
        token = token.replace("billion", "bn").replace("million", "m")
        token = token.replace("thousand", "k").replace("×", "x")
        if token and _is_significant(token):
            out.add(token)
    return out


def match_bullets(originals: list[str], rewritten: list[str], threshold: float = 0.45):
    """Pair rewritten bullets with their most likely source bullet.

    Returns (pairs, unmatched) where pairs is a list of (original, rewritten)
    and unmatched holds rewrites with no plausible source.
    """
    pairs, unmatched = [], []
    pool = list(originals)

    for new in rewritten:
        if not pool:
            unmatched.append(new)
            continue
        scored = [
            (difflib.SequenceMatcher(None, (old or "").lower(), (new or "").lower()).ratio(), old)
            for old in pool
        ]
        score, best = max(scored, key=lambda x: x[0])
        if score >= threshold:
            pairs.append((best, new))
            pool.remove(best)
        else:
            unmatched.append(new)

    return pairs, unmatched


def verify_content(master: dict, tailored: dict) -> list[str]:
    """Check tailored content for numbers that don't appear in the master.

    Returns a list of human-readable warnings — empty means clean.
    """
    warnings = []

    master_exp = {e.get("company", ""): e for e in master.get("experience", []) if isinstance(e, dict)}

    for entry in tailored.get("experience", []):
        if not isinstance(entry, dict):
            continue
        company = entry.get("company", "")
        source = master_exp.get(company)
        if not source:
            warnings.append(f"“{company}” does not appear in your master profile.")
            continue

        originals = [_text(b) for b in source.get("bullets", [])]
        allowed = set()
        for o in originals:
            allowed |= _numbers(o)

        for bullet in entry.get("bullets", []):
            text = _text(bullet)
            invented = _numbers(text) - allowed
            if invented:
                warnings.append(
                    f"{company}: “{_truncate(text)}” contains "
                    f"{', '.join(sorted(invented))}, which isn't in your master profile."
                )

    # Summary numbers must come from the master summary or any bullet.
    allowed_all = set()
    master_sum = master.get("summary", {})
    allowed_all |= _numbers(master_sum.get("default", "") if isinstance(master_sum, dict) else str(master_sum))
    if isinstance(master_sum, dict):
        for variant in (master_sum.get("variants") or {}).values():
            allowed_all |= _numbers(variant.get("text", "") if isinstance(variant, dict) else str(variant))
    for entry in master.get("experience", []):
        if isinstance(entry, dict):
            for b in entry.get("bullets", []):
                allowed_all |= _numbers(_text(b))
    for m in master.get("metrics", []):
        if isinstance(m, dict):
            allowed_all |= _numbers(f"{m.get('value','')} {m.get('label','')} {m.get('text','')}")

    summary = tailored.get("summary", "")
    if isinstance(summary, str):
        invented = _numbers(summary) - allowed_all
        if invented:
            warnings.append(
                f"Summary contains {', '.join(sorted(invented))}, which isn't in your master profile."
            )

    return warnings


def _text(bullet) -> str:
    if isinstance(bullet, dict):
        return bullet.get("text", "")
    return str(bullet)


def _truncate(text: str, limit: int = 60) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"
