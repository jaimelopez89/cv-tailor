"""Correction engine — applies text overlays to tailored content without mutating master.

Corrections are overlays: they stack on top of tailored content.
The master profile is never modified.
"""

import copy
import re
import warnings
from dataclasses import dataclass
from typing import Optional


@dataclass
class Correction:
    action: str  # set, replace_bullet, add_bullet, remove, reorder, hide, add
    section: str
    path: str
    value: Optional[str] = None


def apply_corrections(content: dict, corrections_path: str) -> dict:
    """Apply corrections from file to content dict. Returns new dict (content is not mutated)."""
    result = copy.deepcopy(content)

    with open(corrections_path, "r") as f:
        lines = f.readlines()

    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            correction = _parse_line(line)
            if correction:
                _apply_correction(result, correction)
        except Exception as e:
            warnings.warn(f"Correction line {line_num} skipped: {e}")

    return result


def _unquote(s: str) -> str:
    """Strip matched outer quotes only."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _parse_line(line: str) -> Optional[Correction]:
    """Parse a correction line into a Correction object."""

    # summary: "new text"
    if line.startswith("summary:"):
        value = _unquote(line.split(":", 1)[1].strip())
        return Correction("set", "summary", "", value)

    # experience.order: id1, id2, id3
    if line.startswith("experience.order:"):
        value = line.split(":", 1)[1].strip()
        return Correction("reorder", "experience", "order", value)

    # <section_id>.bullet.add: "text"
    m = re.match(r"(\w+)\.bullet\.add:\s*(.+)", line)
    if m:
        section_id = m.group(1)
        value = _unquote(m.group(2))
        return Correction("add_bullet", "experience", section_id, value)

    # <section_id>.bullet.remove.<N>
    m = re.match(r"(\w+)\.bullet\.remove\.(\d+)", line)
    if m:
        section_id = m.group(1)
        index = m.group(2)
        return Correction("remove", "experience_bullet", f"{section_id}.{index}", None)

    # <section_id>.bullet.<N>: "text"
    m = re.match(r"(\w+)\.bullet\.(\d+):\s*(.+)", line)
    if m:
        section_id = m.group(1)
        index = m.group(2)
        value = _unquote(m.group(3))
        return Correction("replace_bullet", "experience", f"{section_id}.{index}", value)

    # <section_id>.role.<N>.title: "text"
    m = re.match(r"(\w+)\.role\.(\d+)\.(\w+):\s*(.+)", line)
    if m:
        section_id = m.group(1)
        index = m.group(2)
        field = m.group(3)
        value = _unquote(m.group(4))
        return Correction("set", "experience_role", f"{section_id}.{index}.{field}", value)

    # metrics.<N>.value: "text" or metrics.<N>.label: "text"
    m = re.match(r"metrics\.(\d+)\.(\w+):\s*(.+)", line)
    if m:
        index = m.group(1)
        field = m.group(2)
        value = _unquote(m.group(3))
        return Correction("set", "metrics", f"{index}.{field}", value)

    # skills.add: "item" to "group"
    m = re.match(r'skills\.add:\s*"?(.+?)"?\s+to\s+"?(.+?)"?\s*$', line)
    if m:
        item = m.group(1)
        group = m.group(2)
        return Correction("add", "skills", group, item)

    # skills.remove: "item" from "group"
    m = re.match(r'skills\.remove:\s*"?(.+?)"?\s+from\s+"?(.+?)"?\s*$', line)
    if m:
        item = m.group(1)
        group = m.group(2)
        return Correction("remove", "skills", group, item)

    # skills.remove: "item" (from any group)
    m = re.match(r'skills\.remove:\s*(.+)', line)
    if m:
        item = _unquote(m.group(1))
        return Correction("remove", "skills_any", "", item)

    # speaking.remove: "keyword"
    m = re.match(r'speaking\.remove:\s*(.+)', line)
    if m:
        keyword = _unquote(m.group(1))
        return Correction("remove", "speaking", "", keyword)

    # notable.add: "text"
    m = re.match(r'notable\.add:\s*(.+)', line)
    if m:
        value = _unquote(m.group(1))
        return Correction("add", "notable", "", value)

    # notable.remove: "keyword"
    m = re.match(r'notable\.remove:\s*(.+)', line)
    if m:
        keyword = _unquote(m.group(1))
        return Correction("remove", "notable", "", keyword)

    # <section_id>.hide: true/false
    m = re.match(r"(\w+)\.hide:\s*(true|false)", line, re.IGNORECASE)
    if m:
        section_id = m.group(1)
        value = m.group(2).lower()
        return Correction("hide", "any", section_id, value)

    # speaking.show_max: N
    m = re.match(r"speaking\.show_max:\s*(\d+)", line)
    if m:
        return Correction("set", "speaking_max", "", m.group(1))

    # education.<id>.add_detail: "text"
    m = re.match(r"education\.(\w+)\.add_detail:\s*(.+)", line)
    if m:
        edu_id = m.group(1)
        value = _unquote(m.group(2))
        return Correction("add", "education_detail", edu_id, value)

    warnings.warn(f"Unrecognised correction: {line}")
    return None


def _apply_correction(content: dict, c: Correction):
    """Apply a single correction to the content dict."""

    if c.action == "set" and c.section == "summary":
        # Replace text in summary or set new summary
        if c.value and "Replace" in c.value:
            # Handle "Replace X with Y" syntax
            m = re.match(r'Replace\s+"(.+?)"\s+with\s+"(.+?)"', c.value)
            if m:
                old, new = m.group(1), m.group(2)
                summary = content.get("summary", "")
                content["summary"] = summary.replace(old, new)
                return
        content["summary"] = c.value

    elif c.action == "reorder" and c.section == "experience":
        ids = [x.strip() for x in c.value.split(",")]
        exp = content.get("experience", [])
        id_map = {e.get("id", ""): e for e in exp}
        reordered = [id_map[i] for i in ids if i in id_map]
        # Append any entries not in the reorder list
        seen = set(ids)
        for e in exp:
            if e.get("id", "") not in seen:
                reordered.append(e)
        content["experience"] = reordered

    elif c.action == "add_bullet" and c.section == "experience":
        for entry in content.get("experience", []):
            if entry.get("id") == c.path:
                bullets = entry.get("bullets", [])
                bullets.append({"text": c.value, "tags": [], "weight": 7})
                entry["bullets"] = bullets
                return
        warnings.warn(f"Experience entry '{c.path}' not found")

    elif c.action == "replace_bullet" and c.section == "experience":
        parts = c.path.split(".")
        if len(parts) == 2:
            entry_id, idx = parts[0], int(parts[1])
            for entry in content.get("experience", []):
                if entry.get("id") == entry_id:
                    bullets = entry.get("bullets", [])
                    if 0 <= idx < len(bullets):
                        if isinstance(bullets[idx], dict):
                            bullets[idx]["text"] = c.value
                        else:
                            bullets[idx] = c.value
                        return
                    warnings.warn(f"Bullet index {idx} out of range for '{entry_id}'")
                    return
            warnings.warn(f"Experience entry '{entry_id}' not found")

    elif c.action == "remove" and c.section == "experience_bullet":
        parts = c.path.split(".")
        if len(parts) == 2:
            entry_id, idx = parts[0], int(parts[1])
            for entry in content.get("experience", []):
                if entry.get("id") == entry_id:
                    bullets = entry.get("bullets", [])
                    if 0 <= idx < len(bullets):
                        bullets.pop(idx)
                        return

    elif c.action == "set" and c.section == "experience_role":
        parts = c.path.split(".")
        if len(parts) == 3:
            entry_id, idx, field = parts[0], int(parts[1]), parts[2]
            for entry in content.get("experience", []):
                if entry.get("id") == entry_id:
                    roles = entry.get("roles", [])
                    if 0 <= idx < len(roles):
                        roles[idx][field] = c.value
                        return

    elif c.action == "set" and c.section == "metrics":
        parts = c.path.split(".")
        if len(parts) == 2:
            idx, field = int(parts[0]), parts[1]
            metrics = content.get("metrics", [])
            if 0 <= idx < len(metrics):
                metrics[idx][field] = c.value

    elif c.action == "add" and c.section == "skills":
        groups = content.get("skills", {}).get("groups", [])
        for g in groups:
            if g.get("name", "").lower() == c.path.lower():
                g["items"].append(c.value)
                return
        warnings.warn(f"Skill group '{c.path}' not found")

    elif c.action == "remove" and c.section == "skills":
        groups = content.get("skills", {}).get("groups", [])
        for g in groups:
            if g.get("name", "").lower() == c.path.lower():
                g["items"] = [i for i in g["items"] if i.lower() != c.value.lower()]
                return

    elif c.action == "remove" and c.section == "skills_any":
        groups = content.get("skills", {}).get("groups", [])
        for g in groups:
            g["items"] = [i for i in g["items"] if i.lower() != c.value.lower()]

    elif c.action == "remove" and c.section == "speaking":
        speaking = content.get("speaking", [])
        content["speaking"] = [
            s for s in speaking
            if c.value.lower() not in (s.get("title", "") if isinstance(s, dict) else str(s)).lower()
        ]

    elif c.action == "add" and c.section == "notable":
        content.setdefault("notable", []).append(c.value)

    elif c.action == "remove" and c.section == "notable":
        notable = content.get("notable", [])
        content["notable"] = [n for n in notable if c.value.lower() not in n.lower()]

    elif c.action == "hide":
        _set_hidden(content, c.path, c.value == "true")

    elif c.action == "set" and c.section == "speaking_max":
        max_n = int(c.value)
        speaking = content.get("speaking", [])
        content["speaking"] = speaking[:max_n]

    elif c.action == "add" and c.section == "education_detail":
        for edu in content.get("education", []):
            if edu.get("id") == c.path:
                edu.setdefault("details", []).append(c.value)
                return
        warnings.warn(f"Education entry '{c.path}' not found")


def _set_hidden(content: dict, section_id: str, hidden: bool):
    """Set _hidden flag on a section entry by ID."""
    for section_key in ("experience", "ventures", "speaking"):
        entries = content.get(section_key, [])
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id") == section_id:
                entry["_hidden"] = hidden
                return
    # Try ventures by name
    for v in content.get("ventures", []):
        if isinstance(v, dict) and v.get("name", "").lower().startswith(section_id.lower()):
            v["_hidden"] = hidden
            return
    warnings.warn(f"Section '{section_id}' not found for hide operation")
