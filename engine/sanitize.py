"""Text sanitizer — strips LLM artifacts from all content before rendering.

Applied to every piece of text before it reaches PDF or HTML output.
Removes em dashes, smart quotes, and other telltale LLM formatting.
"""

import re


def sanitize(text: str) -> str:
    """Clean LLM artifacts from text. Returns sanitized string."""
    if not text:
        return text

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

    # Ellipsis character → three dots
    text = text.replace("\u2026", "...")

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
