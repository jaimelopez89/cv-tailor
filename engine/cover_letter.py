"""Cover letter generation.

Produces a letter grounded in the master profile and matched to a specific job
description, at the register the detected seniority calls for. Same
no-fabrication contract as the CV tailor: every claim traces to the profile.
"""

import json
import os
import re

from engine.seniority import detect_seniority, tone_instructions, tone_profile

TONES = {
    "executive": "Confident and economical. Short paragraphs, no throat-clearing, outcome-first.",
    "warm": "Personable and human. Show genuine interest in the company without gushing.",
    "direct": "Plain and specific. No adjectives that aren't doing work. Straight to evidence.",
}

LENGTHS = {"short": 250, "medium": 350, "long": 450}

MODEL = "claude-opus-5"


def _clean_letter(letter: dict) -> dict:
    """Strip LLM artifacts from a letter before anyone sees or saves it."""
    from engine.sanitize import sanitize_content
    return sanitize_content(letter)


def generate(profile: dict, target: dict, tone: str = "executive",
             length: str = "medium", provider: str = "auto",
             seniority_level: str = None) -> tuple[dict, list[str]]:
    """Generate a cover letter. Returns (letter, errors).

    letter = {salutation, paragraphs[], closing, signoff, seniority, meta}
    """
    errors = []
    role = target.get("role", "")
    company = target.get("company", "")
    jd_text = target.get("jd_text", "")

    seniority = detect_seniority(role, jd_text)
    if seniority_level:
        seniority = {**seniority, "level": seniority_level,
                     "label": tone_profile(seniority_level)["label"],
                     "confidence": "user-set"}

    use_anthropic = provider in ("auto", "anthropic") and os.environ.get("ANTHROPIC_API_KEY")
    use_openai = provider in ("auto", "openai") and os.environ.get("OPENAI_API_KEY")

    if provider == "anthropic" and not use_anthropic:
        errors.append("Anthropic API key not set. Add it in Settings.")
    elif provider == "openai" and not use_openai:
        errors.append("OpenAI API key not set. Add it in Settings.")

    if use_anthropic:
        try:
            return _finish(_anthropic_letter(profile, target, tone, length, seniority),
                           profile, target, seniority), errors
        except Exception as e:
            if provider == "anthropic":
                errors.append(f"Anthropic generation failed: {e}")
                return _finish(_fallback_letter(profile, target, seniority),
                               profile, target, seniority), errors

    if use_openai:
        try:
            return _finish(_openai_letter(profile, target, tone, length, seniority),
                           profile, target, seniority), errors
        except Exception as e:
            errors.append(f"OpenAI generation failed: {e}")

    if not use_anthropic and not use_openai:
        errors.append("No AI key configured — generated a basic template letter. Add a key in Settings.")

    return _finish(_fallback_letter(profile, target, seniority), profile, target, seniority), errors


def _finish(letter: dict, profile: dict, target: dict, seniority: dict) -> dict:
    """Attach letterhead metadata and normalise the shape."""
    letter = _clean_letter(letter)
    meta = profile.get("meta", {}) or {}
    paragraphs = [p.strip() for p in (letter.get("paragraphs") or []) if str(p).strip()]
    return {
        "salutation": letter.get("salutation") or "Dear Hiring Team,",
        "paragraphs": paragraphs,
        "closing": letter.get("closing") or "",
        "signoff": letter.get("signoff") or "Sincerely,",
        "seniority": seniority,
        "meta": {
            "name": meta.get("name", ""),
            "tagline": meta.get("tagline", ""),
            "email": meta.get("email", ""),
            "phone": meta.get("phone", ""),
            "location": meta.get("location", ""),
            "web": meta.get("web", ""),
            "linkedin": meta.get("linkedin", ""),
        },
        "target": {"role": target.get("role", ""), "company": target.get("company", "")},
    }


def _profile_digest(profile: dict) -> str:
    """Compact, fact-only view of the profile for the prompt."""
    meta = profile.get("meta", {}) or {}
    summary = profile.get("summary", {})
    summary_text = summary.get("default", "") if isinstance(summary, dict) else str(summary)

    lines = [f"NAME: {meta.get('name','')}", f"HEADLINE: {meta.get('tagline','')}",
             f"SUMMARY: {summary_text}", "", "EXPERIENCE:"]
    for entry in profile.get("experience", [])[:5]:
        if not isinstance(entry, dict):
            continue
        roles = ", ".join(
            f"{r.get('title','')} ({r.get('period','')})"
            for r in entry.get("roles", []) if isinstance(r, dict)
        )
        lines.append(f"- {entry.get('company','')} — {roles}")
        for b in entry.get("bullets", [])[:6]:
            text = b.get("text", "") if isinstance(b, dict) else str(b)
            if text:
                lines.append(f"    * {text}")

    metrics = profile.get("metrics", [])
    if metrics:
        lines.append("")
        lines.append("HEADLINE METRICS:")
        for m in metrics[:6]:
            if isinstance(m, dict):
                label = m.get("label") or m.get("text", "")
                value = m.get("value", "")
                lines.append(f"- {value} {label}".strip())

    skills = profile.get("skills", {})
    if isinstance(skills, dict) and skills.get("groups"):
        lines.append("")
        lines.append("SKILLS:")
        for g in skills["groups"][:6]:
            if isinstance(g, dict):
                items = ", ".join(str(i) for i in (g.get("items") or [])[:10])
                lines.append(f"- {g.get('name','')}: {items}")

    return "\n".join(lines)


