"""Text sanitizer — strips LLM artifacts from all content before rendering.

Applied to every piece of text before it reaches PDF or HTML output.
Removes em dashes, smart quotes, and other telltale LLM formatting.
"""

import re


def sanitize(text: str) -> str:
    """Clean LLM artifacts from text. Returns sanitized string."""
    if not text:
        return text

    text = _rewrite_constructions(text)

    # Em dashes → hyphens (the #1 LLM tell)
    text = text.replace(" — ", " - ")
    text = text.replace("— ", "- ")
    text = text.replace(" —", " -")
    text = text.replace("—", " - ")

    # Smart/curly quotes → straight quotes
    text = text.replace("\u201c", '"')   # "
    text = text.replace("\u201d", '"')   # "
    text = text.replace("\u2018", "'")   # '
    text = text.replace("\u2019", "'")   # '

    # En dashes read the same way in prose; keep them out of sentences.
    text = text.replace(" \u2013 ", " - ")
    text = re.sub(r"(?<=[A-Za-z]) ?\u2013 ?(?=[A-Za-z])", " - ", text)

    # Ellipsis character → three dots
    text = text.replace("\u2026", "...")

    # Non-breaking and hair spaces masquerade as ordinary ones.
    text = text.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")

    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text)

    return text.strip()


def sanitize_content(content: dict) -> dict:
    """Recursively sanitize all string values in a content dict."""
    if isinstance(content, str):
        return sanitize(content)
    if isinstance(content, list):
        return [sanitize_content(item) for item in content]
    if isinstance(content, dict):
        return {k: sanitize_content(v) for k, v in content.items()}
    return content


# ── LLM constructions ────────────────────────────────────────────────────────
# Two lists, deliberately. REWRITES are swaps with one obvious meaning, safe to
# apply unattended. FLAG_ONLY are words a real CV legitimately uses, so they are
# surfaced as warnings and left for a human to judge.

_REWRITES = [
    (r"\bdelve[ds]? into\b", "examine"),
    (r"\bdelving into\b", "examining"),
    (r"\bleverag(?:e|ed|ing)\b", {"leverage": "use", "leveraged": "used",
                                    "leveraging": "using"}),
    (r"\butiliz(?:e|ed|ing)\b", {"utilize": "use", "utilized": "used",
                                   "utilizing": "using"}),
    (r"\bin order to\b", "to"),
    (r"\ba testament to\b", "evidence of"),
]

FLAG_ONLY = [
    "robust", "seamless", "seamlessly", "pivotal", "cutting-edge", "showcase",
    "showcased", "showcasing", "underscore", "underscores", "underscoring",
    "elevate", "elevated", "spearhead", "spearheaded", "streamline",
    "streamlined", "empower", "empowered", "tapestry", "realm", "myriad",
    "navigate the complexities", "in today's", "fast-paced",
]

_NOT_JUST = re.compile(r"\bnot (?:just|only|merely)\b[^.!?]*?\b(?:but|it'?s)\b", re.I)


def _match_case(original: str, replacement: str) -> str:
    """Keep the replacement in the same case shape as what it replaced."""
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _rewrite_constructions(text: str) -> str:
    """Apply the unambiguous swaps. Never touches FLAG_ONLY words."""
    for pattern, repl in _REWRITES:
        def _sub(m, repl=repl):
            found = m.group(0)
            target = repl[found.lower()] if isinstance(repl, dict) else repl
            return _match_case(found, target)
        text = re.sub(pattern, _sub, text, flags=re.IGNORECASE)
    return text


def find_llm_isms(text: str) -> list[str]:
    """Report constructions that need a human call. Returns readable notes."""
    if not text:
        return []
    found = []
    low = text.lower()
    for word in FLAG_ONLY:
        if re.search(rf"\b{re.escape(word)}\b", low):
            found.append(f"LLM-ish wording: \u201c{word}\u201d")
    if _NOT_JUST.search(text):
        found.append("LLM-ish construction: \u201cnot just X, but Y\u201d")
    return found


def find_llm_isms_in(content) -> list[str]:
    """Walk a content structure and collect every flag, de-duplicated."""
    notes = []

    def walk(node):
        if isinstance(node, str):
            notes.extend(find_llm_isms(node))
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if not str(key).startswith("_"):
                    walk(value)

    walk(content)
    return sorted(set(notes))
