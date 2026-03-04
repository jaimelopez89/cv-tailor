"""Tailoring engine — selects and prioritises content from master profile for a target role.

Supports deterministic (tag-based scoring) and AI-assisted (Claude API) tailoring.
"""

import copy
import os
import re
from collections import Counter

import yaml


def tailor(master_path: str, target: dict, ai: bool = False, rewrite: bool = False,
           provider: str = "auto") -> tuple[dict, list[str]]:
    """Main entry: load master profile, tailor for target, return (content, errors).

    Args:
        master_path: Path to master_profile.yaml
        target: Dict with company, role, emphasis (list of strings), jd_text (optional)
        ai: Use AI tailoring when a key is available
        rewrite: Allow AI to rewrite bullets (only with ai=True)
        provider: "auto" | "anthropic" | "openai" — which LLM provider to use
    Returns:
        (tailored_content, errors) where errors is a list of human-readable strings
    """
    with open(master_path, "r") as f:
        master = yaml.safe_load(f)

    errors = []

    if ai:
        use_anthropic = provider in ("auto", "anthropic") and os.environ.get("ANTHROPIC_API_KEY")
        use_openai    = provider in ("auto", "openai")    and os.environ.get("OPENAI_API_KEY")

        if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
            errors.append("Anthropic API key not set. Add it in Settings.")
        elif provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            errors.append("OpenAI API key not set. Add it in Settings.")
        elif provider == "auto" and not use_anthropic and not use_openai:
            errors.append("No AI API key configured. Using keyword-based tailoring. Add a key in Settings.")

        if use_anthropic:
            try:
                return _ai_tailor(master, target, rewrite), errors
            except Exception as e:
                errors.append(f"Anthropic tailoring failed: {e}")
                if provider == "anthropic":
                    return _deterministic_tailor(master, target), errors

        if use_openai:
            try:
                return _openai_tailor(master, target, rewrite), errors
            except Exception as e:
                errors.append(f"OpenAI tailoring failed: {e}")

        if errors:
            errors.append("Fell back to keyword-based tailoring.")

    return _deterministic_tailor(master, target), errors


def _deterministic_tailor(master: dict, target: dict) -> dict:
    """Tag-based scoring to select and order content."""
    content = copy.deepcopy(master)
    emphasis = target.get("emphasis", [])
    jd_text = target.get("jd_text", "")

    # Build target tag set from emphasis keywords + JD
    target_tags = _extract_tags(emphasis, jd_text)

    # Summary: pick best variant or default
    content["summary"] = _select_summary(master.get("summary", {}), target_tags)

    # Metrics: score by tag overlap, keep top 4
    metrics = master.get("metrics", [])
    scored_metrics = []
    for m in metrics:
        overlap = len(set(m.get("tags", [])) & target_tags)
        score = m.get("weight", 5) * (1 + overlap)
        scored_metrics.append((score, m))
    scored_metrics.sort(key=lambda x: x[0], reverse=True)
    content["metrics"] = [m for _, m in scored_metrics[:4]]

    # Experience: score bullets, keep top N per entry, reorder entries
    experience = master.get("experience", [])
    scored_entries = []
    for entry in experience:
        entry_copy = copy.deepcopy(entry)
        bullets = entry_copy.get("bullets", [])

        scored_bullets = []
        for b in bullets:
            overlap = len(set(b.get("tags", [])) & target_tags)
            score = b.get("weight", 5) * (1 + overlap)
            scored_bullets.append((score, b))
        scored_bullets.sort(key=lambda x: x[0], reverse=True)

        max_bullets = 5
        entry_copy["bullets"] = [b for _, b in scored_bullets[:max_bullets]]

        # Entry score = max bullet score
        entry_score = scored_bullets[0][0] if scored_bullets else 0
        scored_entries.append((entry_score, entry_copy))

    scored_entries.sort(key=lambda x: x[0], reverse=True)
    content["experience"] = [e for _, e in scored_entries]

    # Skills: filter groups by tag overlap, reorder
    skills = master.get("skills", {})
    if isinstance(skills, dict):
        groups = skills.get("groups", [])
        scored_groups = []
        for g in groups:
            overlap = len(set(g.get("tags", [])) & target_tags)
            scored_groups.append((overlap, g))
        scored_groups.sort(key=lambda x: x[0], reverse=True)
        content["skills"] = {"groups": [g for _, g in scored_groups]}

    # Speaking: filter by tag overlap, keep top entries
    speaking = master.get("speaking", [])
    scored_speaking = []
    for s in speaking:
        tags = s.get("tags", []) if isinstance(s, dict) else []
        overlap = len(set(tags) & target_tags)
        scored_speaking.append((overlap, s))
    scored_speaking.sort(key=lambda x: x[0], reverse=True)
    content["speaking"] = [s for _, s in scored_speaking]

    # Pass through: ventures, education, notable (no filtering)
    content["_target"] = target
    return content


