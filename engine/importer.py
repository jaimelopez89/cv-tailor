"""Profile importer — populates master_profile.yaml from user-provided source documents.

Supported sources:
  - PDF files (existing CV/resume)
  - Text files (pasted content, LinkedIn export)
  - Direct text input

CRITICAL: This module extracts and structures content from source documents.
It NEVER fabricates, embellishes, or invents any information.
Every field in the output must trace directly to the source material.
"""

import os
import re

import yaml


def import_from_text(text: str, master_path: str, merge: bool = True) -> dict:
    """Parse unstructured text into master profile YAML structure.

    Args:
        text: Raw text content from CV, LinkedIn, or user input
        master_path: Path to master_profile.yaml to write/merge into
        merge: If True, merge into existing profile. If False, overwrite.
    """
    text = _clean_encoding(text)
    profile = _parse_text_to_profile(text)

    if merge and os.path.isfile(master_path):
        with open(master_path, "r") as f:
            existing = yaml.safe_load(f) or {}
        profile = _merge_profiles(existing, profile)

    with open(master_path, "w") as f:
        f.write("# Master Profile - populated from source documents\n")
        f.write("# Review and correct this file before generating CVs.\n")
        f.write("# Every entry must be verified against your source material.\n\n")
        yaml.dump(profile, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return profile


def import_from_pdf(pdf_path: str, master_path: str, merge: bool = True) -> dict:
    """Extract text from PDF and parse into master profile."""
    text = _extract_pdf_text(pdf_path)
    if not text.strip():
        raise ValueError(f"Could not extract text from {pdf_path}. "
                         "Try copying the PDF content as text and using --import-text instead.")

    print(f"Extracted {len(text)} characters from {os.path.basename(pdf_path)}")
    return import_from_text(text, master_path, merge=merge)


def _extract_pdf_text(pdf_path: str) -> str:
    """Extract text from PDF using available libraries."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except ImportError:
        pass

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except ImportError:
        pass

    raise ImportError(
        "PDF import requires 'pdfplumber' or 'PyPDF2'. "
        "Install with: pip install pdfplumber\n"
        "Or copy your CV text and use --import-text instead."
    )


# ── Encoding cleanup ────────────────────────────────────────────────────

def _clean_encoding(text: str) -> str:
    """Fix common encoding artifacts from cp1252/latin1 misreads."""
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Common cp1252 misread artifacts
    replacements = {
        "\u0096": "-",    # en dash
        "\u0097": "-",    # em dash
        "\u0091": "'",    # left single quote
        "\u0092": "'",    # right single quote
        "\u0093": '"',    # left double quote
        "\u0094": '"',    # right double quote
        "\u0095": "-",    # bullet
        "\u00d1": "-",    # Ñ used as dash in date ranges
        "\u00a5": " - ",  # ¥ used as separator
        "\u2013": "-",    # en dash
        "\u2014": " - ",  # em dash
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2026": "...",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ── Section-based parser ────────────────────────────────────────────────

# Section headers commonly found in CVs
_SECTION_HEADERS = [
    "profile", "summary", "about", "about me", "professional summary",
    "objective", "personal statement",
    "experience", "employment history", "work experience", "professional experience",
    "work history", "career history",
    "education", "academic background", "qualifications",
    "skills", "core competencies", "technical skills", "key skills",
    "expertise", "areas of expertise",
    "languages",
    "certifications", "certificates",
    "speaking", "presentations", "conferences",
    "publications",
    "projects", "ventures", "advisory",
    "awards", "honors", "achievements",
    "interests", "hobbies", "notable", "beyond work",
    "details", "contact", "personal details", "personal information",
    "references",
]


def _parse_text_to_profile(text: str) -> dict:
    """Parse CV text into structured profile by detecting sections."""
    lines = text.split("\n")

    profile = {
        "meta": {"name": "", "tagline": "", "location": "", "email": "", "web": "", "linkedin": ""},
        "summary": {"default": "", "variants": {}},
        "metrics": [],
        "experience": [],
        "ventures": [],
        "education": [],
        "skills": {"groups": []},
        "speaking": [],
        "notable": [],
    }

    # Extract contact info from entire text
    _extract_contact(profile, text)

    # Split text into sections
    sections = _split_into_sections(lines)

    # Process each section
    for header, content_lines in sections.items():
        header_lower = header.lower().strip()
        content_text = "\n".join(content_lines).strip()

        if not content_text:
            continue

        if header_lower in ("", "header"):
            # First block before any section header - extract name/tagline
            _extract_name_tagline(profile, content_lines)

        elif header_lower in ("profile", "summary", "about", "about me",
                              "professional summary", "objective", "personal statement"):
            profile["summary"]["default"] = content_text

        elif header_lower in ("experience", "employment history", "work experience",
                              "professional experience", "work history", "career history"):
            profile["experience"] = _parse_experience(content_lines)

        elif header_lower in ("education", "academic background", "qualifications"):
            profile["education"] = _parse_education(content_lines)

        elif header_lower in ("skills", "core competencies", "technical skills",
                              "key skills", "expertise", "areas of expertise"):
            profile["skills"] = _parse_skills(content_lines)

        elif header_lower == "languages":
            # Add languages as a skill group
            langs = [w.strip() for w in " ".join(content_lines).split() if w.strip()]
            if langs:
                existing = profile["skills"].get("groups", [])
                existing.append({"name": "Languages", "items": langs})
                profile["skills"]["groups"] = existing

        elif header_lower in ("speaking", "presentations", "conferences"):
            profile["speaking"] = _parse_speaking(content_lines)

        elif header_lower in ("projects", "ventures", "advisory"):
            profile["ventures"] = _parse_ventures(content_lines)

        elif header_lower in ("awards", "honors", "achievements", "notable",
                              "interests", "beyond work"):
            profile["notable"] = [l.strip() for l in content_lines if l.strip()]

    # Store raw text for reference
    profile["_raw_import"] = text
    profile["_import_note"] = (
        "Auto-imported from source document. Review every field for accuracy. "
        "Delete _raw_import and _import_note when done."
    )

    return profile


def _extract_contact(profile: dict, text: str):
    """Extract contact info (email, phone, LinkedIn, web) from full text."""
    meta = profile["meta"]

    # Email
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w{2,}", text)
    if m:
        meta["email"] = m.group()

    # LinkedIn
    m = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", text, re.I)
    if m:
        meta["linkedin"] = m.group()

    # Web URL (not linkedin, not email domain)
    for m in re.finditer(r"(?:https?://)?(?:www\.)?([a-z0-9][\w.-]+\.[a-z]{2,})", text, re.I):
        url = m.group(1)
        if "linkedin" not in url.lower() and "@" not in m.group() and "gmail" not in url.lower():
            meta["web"] = url
            break

    # Phone
    m = re.search(r"\+?\d[\d\s()-]{7,}\d", text)
    if m:
        meta["phone"] = m.group().strip()

    # Location - look for common city patterns near job entries
    for pattern in [r"(?:Location|City|Based in)[:\s]+([^\n,]+)", r" - ([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*)\s*$"]:
        m = re.search(pattern, text)
        if m:
            meta["location"] = m.group(1).strip()
            break


def _extract_name_tagline(profile: dict, lines: list):
    """Extract name and tagline from the header section."""
    meta = profile["meta"]
    clean = [l.strip() for l in lines if l.strip()]

    # Skip lines that are clearly contact info
    for line in clean:
        if re.search(r"[@+]|phone|email|linkedin|details", line, re.I):
            continue
        if len(line) < 3 or len(line) > 80:
            continue

        # First non-contact line with reasonable length is likely name + possibly title
        # Common patterns: "Name Title" or just "Name"
        # Try to detect if it contains a known title
        title_patterns = [
            r"(.*?)\s+(Chief\s+\w+\s+Officer|C[A-Z]O|VP\s+\w+|Vice\s+President|Director|Head\s+of|"
            r"Senior\s+\w+|Manager|Lead|Engineer|Consultant|Architect|Designer|Analyst|"
            r"Marketing\s+\w+|Product\s+\w+|General\s+Manager)(.*)$"
        ]
        found = False
        for tp in title_patterns:
            m = re.match(tp, line, re.I)
            if m:
                meta["name"] = m.group(1).strip()
                meta["tagline"] = (m.group(2) + m.group(3)).strip()
                found = True
                break

        if not found:
            # Just take the first clean line as name
            if not meta["name"]:
                meta["name"] = line

        if meta["name"]:
            break


def _split_into_sections(lines: list) -> dict:
    """Split lines into named sections based on headers."""
    sections = {}
    current = "header"
    sections[current] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            sections.setdefault(current, []).append("")
            continue

        # Check if this line is a section header
        if _is_section_header(stripped):
            current = stripped
            sections[current] = []
        else:
            sections.setdefault(current, []).append(stripped)

    return sections


def _is_section_header(line: str) -> bool:
    """Check if a line is a section header."""
    clean = line.strip().rstrip(":")
    if clean.lower() in _SECTION_HEADERS:
        return True
    # Also match "SKILLS" (all caps), "Skills:", etc.
    if clean.lower().rstrip(":") in _SECTION_HEADERS:
        return True
    return False


# Date pattern for matching employment/education entries
_DATE_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\w*\.?\s+\d{4})"
    r"\s*[-\u2013\u2014]+\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\w*\.?\s+\d{4}|Present|Current|Now)",
    re.I,
)

# Simpler: just year range
_YEAR_RE = re.compile(r"(\d{4})\s*[-\u2013\u2014]+\s*(\d{4}|Present|Current|Now)", re.I)


def _parse_experience(lines: list) -> list:
    """Parse employment history into structured experience entries."""
    entries = []
    current_entry = None
    current_bullets = []

    for line in lines:
        if not line.strip():
            continue

        # Check if this line starts a new entry (contains a date range)
        date_match = _DATE_RE.search(line) or _YEAR_RE.search(line)
        if date_match:
            # Save previous entry
            if current_entry:
                current_entry["bullets"] = [{"text": b} for b in current_bullets if b.strip()]
                entries.append(current_entry)
                current_bullets = []

            # Parse this entry header
            date_start = date_match.start()
            header_part = line[:date_start].strip().rstrip(",").strip()
            period = f"{date_match.group(1)} - {date_match.group(2)}"

            # After the date, look for location
            after_date = line[date_match.end():].strip()
            location = ""
            # Location often follows date with separator
            loc_match = re.match(r"[-\u00b7\u2022\|,]+\s*(.+)", after_date)
            if loc_match:
                location = loc_match.group(1).strip()

            # Split header into title and company
            # Common patterns: "Title, Company" or "Title at Company"
            title, company, subtitle = _split_role_company(header_part)

            current_entry = {
                "company": company,
                "subtitle": subtitle,
                "roles": [{"title": title, "period": period, "location": location}],
                "bullets": [],
            }
        elif current_entry:
            # This is a description/bullet line for the current entry
            stripped = line.strip()
            # Remove leading bullet markers
            stripped = re.sub(r"^[-\u2022\u2023\u25cf\u25cb\u2013\u2014\u25b8\u25b9\*>]+\s*", "", stripped)
            if stripped:
                current_bullets.append(stripped)

    # Don't forget the last entry
    if current_entry:
        current_entry["bullets"] = [{"text": b} for b in current_bullets if b.strip()]
        entries.append(current_entry)

    # Post-process: merge entries with same company
    entries = _merge_same_company(entries)

    return entries


def _split_role_company(header: str) -> tuple:
    """Split 'Title, Company Name' into (title, company, subtitle).

    Returns (title, company, subtitle).
    """
    # Try "Title, Company Suffix" pattern
    # Look for company indicators
    company_suffixes = [
        "Inc", "LLC", "Ltd", "GmbH", "AG", "Corp", "Co", "SA", "BV", "NV",
        "Oy", "AB", "AS", "Plc", "Group", "Holdings",
    ]

    # Try splitting on last comma before company
    parts = header.split(",")
    if len(parts) >= 2:
        # Check if last part looks like a company
        last = parts[-1].strip()
        # If there are company suffixes in the last part, it's title, company
        for suffix in company_suffixes:
            if suffix.lower() in last.lower():
                company = last
                title = ",".join(parts[:-1]).strip()
                return title, company, ""

        # If there are 3+ parts, middle might be company
        if len(parts) >= 3:
            company = parts[-1].strip()
            title = parts[0].strip()
            subtitle = ""
            return title, company, subtitle

        # Default: first part is title, rest is company
        title = parts[0].strip()
        company = ",".join(parts[1:]).strip()
        return title, company, ""

    return header, "", ""


def _merge_same_company(entries: list) -> list:
    """Merge consecutive entries at the same company into multi-role entries."""
    if not entries:
        return entries

    merged = []
    for entry in entries:
        if (merged and
            merged[-1]["company"] and
            entry["company"] and
            _normalize_company(merged[-1]["company"]) == _normalize_company(entry["company"])):
            # Same company - merge roles
            merged[-1]["roles"].extend(entry["roles"])
            merged[-1]["bullets"].extend(entry["bullets"])
        else:
            merged.append(entry)

    return merged


def _normalize_company(name: str) -> str:
    """Normalize company name for comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _parse_education(lines: list) -> list:
    """Parse education entries."""
    entries = []
    current = None

    for line in lines:
        if not line.strip():
            continue

        date_match = _DATE_RE.search(line) or _YEAR_RE.search(line)
        if date_match:
            if current:
                entries.append(current)

            header_part = line[:date_match.start()].strip().rstrip(",").strip()
            period = f"{date_match.group(1)} - {date_match.group(2)}"

            after_date = line[date_match.end():].strip()
            location = ""
            loc_match = re.match(r"[-\u00b7\u2022\|,]+\s*(.+)", after_date)
            if loc_match:
                location = loc_match.group(1).strip()

            # Split into school and degree
            school, degree = _split_school_degree(header_part)

            current = {
                "school": school,
                "degree": degree,
                "period": period,
                "details": [],
            }
            if location:
                current["details"].append(location)
        elif current:
            stripped = line.strip()
            if stripped:
                current["details"].append(stripped)

    if current:
        entries.append(current)

    return entries


def _split_school_degree(header: str) -> tuple:
    """Split education header into (school, degree)."""
    # Common patterns:
    # "MIT, MicroMasters Program (MITx), Statistics and Data Science"
    # "University Name, M.Sc. in Something"

    # Look for degree indicators
    degree_patterns = [
        r"(B\.?S\.?c?|M\.?S\.?c?|Ph\.?D|MBA|B\.?A\.?|M\.?A\.?|MicroMasters|Bachelor|Master|Doctor)",
    ]

    parts = header.split(",")
    if len(parts) >= 2:
        # First part is usually the school
        school = parts[0].strip()
        degree = ",".join(parts[1:]).strip()
        return school, degree

    return header, ""


def _parse_skills(lines: list) -> dict:
    """Parse skills into groups."""
    all_text = " ".join(l.strip() for l in lines if l.strip())

    # Check if skills are grouped with headers (e.g., "Technical: Python, R, SQL")
    groups = []
    group_pattern = re.compile(r"([A-Z][\w\s&]+?):\s*(.+?)(?=\n[A-Z]|\Z)", re.S)
    matches = list(group_pattern.finditer(all_text))

    if matches:
        for m in matches:
            name = m.group(1).strip()
            items = [i.strip() for i in re.split(r"[,;|]", m.group(2)) if i.strip()]
            if items:
                groups.append({"name": name, "items": items})
    else:
        # No grouping detected - split by common separators
        items = [i.strip() for i in re.split(r"[,;|\n]", all_text) if i.strip()]
        # If items are space-separated single words, try that too
        if len(items) <= 1 and all_text:
            # Might be space-separated
            items = [w.strip() for w in all_text.split() if w.strip() and len(w.strip()) > 1]
        if items:
            groups.append({"name": "Skills", "items": items})

    return {"groups": groups}


def _parse_speaking(lines: list) -> list:
    """Parse speaking/conference entries."""
    entries = []
    for line in lines:
        if not line.strip():
            continue
        year_match = re.search(r"\b(20\d{2})\b", line)
        title = line.strip()
        year = ""
        if year_match:
            year = year_match.group(1)
            # Remove year from title if it's at the end
            title = line[:year_match.start()].strip().rstrip(",.-")
        entries.append({"title": title, "year": year})
    return entries


def _parse_ventures(lines: list) -> list:
    """Parse ventures/projects entries."""
    entries = []
    for line in lines:
        if not line.strip():
            continue
        entries.append({
            "name": line.strip(),
            "period": "",
            "description": "",
        })
    return entries


def _merge_profiles(existing: dict, new: dict) -> dict:
    """Merge new profile data into existing, preferring new non-empty values."""
    merged = dict(existing)

    # Merge meta: fill empty fields
    if "meta" in new:
        merged_meta = merged.get("meta", {})
        for key, value in new["meta"].items():
            if value and not merged_meta.get(key):
                merged_meta[key] = value
        merged["meta"] = merged_meta

    # Replace empty sections with parsed ones
    for key in ("experience", "education", "ventures", "speaking", "notable"):
        if new.get(key) and not merged.get(key):
            merged[key] = new[key]

    # Merge summary
    new_summary = new.get("summary", {})
    if isinstance(new_summary, dict):
        new_default = new_summary.get("default", "")
    else:
        new_default = str(new_summary)
    existing_summary = merged.get("summary", {})
    if isinstance(existing_summary, dict):
        existing_default = existing_summary.get("default", "")
    else:
        existing_default = str(existing_summary)
    if new_default and not existing_default:
        merged["summary"] = new.get("summary", merged.get("summary"))

    # Merge skills
    new_groups = new.get("skills", {}).get("groups", [])
    existing_groups = merged.get("skills", {}).get("groups", [])
    if new_groups and not existing_groups:
        merged["skills"] = new["skills"]

    # Keep raw import
    if "_raw_import" in new:
        merged["_raw_import"] = new["_raw_import"]
    if "_import_note" in new:
        merged["_import_note"] = new["_import_note"]

    return merged
