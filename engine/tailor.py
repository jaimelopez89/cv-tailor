"""Tailoring engine — selects and prioritises content from master profile for a target role.

Supports deterministic (tag-based scoring) and AI-assisted (Claude API) tailoring.
"""

import copy
import os
import re
from collections import Counter

import yaml

from engine.metrics import normalize_metric, renderable_metrics
from engine.seniority import detect_seniority, tone_instructions, tone_profile

MODEL = "claude-opus-5"


def tailor(master_path: str, target: dict, ai: bool = False, rewrite: bool = True,
           provider: str = "auto", recommendations: list = None,
           seniority: dict = None) -> tuple[dict, list[str]]:
    """Main entry: load master profile, tailor for target, return (content, errors).

    Args:
        master_path: Path to master_profile.yaml
        target: Dict with company, role, emphasis (list of strings), jd_text (optional)
        ai: Use AI tailoring when a key is available
        rewrite: Rewrite bullets aggressively (default). False = select/reorder only.
        provider: "auto" | "anthropic" | "openai" — which LLM provider to use
        recommendations: Fit-analysis recommendations for the model to act on
        seniority: Detected seniority dict; computed from the target when omitted
    Returns:
        (tailored_content, errors) where errors is a list of human-readable strings
    """
    with open(master_path, "r") as f:
        master = yaml.safe_load(f)

    errors = []
    if seniority is None:
        seniority = detect_seniority(target.get("role", ""), target.get("jd_text", ""))
    recommendations = recommendations or []

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
                return _finish(_ai_tailor(master, target, rewrite, recommendations, seniority),
                               master, target, seniority), errors
            except Exception as e:
                if provider == "anthropic":
                    errors.append(f"Anthropic tailoring failed: {e}")
                    return _deterministic_tailor(master, target, seniority), errors
                # auto mode: silently try next provider

        if use_openai:
            try:
                return _finish(_openai_tailor(master, target, rewrite, recommendations, seniority),
                               master, target, seniority), errors
            except Exception as e:
                if provider == "openai":
                    errors.append(f"OpenAI tailoring failed: {e}")
                # auto mode: silently fall through to deterministic

        if provider == "auto" and (use_anthropic or use_openai):
            errors.append("AI tailoring unavailable. Using keyword-based tailoring.")
        elif errors:
            errors.append("Fell back to keyword-based tailoring.")

    return _deterministic_tailor(master, target, seniority), errors


def _finish(content: dict, master: dict, target: dict, seniority: dict) -> dict:
    """Normalise an AI response: resolve the summary, clean metrics, tag seniority."""
    if isinstance(content.get("summary"), dict):
        target_tags = _extract_tags(target.get("emphasis", []), target.get("jd_text", ""))
        content["summary"] = _select_summary(master.get("summary", {}), target_tags)

    # Metrics must always reach the template with value/label populated.
    content["metrics"] = renderable_metrics(content.get("metrics") or master.get("metrics", []))

    content["_seniority"] = seniority
    return content


def _deterministic_tailor(master: dict, target: dict, seniority: dict = None) -> dict:
    """Tag-based scoring to select and order content."""
    if seniority is None:
        seniority = detect_seniority(target.get("role", ""), target.get("jd_text", ""))
    profile = tone_profile(seniority["level"])
    content = copy.deepcopy(master)
    emphasis = target.get("emphasis", [])
    jd_text = target.get("jd_text", "")

    # Build target tag set from emphasis keywords + JD
    target_tags = _extract_tags(emphasis, jd_text)

    # Summary: pick best variant or default
    content["summary"] = _select_summary(master.get("summary", {}), target_tags)

    # Metrics: normalise, score by tag overlap, keep top 4 that can actually render
    scored_metrics = []
    for raw in master.get("metrics", []):
        m = normalize_metric(raw)
        overlap = len(set(m.get("tags", [])) & target_tags)
        score = m.get("weight", 5) * (1 + overlap)
        scored_metrics.append((score, m))
    scored_metrics.sort(key=lambda x: x[0], reverse=True)
    content["metrics"] = renderable_metrics([m for _, m in scored_metrics])

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

        max_bullets = profile["bullets_per_role"]
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
    content["_seniority"] = seniority
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