def _prompt(profile: dict, target: dict, tone: str, length: str, seniority: dict) -> str:
    words = LENGTHS.get(length, 350)
    tone_desc = TONES.get(tone, TONES["executive"])
    role = target.get("role", "the role")
    company = target.get("company", "the company")
    jd = (target.get("jd_text") or "")[:4000]

    return f"""Write a cover letter for this application.

TARGET
Role: {role}
Company: {company}

JOB DESCRIPTION
{jd or "(none supplied — work from the role title alone)"}

CANDIDATE PROFILE (the ONLY source of facts)
{_profile_digest(profile)}

{tone_instructions(seniority['level'])}

HOUSE STYLE - non-negotiable:
- Never use em dashes or en dashes. Use a comma, a full stop, or a plain hyphen.
- Use straight quotes and apostrophes, never curly ones.
- Never write: delve, leverage, utilize, robust, seamless, pivotal, cutting-edge,
  showcase, underscore, elevate, tapestry, realm, myriad, fast-paced.
- Never write the "not just X, but Y" construction, or any variant of it.
- Plain, concrete, specific. No press-release register.

TONE: {tone_desc}
LENGTH: about {words} words across 3-4 body paragraphs.

RULES
1. NO FABRICATION. Every achievement, number, employer, and skill must come from
   the candidate profile above. Never invent a detail, a motivation, or a
   connection to the company that isn't supported.
2. Open with a specific hook tied to this company or role — something drawn from
   the job description. Never "I am writing to apply for...".
3. Cite two or three CONCRETE achievements from the profile, with their real
   numbers, each one chosen because it answers a requirement stated in the JD.
4. Mirror the job description's own vocabulary for the things it cares about.
5. Write at the seniority register described above.
6. No filler sentences, no restating the CV wholesale, no "team player" clichés.
7. If the profile genuinely lacks something the JD asks for, do not paper over
   it — lean on the adjacent strength instead. Never claim it.

Return ONLY a JSON object, no markdown fences:
{{
  "salutation": "Dear ...,",
  "paragraphs": ["first paragraph", "second", "third"],
  "closing": "final short paragraph with a call to action",
  "signoff": "Sincerely,"
}}"""


def _anthropic_letter(profile, target, tone, length, seniority) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system="You are an expert cover letter writer. Return only a JSON object. "
               "Every fact must come from the supplied profile — never fabricate.",
        messages=[{"role": "user", "content": _prompt(profile, target, tone, length, seniority)}],
    )
    if message.stop_reason == "refusal":
        raise ValueError("Request was declined by the safety system.")

    text = "".join(b.text for b in message.content if b.type == "text").strip()
    return _parse_json(text)


def _openai_letter(profile, target, tone, length, seniority) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=2000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are an expert cover letter writer. Return only a JSON "
                                          "object. Every fact must come from the supplied profile."},
            {"role": "user", "content": _prompt(profile, target, tone, length, seniority)},
        ],
    )
    return _parse_json(resp.choices[0].message.content)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.split("\n") if not l.startswith("```"))
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("Model did not return JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict) or "paragraphs" not in data:
        raise ValueError("Response missing required fields")
    return data


def _fallback_letter(profile: dict, target: dict, seniority: dict) -> dict:
    """Deterministic skeleton used when no AI provider is available.

    Deliberately plain — it assembles real profile content and leaves the user
    to edit, rather than pretending to be a finished letter.
    """
    meta = profile.get("meta", {}) or {}
    role = target.get("role") or "the role"
    company = target.get("company") or "your organisation"

    summary = profile.get("summary", {})
    summary_text = summary.get("default", "") if isinstance(summary, dict) else str(summary)

    achievements = []
    for entry in profile.get("experience", [])[:2]:
        if not isinstance(entry, dict):
            continue
        for b in entry.get("bullets", [])[:2]:
            text = b.get("text", "") if isinstance(b, dict) else str(b)
            if text:
                achievements.append(f"At {entry.get('company','')}, {text[0].lower() + text[1:]}")

    paragraphs = [
        f"I am applying for the {role} position at {company}.",
        summary_text,
    ]
    if achievements:
        paragraphs.append(" ".join(achievements[:3]))

    return {
        "salutation": "Dear Hiring Team,",
        "paragraphs": [p for p in paragraphs if p],
        "closing": f"I would welcome the chance to discuss how this experience applies at {company}.",
        "signoff": "Sincerely,",
    }
