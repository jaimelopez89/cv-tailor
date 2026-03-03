# CV Tailor

Generate publication-quality, tailored PDF CVs from a structured YAML master profile.

Each target role gets a precisely tailored CV — different bullet emphasis, reordered experience, selected metrics — without touching layout code. Content is data. Layout is code. They never touch each other.

## Core Principle: No Fabrication

**Every fact in the output must come from user-provided sources.** The tool never invents, embellishes, or hallucinates content. Accepted sources:

- Your existing CV/resume (PDF or text)
- Your LinkedIn profile
- Text you paste or provide directly
- Job descriptions you supply
- URLs you explicitly provide

The tool *selects, reorders, and reformats* your real content. It does not create content from thin air.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# 1. Import your existing CV
python cv.py --import-pdf my_cv.pdf
# or
python cv.py --import-text my_cv.txt

# 2. Review and complete the master profile
#    (edit data/master_profile.yaml — add tags, weights, variants)

# 3. Generate a CV
python cv.py --preview

# 4. Tailor for a specific role
python cv.py --target "Dir Product Marketing, Anthropic" --jd jd.txt --preview

# 5. AI-assisted tailoring (requires ANTHROPIC_API_KEY)
python cv.py --target "Dir Product Marketing, Anthropic" --jd jd.txt --ai --preview
```

Fonts are downloaded automatically on first run (~2MB from Google Fonts).

## Workflow

### Step 1: Import your source material

```bash
# From a PDF CV
python cv.py --import-pdf /path/to/your_cv.pdf

# From a text file (e.g., LinkedIn copy-paste)
python cv.py --import-text /path/to/profile.txt
```

The importer extracts what it can and puts the raw text into `_raw_import` in the YAML. You then review the file and move content into the correct sections.

### Step 2: Populate the master profile

Edit `data/master_profile.yaml`. Structure:

```yaml
meta:         # name, tagline, contact info
summary:      # default + tagged variants for different positioning
metrics:      # quantified achievements with tags and weights
experience:   # companies -> roles -> bullets (each with tags + weight)
ventures:     # side projects and advisory work
education:    # degrees and certifications
skills:       # grouped skill lists with tags
speaking:     # talks and podcasts
notable:      # personal highlights
```

Every bullet and metric has **tags** (for matching to targets) and **weights** (1-10 priority). The tailoring engine uses these to select the strongest content for each role.

### Step 3: Create target briefs

```yaml
# data/targets/anthropic_pm.yaml
company: "Anthropic"
role: "Director of Product Marketing"
emphasis:
  - AI/ML product expertise
  - Developer audience marketing
  - Technical credibility
  - Competitive positioning
```

Or pass inline: `--target "Dir Product Marketing, Anthropic"`

### Step 4: Apply corrections

After reviewing a generated PDF, apply corrections without touching layout:

```txt
# corrections.txt
summary: Replace "data infrastructure" with "AI-native"
ververica.bullet.1: "Shortened replacement text"
ververica.bullet.add: "New bullet to append"
skills.remove: HubSpot
skills.add: "LLM Orchestration" to "Technology"
speaking.remove: Ops Cast
notable.add: "3x Board advisor for growth-stage companies"
experience.order: ververica, wartsila, aiven, sharper_shape
ventures.revhunt.hide: true
speaking.show_max: 4
education.mit.add_detail: "Capstone: Bayesian inference"
```

Apply: `python cv.py --corrections corrections.txt --preview`

## CLI Reference

```
python cv.py [OPTIONS]

Import:
  --import-pdf FILE    Import CV from PDF into master profile
  --import-text FILE   Import CV from text file into master profile

Generate:
  --target TEXT        Target role (saved brief name or "Role, Company")
  --jd FILE            Job description file to analyse
  --corrections FILE   Corrections file to apply
  --output FILE        Output PDF path (default: auto-named)
  --ai                 Use Claude API for intelligent tailoring
  --rewrite            Allow AI to rewrite bullets (with --ai)
  --preview            Open generated PDF immediately

Inspect:
  --list-targets       Show saved target briefs
  --show SECTION       Print current content (e.g., experience.ververica)
  --diff               Show changes from master profile

Interactive:
  --interactive        Launch interactive REPL
```

## Interactive Mode

```bash
python cv.py --interactive
```

| Command | Description |
|---|---|
| `show [section]` | Display current content |
| `edit summary: new text` | Edit a section |
| `target "Role, Company"` | Re-tailor for new target |
| `preview` | Generate and open PDF |
| `save filename.pdf` | Save PDF to output/ |
| `diff` | Show changes from master |
| `undo` | Undo last change |
| `corrections file.txt` | Apply corrections file |
| `quit` | Exit |

## AI Tailoring

Set `ANTHROPIC_API_KEY` in your environment, then:

```bash
# Select + reorder only (default — safe, preserves original text)
python cv.py --target "VP Growth, Stripe" --jd jd.txt --ai

# Allow bullet rewriting (more aggressive, review carefully)
python cv.py --target "VP Growth, Stripe" --jd jd.txt --ai --rewrite
```

The AI is instructed to ONLY use content from the master profile. It selects, reorders, and (with `--rewrite`) rephrases — but never invents. Output is written to `data/output/tailored_content.yaml` for review.

## Design: Ember

The layout engine ("Ember") renders warm, editorial-quality PDFs:

- **DM Serif Text** for name and section headers
- **Poppins** (5 weights) for body typography
- **Source Code Pro** for metadata
- Cream background, rust accents, generous whitespace
- A4, 2-page adaptive layout with automatic page breaks

## File Structure

```
cv-tailor/
├── cv.py                  # CLI entry + REPL
├── engine/
│   ├── fonts.py           # Font download/registration
│   ├── importer.py        # Source document import
│   ├── tailor.py          # Tailoring engine
│   ├── correct.py         # Corrections parser/applier
│   └── layout.py          # Ember PDF layout engine
├── data/
│   ├── master_profile.yaml
│   ├── targets/           # Saved target briefs
│   ├── corrections/       # Per-target corrections
│   └── output/            # Generated PDFs + YAML
├── fonts/                 # Auto-downloaded TTFs
└── requirements.txt
```
