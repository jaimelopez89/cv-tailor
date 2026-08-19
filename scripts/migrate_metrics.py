#!/usr/bin/env python
"""One-off migration: turn sentence-shaped metrics into value/label pairs.

Imported profiles store metrics as a single sentence, which every CV template
renders as an empty cell. This splits them with a regex, optionally sharpens the
captions with an LLM, and writes the profile back after taking a backup.

    python scripts/migrate_metrics.py             # regex only, dry run
    python scripts/migrate_metrics.py --write     # regex only, write
    python scripts/migrate_metrics.py --ai --write

Captions the regex produces are serviceable but wordy; --ai shortens them to the
2-4 words the templates are designed around.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.metrics import normalize_metric  # noqa: E402

MASTER = Path(__file__).resolve().parent.parent / "data" / "master_profile.yaml"
MODEL = "claude-opus-5"


def sharpen_labels(metrics: list[dict]) -> list[dict]:
    """Ask Claude to shorten each label to a caption. Values are never touched."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — keeping regex labels.")
        return metrics

    payload = [{"value": m["value"], "label": m["label"]} for m in metrics]
    prompt = (
        "These are headline CV metrics. Rewrite each `label` as a caption of 2-4 "
        "words that sits under the figure — a noun phrase, no verbs, no trailing "
        "punctuation, capitalised like a title. Keep every `value` exactly as it "
        "is. Do not invent metrics or change any number.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        'Return only JSON: {"metrics": [{"value": "...", "label": "..."}]}'
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    if message.stop_reason == "refusal":
        print("  Request declined — keeping regex labels.")
        return metrics

    text = "".join(b.text for b in message.content if b.type == "text").strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.split("\n") if not l.startswith("```"))

    try:
        improved = json.loads(text)["metrics"]
    except Exception as e:
        print(f"  Could not parse response ({e}) — keeping regex labels.")
        return metrics

    for metric, better in zip(metrics, improved):
        if isinstance(better, dict) and better.get("label"):
            metric["label"] = better["label"]
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write changes to the profile")
    parser.add_argument("--ai", action="store_true", help="use Claude to shorten labels")
    parser.add_argument("--profile", default=str(MASTER), help="path to master_profile.yaml")
    args = parser.parse_args()

    path = Path(args.profile)
    if not path.exists():
        print(f"Profile not found: {path}")
        return 1

    with open(path) as f:
        profile = yaml.safe_load(f) or {}

    original = profile.get("metrics") or []
    if not original:
        print("No metrics to migrate.")
        return 0

    migrated = [normalize_metric(m) for m in original]
    for m in migrated:
        m.pop("text", None)

    if args.ai:
        print("Sharpening labels with Claude…")
        migrated = sharpen_labels(migrated)

    print(f"\n{len(migrated)} metric(s):\n")
    for before, after in zip(original, migrated):
        source = before.get("text") if isinstance(before, dict) else str(before)
        if source:
            print(f"  {source}")
        print(f"    → value: {after['value']!r}")
        print(f"      label: {after['label']!r}\n")

    unusable = [m for m in migrated if not m["value"] and not m["label"]]
    if unusable:
        print(f"⚠ {len(unusable)} metric(s) could not be split — fill them in the Edit tab.\n")

    if not args.write:
        print("Dry run. Re-run with --write to apply.")
        return 0

    backup = path.with_suffix(f".backup-{datetime.now():%Y%m%d-%H%M%S}.yaml")
    shutil.copy2(path, backup)
    print(f"Backup: {backup}")

    profile["metrics"] = migrated
    with open(path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