def _shared_rules(target: dict, rewrite: bool, recommendations: list, seniority: dict) -> str:
    """The tailoring contract shared by both providers."""
    target_desc = f"Company: {target.get('company', 'Unknown')}\n"
    target_desc += f"Role: {target.get('role', 'Unknown')}\n"
    if target.get("emphasis"):
        target_desc += f"Emphasis: {', '.join(target['emphasis'])}\n"
    if target.get("jd_text"):
        target_desc += f"\nJob Description:\n{target['jd_text'][:6000]}\n"

    if rewrite:
        rewrite_block = """REWRITING — BE AGGRESSIVE. This is the most important instruction.
Rewrite EVERY bullet you keep. A bullet that comes back unchanged is a failure
unless it was already perfectly matched to this job.

For each bullet:
- Lead with the OUTCOME, not the activity. "Built X" is weak; "Grew pipeline
  3x by building X" is right.
- Re-express it in the job description's OWN vocabulary. If the JD says
  "go-to-market", do not say "commercial launch". Mirror their words.
- Cut throat-clearing, hedges, and any clause that does not earn its place.
- Front-load the words that matter to this employer; a recruiter reads the
  first six words of each line and no more.
- Aim for one line, never more than two.

WHAT YOU MUST NOT CHANGE — these are load-bearing facts:
- Every number, percentage, currency amount, and multiple, exactly as written.
- Every company name, product name, technology, and person's title.
- Every date and time period.
- The nature of your involvement. If the source says "contributed to", you may
  not upgrade it to "led". If it says "supported", it is not "owned".
Rewriting means re-expressing what is there with sharper words and a better
order. It never means adding, inflating, or implying something new."""
    else:
        rewrite_block = ("REWRITING — DISABLED. Select and reorder only. "
                         "Reproduce bullet text exactly as it appears in the master profile.")

    rec_block = ""
    if recommendations:
        lines = []
        for r in recommendations:
            if isinstance(r, dict):
                where = r.get("location") or r.get("section") or "profile"
                lines.append(f"- [{where}] {r.get('suggestion', '')}".rstrip())
                if r.get("draft"):
                    lines.append(f"    suggested wording: {r['draft']}")
            elif r:
                lines.append(f"- {r}")
        if lines:
            rec_block = (
                "\nRECOMMENDATIONS TO CARRY OUT\n"
                "A fit analysis of this job produced the notes below. Act on them — they are\n"
                "instructions, not suggestions. Where one proposes wording, use it (adjusted to\n"
                "fit the surrounding text). Where it identifies a gap you cannot fill from the\n"
                "profile, reorder to foreground the closest genuine evidence instead. Never\n"
                "invent content to satisfy a recommendation.\n" + "\n".join(lines) + "\n"
            )

    return f"""TARGET:
{target_desc}
{tone_instructions(seniority['level'])}
{rec_block}
{rewrite_block}

NO FABRICATION — the hard boundary:
Every fact, metric, employer, technology, and claim in your output must exist in
the master profile. You may re-word, re-order, re-frame, and cut. You may not add.
If the profile lacks relevant material for something the job wants, leave that
area thin. A sparse honest CV beats an padded one, and invented content is
caught by an automated check that will reject your output.

TASKS:
1. Write the summary for THIS job at the seniority register above, using only
   facts from the profile. Rewrite it — do not just pick a variant verbatim.
2. Keep the strongest bullets per experience entry (see the seniority limit) and
   rewrite each one per the rules above.
3. Reorder experience entries to lead with the most relevant.
4. Choose the metrics that matter most to this employer. Each needs a short
   `value` (the figure, e.g. "EUR 1.5bn") and a short `label` of 2-4 words.
   Never emit a metric with an empty value or label.
5. Reorder skill groups to lead with the most relevant.
6. Keep only the speaking entries that support this application."""


def _ai_tailor(master: dict, target: dict, rewrite: bool = True,
               recommendations: list = None, seniority: dict = None) -> dict:
    """Use the Claude API for intelligent tailoring."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    master_yaml = yaml.dump(master, default_flow_style=False, allow_unicode=True)

    prompt = f"""Tailor this CV for the target role.

{_shared_rules(target, rewrite, recommendations or [], seniority)}

MASTER PROFILE:
{master_yaml}

Return ONLY valid YAML (no markdown fences) with these top-level keys:
meta: (copy from master exactly — do not alter)
summary: "rewritten summary text"
metrics: (list of {{value, label, tags, weight}} dicts)
experience: (list of entries with company/subtitle/location/roles/bullets)
ventures: (copy from master exactly)
education: (copy from master exactly)
skills: (groups list)
speaking: (filtered list)
notable: (copy from master exactly)"""

    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system="You are an expert CV editor. Return only YAML. Rewrite aggressively "
               "for the target role while never altering a fact.",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise ValueError("Request was declined by the safety system.")

    response_text = "".join(b.text for b in message.content if b.type == "text").strip()

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


def _openai_tailor(master: dict, target: dict, rewrite: bool = True,
                   recommendations: list = None, seniority: dict = None) -> dict:
    """Use OpenAI gpt-4o-mini for tailoring (JSON output to avoid YAML parse issues)."""
    import json
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)

    # Send master as JSON (avoids YAML colon ambiguity in the prompt)
    master_json = json.dumps(master, ensure_ascii=False, indent=2)

    user_msg = f"""Tailor this CV for the target role.

{_shared_rules(target, rewrite, recommendations or [], seniority)}

MASTER PROFILE (JSON):
{master_json}

Return a JSON object with these exact top-level keys (copy unchanged sections
verbatim from master): meta, summary, metrics, experience, ventures, education,
skills, speaking, notable.
Each metric must be {{"value": "...", "label": "...", "tags": [...], "weight": N}}
with both value and label non-empty."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=8000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content":
                "You are an expert CV editor. Return only a JSON object. Rewrite bullets "
                "aggressively for the target role, but every fact — numbers, companies, "
                "dates, technologies — must come from the master profile unchanged."},
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
