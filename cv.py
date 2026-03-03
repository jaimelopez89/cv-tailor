#!/usr/bin/env python3
"""CV Tailor — Generate publication-quality, tailored PDF CVs from a structured YAML master profile.

Usage:
    python cv.py --target "Dir Product Marketing, Anthropic" --jd jd.txt --ai
    python cv.py --corrections fixes.txt --preview
    python cv.py --interactive
    python cv.py --list-targets
"""

import argparse
import copy
import difflib
import os
import platform
import re
import subprocess
import sys

import yaml

from engine.correct import apply_corrections
from engine.importer import import_from_pdf, import_from_text
from engine.layout import render, render_html
from engine.tailor import list_targets, load_target, save_target, tailor
from engine.templates import list_templates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_PATH = os.path.join(DATA_DIR, "master_profile.yaml")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")


def main():
    parser = argparse.ArgumentParser(
        description="CV Tailor — tailored PDF CVs from a YAML master profile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python cv.py --target "Dir Product Marketing, Anthropic" --jd jd.txt --ai
  python cv.py --corrections fixes.txt --preview
  python cv.py --interactive
  python cv.py --list-targets
  python cv.py --show experience.ververica""",
    )
    parser.add_argument("--target", help="Target role (saved name or 'Role, Company')")
    parser.add_argument("--jd", help="Job description file to analyse")
    parser.add_argument("--corrections", help="Corrections file to apply")
    parser.add_argument("--output", help="Output PDF path (default: auto-named)")
    parser.add_argument("--ai", action="store_true", help="Use Claude API for tailoring")
    parser.add_argument("--rewrite", action="store_true", help="Allow AI to rewrite bullets")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive REPL")
    parser.add_argument("--preview", action="store_true", help="Open generated PDF immediately")
    parser.add_argument("--list-targets", action="store_true", help="Show saved target briefs")
    parser.add_argument("--show", metavar="SECTION", help="Print content for a section")
    parser.add_argument("--diff", action="store_true", help="Show what changed from master")
    parser.add_argument("--template", default="ember", help="Template name (ember, meridian, slate, verdant, folio)")
    parser.add_argument("--html", action="store_true", help="Also generate HTML output")
    parser.add_argument("--list-templates", action="store_true", help="Show available templates")
    parser.add_argument("--import-pdf", metavar="FILE", help="Import CV from PDF into master profile")
    parser.add_argument("--import-text", metavar="FILE", help="Import CV from text file into master profile")

    args = parser.parse_args()

    if getattr(args, "import_pdf", None):
        profile = import_from_pdf(args.import_pdf, MASTER_PATH)
        print(f"Imported from PDF into {MASTER_PATH}")
        print("IMPORTANT: Review data/master_profile.yaml and verify every field.")
        print("Move content from _raw_import into the correct sections.")
        return

    if getattr(args, "import_text", None):
        with open(args.import_text, "rb") as f:
            raw = f.read()
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("utf-8", errors="replace")
        profile = import_from_text(text, MASTER_PATH)
        print(f"Imported from text into {MASTER_PATH}")
        print("IMPORTANT: Review data/master_profile.yaml and verify every field.")
        print("Move content from _raw_import into the correct sections.")
        return

    if args.list_templates:
        print("Available templates:")
        for name, desc in list_templates():
            marker = " (default)" if name == "ember" else ""
            print(f"  {name:12s} {desc}{marker}")
        return

    if args.list_targets:
        targets = list_targets()
        if targets:
            print("Saved targets:")
            for t in targets:
                print(f"  {t}")
        else:
            print("No saved targets. Use --target to create one.")
        return

    if args.interactive:
        _run_repl(args)
        return

    if args.show:
        _show_section(args.show)
        return

    # Main pipeline: load → tailor → correct → render
    content = _run_pipeline(args)
    if content:
        output_path = _resolve_output_path(args, content)
        render(content, output_path, template_name=args.template)
        print(f"PDF generated: {output_path}")

        if args.html:
            html_path = output_path.rsplit(".", 1)[0] + ".html"
            render_html(content, html_path, template_name=args.template)
            print(f"HTML generated: {html_path}")

        if args.diff:
            _show_diff(content)

        if args.preview:
            _open_file(output_path)


def _run_pipeline(args) -> dict:
    """Execute the main tailoring pipeline, returning content dict."""
    # Build target
    target = {}
    if args.target:
        target = load_target(args.target)

    # Load JD text
    if args.jd and os.path.isfile(args.jd):
        with open(args.jd, "r") as f:
            target["jd_text"] = f.read()

    # Tailor
    if args.target or args.ai:
        content = tailor(MASTER_PATH, target, ai=args.ai, rewrite=args.rewrite)
    else:
        # No target — render master as-is
        with open(MASTER_PATH, "r") as f:
            content = yaml.safe_load(f)
        # Resolve summary
        summary = content.get("summary", {})
        if isinstance(summary, dict):
            content["summary"] = summary.get("default", "")

    # Save intermediate YAML
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    intermediate_path = os.path.join(OUTPUT_DIR, "tailored_content.yaml")
    _save_intermediate(content, intermediate_path, target)

    # Apply corrections
    if args.corrections and os.path.isfile(args.corrections):
        content = apply_corrections(content, args.corrections)

    return content


def _resolve_output_path(args, content) -> str:
    """Determine output PDF path."""
    if args.output:
        return args.output

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    name = content.get("meta", {}).get("name", "CV").replace(" ", "_")
    target = content.get("_target", {})
    company = target.get("company", "").replace(" ", "_")
    if company:
        return os.path.join(OUTPUT_DIR, f"{name}_{company}.pdf")
    return os.path.join(OUTPUT_DIR, f"{name}_CV.pdf")


def _save_intermediate(content: dict, path: str, target: dict):
    """Save tailored content YAML for inspection."""
    output = copy.deepcopy(content)
    output.pop("_target", None)

    header = "# AUTO-GENERATED — safe to edit manually\n"
    if target:
        header += f"# Target: {target.get('role', '')} at {target.get('company', '')}\n"
    header += f"# Generated: {_today()}\n\n"

    with open(path, "w") as f:
        f.write(header)
        yaml.dump(output, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _show_section(section_path: str):
    """Print a section from the master profile."""
    with open(MASTER_PATH, "r") as f:
        master = yaml.safe_load(f)

    parts = section_path.split(".")
    data = master
    for part in parts:
        if isinstance(data, dict):
            data = data.get(part)
        elif isinstance(data, list):
            # Try to find by id
            found = None
            for item in data:
                if isinstance(item, dict) and item.get("id") == part:
                    found = item
                    break
            data = found
        else:
            data = None
        if data is None:
            print(f"Section '{section_path}' not found.")
            return

    print(yaml.dump(data, default_flow_style=False, allow_unicode=True))


def _show_diff(content: dict):
    """Show diff between master profile and tailored content."""
    with open(MASTER_PATH, "r") as f:
        master = yaml.safe_load(f)

    master_yaml = yaml.dump(master, default_flow_style=False, allow_unicode=True, sort_keys=False)
    content_clean = copy.deepcopy(content)
    content_clean.pop("_target", None)
    content_yaml = yaml.dump(content_clean, default_flow_style=False, allow_unicode=True, sort_keys=False)

    diff = difflib.unified_diff(
        master_yaml.splitlines(keepends=True),
        content_yaml.splitlines(keepends=True),
        fromfile="master_profile.yaml",
        tofile="tailored_content.yaml",
    )

    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            print(f"\033[32m{line}\033[0m", end="")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"\033[31m{line}\033[0m", end="")
        elif line.startswith("@@"):
            print(f"\033[36m{line}\033[0m", end="")
        else:
            print(line, end="")


def _open_file(path: str):
    """Open a file with the OS default application."""
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", path])
    elif system == "Linux":
        subprocess.run(["xdg-open", path])
    elif system == "Windows":
        os.startfile(path)


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


# ── Interactive REPL ─────────────────────────────────────────────────────

def _run_repl(args):
    """Interactive REPL for iterative CV editing."""
    print("CV Tailor — Interactive Mode")
    print("Type 'help' for commands.\n")

    # Initial load
    with open(MASTER_PATH, "r") as f:
        master = yaml.safe_load(f)

    content = copy.deepcopy(master)
    # Resolve summary
    summary = content.get("summary", {})
    if isinstance(summary, dict):
        content["summary"] = summary.get("default", "")

    undo_stack = []
    current_target = {}
    last_pdf_path = None

    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not line:
            continue

        cmd_parts = line.split(None, 1)
        cmd = cmd_parts[0].lower()
        rest = cmd_parts[1] if len(cmd_parts) > 1 else ""

        if cmd == "quit" or cmd == "exit" or cmd == "q":
            print("Bye!")
            break

        elif cmd == "help":
            _repl_help()

        elif cmd == "show":
            _repl_show(content, rest)

        elif cmd == "edit":
            undo_stack.append(copy.deepcopy(content))
            _repl_edit(content, rest)

        elif cmd == "target":
            undo_stack.append(copy.deepcopy(content))
            target_name = rest.strip().strip('"').strip("'")
            if not target_name:
                print("Usage: target \"Role, Company\"")
                continue
            current_target = load_target(target_name)
            content = tailor(MASTER_PATH, current_target, ai=args.ai, rewrite=args.rewrite)
            print(f"Re-tailored for: {current_target.get('role', '')} at {current_target.get('company', '')}")

        elif cmd == "preview":
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            last_pdf_path = os.path.join(OUTPUT_DIR, "preview.pdf")
            render(content, last_pdf_path, template_name=args.template)
            print(f"Generated: {last_pdf_path}")
            _open_file(last_pdf_path)

        elif cmd == "save":
            filename = rest.strip() or "cv_output.pdf"
            if not filename.endswith(".pdf"):
                filename += ".pdf"
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            out_path = os.path.join(OUTPUT_DIR, filename)
            render(content, out_path, template_name=args.template)
            print(f"Saved: {out_path}")

        elif cmd == "diff":
            _show_diff(content)

        elif cmd == "undo":
            if undo_stack:
                content = undo_stack.pop()
                print("Undone.")
            else:
                print("Nothing to undo.")

        elif cmd == "corrections" or cmd == "correct":
            path = rest.strip()
            if not path or not os.path.isfile(path):
                print("Usage: corrections <file_path>")
                continue
            undo_stack.append(copy.deepcopy(content))
            content = apply_corrections(content, path)
            print("Corrections applied.")

        else:
            print(f"Unknown command: {cmd}. Type 'help' for commands.")


def _repl_help():
    print("""Commands:
  show [section]          Show current content (e.g., 'show summary', 'show experience.ververica')
  edit <section>: <text>  Edit a section (e.g., 'edit summary: New summary text')
  target "Role, Company"  Re-tailor for a new target
  preview                 Generate and open PDF
  save [filename.pdf]     Save PDF to output directory
  diff                    Show changes from master profile
  undo                    Undo last change
  corrections <file>      Apply corrections file
  help                    Show this help
  quit                    Exit""")


def _repl_show(content: dict, section: str):
    """Show a section of the current content."""
    if not section:
        # Show overview
        print(f"Name: {content.get('meta', {}).get('name', '')}")
        summary = content.get("summary", "")
        print(f"Summary: {summary[:100]}...")
        print(f"Metrics: {len(content.get('metrics', []))}")
        print(f"Experience entries: {len(content.get('experience', []))}")
        for e in content.get("experience", []):
            print(f"  - {e.get('company', '')} ({len(e.get('bullets', []))} bullets)")
        print(f"Ventures: {len(content.get('ventures', []))}")
        print(f"Education: {len(content.get('education', []))}")
        print(f"Speaking: {len(content.get('speaking', []))}")
        print(f"Notable: {len(content.get('notable', []))}")
        return

    parts = section.strip().split(".")
    data = content
    for part in parts:
        if isinstance(data, dict):
            data = data.get(part)
        elif isinstance(data, list):
            found = None
            for item in data:
                if isinstance(item, dict) and item.get("id") == part:
                    found = item
                    break
            data = found
        else:
            data = None
        if data is None:
            print(f"Section '{section}' not found.")
            return

    if isinstance(data, str):
        print(data)
    else:
        print(yaml.dump(data, default_flow_style=False, allow_unicode=True))


def _repl_edit(content: dict, instruction: str):
    """Apply a simple edit instruction."""
    if ":" not in instruction:
        print("Usage: edit <section>: <new value or instruction>")
        return

    section, value = instruction.split(":", 1)
    section = section.strip()
    value = value.strip()

    if section == "summary":
        # Check for Replace instruction
        m = re.match(r'Replace\s+"(.+?)"\s+with\s+"(.+?)"', value)
        if m:
            old, new = m.group(1), m.group(2)
            content["summary"] = content.get("summary", "").replace(old, new)
            print(f"Replaced '{old}' with '{new}' in summary.")
        else:
            content["summary"] = value
            print("Summary updated.")
    elif "." in section:
        # Handle nested paths like experience.ververica.bullet.0
        print(f"Edit applied to {section}.")
        # Delegate to correction engine for complex edits
        _repl_apply_single_correction(content, f"{section}: {value}")
    else:
        if section in content:
            content[section] = value
            print(f"{section} updated.")
        else:
            print(f"Section '{section}' not found.")


def _repl_apply_single_correction(content: dict, line: str):
    """Apply a single correction line to content."""
    from engine.correct import _apply_correction, _parse_line
    correction = _parse_line(line)
    if correction:
        _apply_correction(content, correction)
        print("Applied.")
    else:
        print(f"Could not parse edit: {line}")


if __name__ == "__main__":
    main()
