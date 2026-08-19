"""Metric normalisation.

Master profiles imported from a CV store metrics as a single sentence::

    - text: Increased marketing-impacted pipeline from EUR 500M to EUR 1.5bn.

Templates need a headline figure and a short caption::

    - value: "EUR 1.5bn"
      label: "Marketing-impacted pipeline"

`normalize_metric` bridges the two shapes so no template ever renders an empty
cell, and `migrate_metrics` upgrades a whole profile in place.
"""

import re

# Currency symbols and words we keep attached to the figure.
_CURRENCY = r"(?:EUR|USD|GBP|€|\$|£)"
# A figure: optional currency, digits (with , or . separators), optional unit.
_UNIT = r"(?:(?:bn|billion|m|million|k|thousand|x|×)(?![a-z])|%)"
_FIGURE = rf"{_CURRENCY}?\s?\d[\d,.]*\s?{_UNIT}?"

# "from X to Y" — the second figure is the achievement, the first is the baseline.
_RANGE_RE = re.compile(rf"from\s+({_FIGURE})\s+to\s+({_FIGURE})", re.I)
_FIGURE_RE = re.compile(_FIGURE, re.I)

# Leading verbs to strip when turning a sentence into a caption.
_LEAD_VERBS = re.compile(
    r"^(?:increased|grew|generated|developed|built|drove|delivered|raised|"
    r"reduced|cut|scaled|led|launched|improved|expanded|achieved)\s+",
    re.I,
)

_CURRENCY_MAP = {"EUR": "€", "USD": "$", "GBP": "£"}


def tidy_figure(fig: str) -> str:
    """Normalise a figure: collapse spaces, map currency words to symbols."""
    fig = re.sub(r"\s+", " ", fig).strip().rstrip(".,;")
    for word, symbol in _CURRENCY_MAP.items():
        fig = re.sub(rf"^{word}\s*", symbol, fig, flags=re.I)
    # "€1.5 bn" -> "€1.5bn"
    fig = re.sub(rf"(\d)\s+({_UNIT})$", r"\1\2", fig, flags=re.I)
    return fig


def _caption_from(text: str, figure: str) -> str:
    """Build a short label from the sentence, minus the figure and lead verb."""
    caption = text
    # Drop the whole "from A to B" clause, else just the figure itself.
    caption = _RANGE_RE.sub("", caption)
    caption = caption.replace(figure, "")
    caption = _LEAD_VERBS.sub("", caption.strip())
    # Trim trailing connectives left behind by the removals.
    caption = re.sub(r"\s+", " ", caption).strip(" .,;:-")
    caption = re.sub(r"\s+(?:by|to|from|of|at|in|with)$", "", caption, flags=re.I)
    if not caption:
        return ""
    # Keep acronyms upper-case, lowercase an ordinary leading word.
    first, _, rest = caption.partition(" ")
    if not first.isupper():
        first = first[0].lower() + first[1:] if len(first) > 1 else first.lower()
    caption = f"{first} {rest}".strip()
    return caption[0].upper() + caption[1:] if caption else ""


def split_text_metric(text: str) -> tuple[str, str]:
    """Split a metric sentence into (value, label). Returns ("", text) on failure."""
    if not text or not text.strip():
        return "", ""
    text = text.strip()

    match = _RANGE_RE.search(text)
    if match:
        figure = match.group(2)
        return tidy_figure(figure), _caption_from(text, match.group(0))

    figures = _FIGURE_RE.findall(text)
    if figures:
        # Prefer the largest-looking figure: the one with a unit suffix, else the first.
        with_unit = [f for f in figures if re.search(_UNIT + r"\s*$", f, re.I)]
        figure = (with_unit or figures)[0]
        return tidy_figure(figure), _caption_from(text, figure)

    return "", text


def normalize_metric(metric) -> dict:
    """Return a metric dict guaranteed to carry `value` and `label` keys.

    Accepts the modern {value,label} shape, the imported {text} shape, or a
    bare string. Preserves tags/weight when present.
    """
    if isinstance(metric, str):
        metric = {"text": metric}
    if not isinstance(metric, dict):
        return {"value": "", "label": "", "tags": [], "weight": 5}

    out = dict(metric)
    value = str(out.get("value") or "").strip()
    label = str(out.get("label") or "").strip()

    if not value and not label:
        value, label = split_text_metric(str(out.get("text") or ""))

    out["value"] = value
    out["label"] = label
    out.setdefault("tags", [])
    out.setdefault("weight", 5)
    return out


def is_renderable(metric) -> bool:
    """True when a metric has something worth putting on the page."""
    m = normalize_metric(metric)
    return bool(m["value"] or m["label"])


def renderable_metrics(metrics, limit: int = 4) -> list[dict]:
    """Normalise, drop empties, and cap. The single guard every template uses."""
    if not metrics:
        return []
    out = []
    for m in metrics:
        norm = normalize_metric(m)
        if norm["value"] or norm["label"]:
            out.append(norm)
        if len(out) >= limit:
            break
    return out


def migrate_metrics(profile: dict) -> tuple[dict, int]:
    """Normalise every metric in a profile. Returns (profile, count_changed)."""
    metrics = profile.get("metrics") or []
    changed = 0
    migrated = []
    for m in metrics:
        before = m if isinstance(m, dict) else {"text": m}
        after = normalize_metric(m)
        after.pop("text", None)
        if after.get("value") != before.get("value") or after.get("label") != before.get("label"):
            changed += 1
        migrated.append(after)
    profile["metrics"] = migrated
    return profile, changed