def _select_summary(summary_data: dict, target_tags: set) -> str:
    """Select best summary variant based on tag overlap."""
    if isinstance(summary_data, str):
        return summary_data

    default = summary_data.get("default", "")
    variants = summary_data.get("variants", {})

    best_text = default
    best_score = 0

    for key, variant in variants.items():
        if isinstance(variant, dict):
            text = variant.get("text", "")
            tags = set(variant.get("tags", []))
        else:
            text = str(variant)
            tags = set()

        overlap = len(tags & target_tags)
        if overlap > best_score:
            best_score = overlap
            best_text = text

    return best_text


def _extract_tags(emphasis: list, jd_text: str) -> set:
    """Build tag set from emphasis keywords and JD text."""
    tags = set()

    # Direct emphasis items as tags (lowercase, underscored)
    for item in emphasis:
        tag = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_")
        tags.add(tag)
        # Also add individual words as potential tags
        for word in item.lower().split():
            clean = re.sub(r"[^a-z0-9]", "", word)
            if len(clean) > 2:
                tags.add(clean)

    # Extract keywords from JD text
    if jd_text:
        words = re.findall(r"[a-z]+", jd_text.lower())
        freq = Counter(words)
        # Keep words that appear 2+ times and aren't common stopwords
        stopwords = {
            "the", "and", "for", "with", "you", "our", "that", "this",
            "are", "will", "have", "from", "your", "about", "who", "has",
            "can", "all", "but", "not", "they", "was", "been", "more",
        }
        for word, count in freq.most_common(30):
            if count >= 2 and word not in stopwords and len(word) > 2:
                tags.add(word)

    return tags


def _ai_tailor(master: dict, target: dict, rewrite: bool = False) -> dict:
    """Use Claude API for intelligent tailoring."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    master_yaml = yaml.dump(master, default_flow_style=False, allow_unicode=True)
    target_desc = f"Company: {target.get('company', 'Unknown')}\n"
    target_desc += f"Role: {target.get('role', 'Unknown')}\n"
    if target.get("emphasis"):
        target_desc += f"Emphasis: {', '.join(target['emphasis'])}\n"
    if target.get("jd_text"):
        target_desc += f"\nJob Description:\n{target['jd_text']}\n"

    rewrite_instruction = ""
    if rewrite:
        rewrite_instruction = """- You MAY rewrite bullet text to better position for the role, but preserve
  all factual claims, metrics, and specificity. Never invent achievements."""
    else:
        rewrite_instruction = """- Do NOT rewrite bullets. Select and reorder only. Use exact original text."""

    prompt = f"""Given this master career profile and target role, produce a tailored content YAML.

CRITICAL RULE — NO FABRICATION:
- Every fact, metric, bullet, and claim in the output MUST come from the master profile below.
- NEVER invent achievements, metrics, company descriptions, or any content not in the source.
- You may ONLY select, reorder, and (if --rewrite is set) rephrase existing content.
- If the master profile lacks relevant content for an area, leave it sparse — do not fill gaps.

TARGET:
{target_desc}

MASTER PROFILE:
{master_yaml}

INSTRUCTIONS:
1. Select the best summary variant for this role (or use default). If rewrite is allowed,
   you may adjust phrasing but ONLY using facts from the profile.
2. Select and reorder the 3-5 strongest bullets per experience entry for this target.
3. Reorder experience entries to lead with most relevant.
4. Select top 4 metrics most relevant to this role.
5. Reorder skill groups to lead with most relevant.
6. Select most relevant speaking entries.
{rewrite_instruction}

