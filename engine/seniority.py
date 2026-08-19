"""Seniority detection and tone profiles.

Reads the target role title and job description to work out what level the
job sits at, then supplies a tone profile that steers both CV tailoring and
cover-letter generation. A VP posting and a senior IC posting want opposite
things from the same career history: one wants org scale and P&L, the other
wants depth of craft.
"""

import re

LEVELS = ["ic", "lead", "manager", "director", "vp", "c_suite"]

# Title patterns, most senior first — the first match wins.
_TITLE_PATTERNS = [
    ("c_suite", r"\b(chief\s+\w+\s+officer|c[teimfop]o|founder|co-?founder|"
                r"president|managing\s+director|general\s+manager)\b"),
    ("vp",      r"\b(vp|vice\s+president|svp|evp|head\s+of|global\s+head)\b"),
    ("director", r"\b(director|group\s+manager|senior\s+manager)\b"),
    ("manager", r"\b(manager|team\s+lead(?:er)?|people\s+lead)\b"),
    ("lead",    r"\b(lead|principal|staff|architect)\b"),
    ("ic",      r"\b(senior|junior|associate|specialist|analyst|engineer|"
                r"designer|scientist|coordinator|consultant)\b"),
]

# JD phrases that pull the read up or down, with weights.
_JD_SIGNALS = [
    ("c_suite", 3, r"\b(board|c-?suite|executive\s+team|p&l\s+owner|"
                   r"company\s+strategy|investor|fundrais)"),
    ("vp",      2, r"\b(org(?:ani[sz]ation)?\s+of|multiple\s+teams|"
                   r"leadership\s+team|budget\s+owner|headcount|"
                   r"reports?\s+to\s+the\s+(?:ceo|cmo|cto|cpo|founder))"),
    ("director", 2, r"\b(manage\s+managers|cross-?functional\s+lead|"
                    r"department|roadmap\s+owner)"),
    ("manager", 1, r"\b(manage\s+a\s+team|direct\s+reports|hiring|"
                   r"coach(?:ing)?|1:1s)"),
    ("lead",    1, r"\b(technical\s+lead|mentor|set\s+the\s+standard|"
                   r"own\s+the\s+architecture)"),
    ("ic",      1, r"\b(hands-?on|individual\s+contributor|day-?to-?day\s+execution|"
                   r"write\s+code|ship\s+features)"),
]

TONE_PROFILES = {
    "c_suite": {
        "label": "C-suite / Founder",
        "register": "Board-level. Speak in company outcomes, market position, and capital efficiency.",
        "foreground": "P&L ownership, company-wide strategy, board and investor exposure, market creation",
        "background": "tooling detail, individual execution, process mechanics",
        "verbs": "set, owned, scaled, positioned, transformed, established",
        "summary_words": 55,
        "bullets_per_role": 4,
    },
    "vp": {
        "label": "VP / Head of",
        "register": "Executive. Lead with business outcome and the scale of the org that delivered it.",
        "foreground": "org design, multi-team leadership, budget, revenue and pipeline impact, exec influence",
        "background": "individual tool proficiency, task-level detail",
        "verbs": "built, led, scaled, owned, drove, unified",
        "summary_words": 60,
        "bullets_per_role": 5,
    },
    "director": {
        "label": "Director",
        "register": "Senior operator. Pair strategic ownership with evidence you ran the machine.",
        "foreground": "cross-functional programmes, roadmap ownership, managing managers, measurable outcomes",
        "background": "hands-on implementation minutiae",
        "verbs": "directed, established, delivered, coordinated, grew",
        "summary_words": 60,
        "bullets_per_role": 5,
    },
    "manager": {
        "label": "Manager",
        "register": "Hands-on leader. Balance team outcomes with your own contribution.",
        "foreground": "team delivery, hiring and coaching, process improvement, shipped outcomes",
        "background": "company-level strategy claims",
        "verbs": "managed, shipped, improved, coached, ran",
        "summary_words": 55,
        "bullets_per_role": 5,
    },
    "lead": {
        "label": "Lead / Principal",
        "register": "Senior practitioner. Emphasise technical judgement and influence without authority.",
        "foreground": "technical direction, systems design, mentoring, standards you set",
        "background": "headcount and budget figures",
        "verbs": "designed, architected, led, introduced, mentored",
        "summary_words": 50,
        "bullets_per_role": 5,
    },
    "ic": {
        "label": "Individual contributor",
        "register": "Practitioner. Concrete, specific, craft-focused. Show the work, not the org chart.",
        "foreground": "what you personally built and shipped, tools and methods, measurable results",
        "background": "org design, headcount, board exposure",
        "verbs": "built, shipped, implemented, analysed, automated",
        "summary_words": 50,
        "bullets_per_role": 5,
    },
}


def detect_seniority(role: str = "", jd_text: str = "") -> dict:
    """Infer the seniority level of a target role.

    Returns {level, label, confidence, signals} where `signals` explains the
    read so the UI can show it and the user can override.
    """
    role = (role or "").lower()
    jd = (jd_text or "").lower()
    signals = []

    title_level = None
    for level, pattern in _TITLE_PATTERNS:
        if re.search(pattern, role, re.I):
            title_level = level
            match = re.search(pattern, role, re.I)
            signals.append(f"title: “{match.group(0)}” → {level}")
            break

    scores = {lvl: 0 for lvl in LEVELS}
    if title_level:
        scores[title_level] += 5

    for level, weight, pattern in _JD_SIGNALS:
        hits = len(re.findall(pattern, jd, re.I))
        if hits:
            scores[level] += weight * min(hits, 3)
            signals.append(f"JD mentions {level} signals ×{hits}")

    best = max(scores, key=lambda k: scores[k])
    top = scores[best]
    if top == 0:
        # Nothing to go on — assume a senior IC/lead posting rather than guess high.
        return {
            "level": "lead",
            "label": TONE_PROFILES["lead"]["label"],
            "confidence": "low",
            "signals": ["no clear seniority signals — defaulted to Lead"],
        }

    runner_up = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
    if top >= 5 and top - runner_up >= 3:
        confidence = "high"
    elif top - runner_up >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "level": best,
        "label": TONE_PROFILES[best]["label"],
        "confidence": confidence,
        "signals": signals,
    }


def tone_profile(level: str) -> dict:
    """Tone profile for a level, falling back to `lead` for unknown values."""
    return TONE_PROFILES.get(level, TONE_PROFILES["lead"])


def tone_instructions(level: str) -> str:
    """Prompt fragment describing how to write for this seniority level."""
    p = tone_profile(level)
    return (
        f"SENIORITY: {p['label']}\n"
        f"- Register: {p['register']}\n"
        f"- Foreground: {p['foreground']}.\n"
        f"- Play down: {p['background']}.\n"
        f"- Preferred verbs: {p['verbs']}.\n"
        f"- Summary length: about {p['summary_words']} words.\n"
        f"- Keep at most {p['bullets_per_role']} bullets per role."
    )