Return ONLY valid YAML matching this exact structure (no markdown fences):
meta: (copy from master exactly — do not alter)
summary: "selected/refined summary text"
metrics: (list of value/label dicts — from master only)
experience: (list of entries with company/subtitle/roles/bullets — from master only)
ventures: (copy from master exactly)
education: (copy from master exactly)
skills: (groups list — from master only)
speaking: (filtered list — from master only)
notable: (copy from master exactly)"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Strip markdown fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        response_text = "\n".join(lines)

    content = yaml.safe_load(response_text)
    if not isinstance(content, dict) or "meta" not in content:
        raise ValueError("AI response missing required fields")

    content["_target"] = target
    return content


def _openai_tailor(master: dict, target: dict, rewrite: bool = False) -> dict:
    """Use OpenAI gpt-4o-mini for intelligent tailoring (JSON output to avoid YAML parse issues)."""
    import json
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)

    # Send master as JSON (avoids YAML colon ambiguity in the prompt)
    master_json = json.dumps(master, ensure_ascii=False, indent=2)
    target_desc = f"Company: {target.get('company', 'Unknown')}\n"
    target_desc += f"Role: {target.get('role', 'Unknown')}\n"
    if target.get("emphasis"):
        target_desc += f"Emphasis: {', '.join(target['emphasis'])}\n"
    if target.get("jd_text"):
        target_desc += f"\nJob Description:\n{target['jd_text'][:2000]}\n"

    rewrite_instruction = (
        "You MAY rewrite bullet text to better position for the role, but preserve "
        "all factual claims, metrics, and specificity. Never invent achievements."
        if rewrite else
        "Do NOT rewrite bullets. Select and reorder only. Use exact original text."
    )

    system_msg = (
        "You are an expert CV editor. Return only a JSON object — no markdown, no explanation. "
        "Every fact in the output must come from the master profile. Never fabricate content."
    )
    user_msg = f"""Tailor this CV for the target role.

TARGET:
{target_desc}

MASTER PROFILE (JSON):
{master_json}

INSTRUCTIONS:
1. Select the best summary variant or use default.
2. Select and reorder 3-5 strongest bullets per experience entry for this role.
3. Reorder experience entries to lead with most relevant.
4. Select top 4 metrics most relevant to this role.
5. Reorder skill groups to lead with most relevant.
6. Select most relevant speaking entries.
7. {rewrite_instruction}

Return a JSON object with these exact top-level keys (copy unchanged sections verbatim from master):
meta, summary, metrics, experience, ventures, education, skills, speaking, notable"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=4000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    )

    content = json.loads(resp.choices[0].message.content)
    if not isinstance(content, dict) or "meta" not in content:
        raise ValueError("OpenAI response missing required fields")

    content["_target"] = target
    return content


# ── Target I/O ───────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
TARGETS_DIR = os.path.join(DATA_DIR, "targets")


def load_target(name_or_path: str) -> dict:
    """Load a target brief from file or create from inline string.

    If name_or_path is a file, load it. Otherwise parse "Role, Company" format.
    """
    # Check if it's a file path
    if os.path.isfile(name_or_path):
        with open(name_or_path, "r") as f:
            return yaml.safe_load(f)

    # Check saved targets
    safe_name = re.sub(r"[^a-z0-9]+", "_", name_or_path.lower()).strip("_")
    saved_path = os.path.join(TARGETS_DIR, f"{safe_name}.yaml")
    if os.path.isfile(saved_path):
        with open(saved_path, "r") as f:
            return yaml.safe_load(f)

    # Parse inline: "Role, Company"
    parts = [p.strip() for p in name_or_path.split(",", 1)]
    if len(parts) == 2:
        return {"role": parts[0], "company": parts[1], "emphasis": []}
    return {"role": name_or_path, "company": "", "emphasis": []}


def save_target(target: dict, name: str = None):
    """Save target brief to targets directory."""
    os.makedirs(TARGETS_DIR, exist_ok=True)
    if not name:
        name = f"{target.get('role', 'unknown')}_{target.get('company', 'unknown')}"
    safe_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    path = os.path.join(TARGETS_DIR, f"{safe_name}.yaml")
    with open(path, "w") as f:
        yaml.dump(target, f, default_flow_style=False, allow_unicode=True)
    return path


def list_targets() -> list:
    """List saved target briefs."""
    if not os.path.isdir(TARGETS_DIR):
        return []
    return [f.replace(".yaml", "") for f in os.listdir(TARGETS_DIR) if f.endswith(".yaml")]
