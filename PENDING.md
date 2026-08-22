# PENDING — open items for CV Tailor

Last updated: 2026-08-23
Branch: `feat/aggressive-tailoring-and-cover-letters` (6 commits ahead of `main`, unmerged)
Tests: 149 passing (`test_app.py`, `test_launcher.py`)

Everything below is either not built, not verified, or a decision waiting on Jaime.
Shipped work is in the git log, not here.

---

## 1. Designed and approved, NOT BUILT

### Reorder Experience entries (companies) in the Edit tab

The one feature that was agreed and never implemented.

**Problem:** bullets have ↑/↓ reorder buttons (`moveBullet`, `static/app.js:432`).
Experience entries — the companies — have none, so the order they were imported
in is the order you are stuck with.

**Design as agreed:**

- `moveExperience(i, dir)` in `static/app.js`, mirroring `moveBullet` exactly:
  swap adjacent entries in `state.profile.experience`, `markDirty()`,
  `renderContent()`, then scroll the moved card into view with a brief highlight.
- ↑/↓ buttons in the entry header next to the collapse chevron, reusing the
  existing `.btn-move` styling. Disabled at the ends of the list.
- The header row already carries `onclick="toggleEntry(...)"`, so the move
  buttons need `event.stopPropagation()` or clicking ↑ also collapses the card.
- No backend change. `experience` is an ordered list in the YAML, so the new
  order saves and renders as-is.

**Testing:** Playwright against the running app — reorder two companies, assert
`state.profile.experience` order changed, that it survives a save/reload
round-trip through `/api/profile`, and that clicking ↑ does not collapse the
card. There is no JS test framework in this repo, so that is where the only
real coverage would live.

**Note:** this sets the order in the *master* profile. The Tailor step still
reorders experience by relevance per job, so a manual order is the starting
point, not the last word.

---

## 2. Blocked on the Anthropic account

### The cheap-model path has never actually run

`engine/tailor.py` defaults to `claude-haiku-4-5`, but **no live Haiku request
has ever succeeded.** The account has been returning:

```
You have reached your specified API usage limits.
You will regain access on 2026-09-01 at 00:00 UTC.
```

Every Anthropic call 400s regardless of model. What is verified is only that
`_reasoning_kwargs("claude-haiku-4-5")` returns `{}` — the unit test — not that
a real Haiku tailor produces good output.

**After 2026-09-01, do this:**

1. Run a tailor with provider pinned to `anthropic` and confirm no errors.
2. Judge the output quality against the OpenAI path. Haiku is 5× cheaper than
   Opus but this is a rewriting task; if quality drops, set
   `CV_TAILOR_MODEL=claude-opus-5` (or Sonnet) and accept the cost.
3. Re-test instruction obedience — see item 3.

**Until then:** leave the provider on **Auto** or **OpenAI** in the Tailor form.
Pinning Anthropic silently drops to the keyword-only fallback: no AI tailoring,
empty diff, and the reason appears in the warnings rather than as an error.

---

## 3. Known-unreliable behaviour, needs re-testing

### Instructions reach the model but are not always obeyed

The interactive instruction box is wired correctly and unit-tested: instructions
land in the prompt above the fit recommendations and below the no-fabrication
rule. But in live testing, gpt-4o-mini was given:

> "Cut every bullet that is not about revenue or technical work"

and the bullet count went **up**, from 9 to 10.

The plumbing is proven; obedience is a model-capability question. Re-test this
on Haiku (item 2) before concluding the feature works. If a cheap model cannot
follow instructions reliably, that is an argument for spending more on this
specific call than on the initial tailor.

### One unexplained slow run

A re-tailor through OpenAI once took **4m15s** where the initial tailor took 26s.
Looked like a slow API response rather than our code, and it did not recur. If
it repeats, worth investigating before assuming it is upstream.

---

## 4. Real problem, deliberately not fixed

### The test suite bills the account and can hang

`/api/tailor` calls `_analyze_fit()` **unconditionally** — it ignores `use_ai`.
So every test that posts `use_ai: false` still makes a live Anthropic API call.
This predates all recent work (it is in `349e6c2`).

Symptoms seen: the suite blocked indefinitely on an open TCP connection to
Anthropic at 0% CPU. It only became visible when the API started hanging
instead of fast-failing on the usage limit; the SDK's retry backoff turned that
into an indefinite stall. Two pytest processes were left hanging for over an
hour.

**Workaround in use** — run the suite hermetically, 149 tests in ~20s:

```bash
ANTHROPIC_API_KEY=dummy OPENAI_API_KEY=dummy python -m pytest test_app.py test_launcher.py -q
```

**The actual fix** is to make `_analyze_fit` respect `use_ai` (`app.py:220`).
Left undone because it is a behaviour change to the tailoring flow, not just a
test fix: turning off AI tailoring would then also turn off AI fit analysis.
That is arguably what the "Use AI tailoring" toggle already promises, but it is
Jaime's call. Needs a test either way.

---

## 5. Unverified — needs a human to look

### Does ⌘Space find the app?

Never confirmed. `scripts/install_app.sh` now copies the bundle into
`/Applications` rather than symlinking it (Spotlight does not index symlinked
app bundles, which is why the first attempt failed). But **Spotlight queries
are blocked from the agent sandbox** — `mdfind` and `mdls` return nothing even
for Google Chrome — so the indexing side is genuinely unverified.

If ⌘Space still comes up empty, the next suspect is a stale Spotlight index,
which needs a command that cannot be run unattended:

```bash
sudo mdutil -E /
```

Fallback that does not depend on Spotlight at all: drag `/Applications/CV
Tailor.app` onto the Dock.

### The app window has never been seen

The Chrome app-mode window was verified by process table and HTTP 200, never
visually — `screencapture` needs screen-recording permission the terminal does
not have. Worth one look that the chrome-less window actually renders correctly
(no tab strip, no address bar, correct size).

### The keyboard shortcut is not set up

GUI-only, no scriptable path. To do it:

Shortcuts.app → **+** → search *Open App* → drag it in → pick **CV Tailor** →
in the ⓘ sidebar tick **Use as Quick Action** → **Add Keyboard Shortcut**.

---

## 6. Decisions waiting on Jaime

### Which flagged LLM-isms should become automatic rewrites?

Currently **stripped outright**: em dashes, en dashes, curly quotes and
apostrophes, ellipsis characters, non-breaking spaces.

Currently **rewritten** (unambiguous, case-preserving): delve into → examine,
leverage → use, utilize → use, in order to → to, a testament to → evidence of.

Currently **flagged only** — surfaced in the warnings panel, never changed,
because a real CV legitimately uses them:

> robust · seamless · pivotal · cutting-edge · showcase · underscore · elevate ·
> spearheaded · streamlined · empower · tapestry · realm · myriad · fast-paced ·
> "not just X, but Y"

Any of these can be promoted from flag to rewrite. Say which. The lists are
`_REWRITES` and `FLAG_ONLY` in `engine/sanitize.py`.

### Should the cover letter move to a cheap model too?

`engine/cover_letter.py` still uses `claude-opus-5`. Left alone deliberately —
it is one call per letter, unlike tailoring which is an iterative loop. Cheap to
change if the cost matters.

---

## 7. Latent, worth knowing

### The venv is arm64-only on a universal2 interpreter

`/Library/Frameworks/Python.framework` is a universal2 binary (x86_64 + arm64),
but the installed wheels are arm64-only. A universal binary inherits its
**parent process's** architecture, so anything that launches Python from a
translated (Rosetta) parent gets an `ImportError: incompatible architecture`.

This already caused the `.app` to fail on launch and is now defended twice —
`LSRequiresNativeExecution` in `Info.plist`, and an `arch -arm64` re-exec in
`scripts/cvtailor`. But the underlying mismatch is still there and will bite
anywhere else that starts Python from a translated parent.

### Re-tailoring resets accept/reject toggles

By design, not a bug. Each re-tailor returns a fresh result from the master
profile, so per-diff accept/reject selections reset. Settle the instructions
first, then do accept/reject.

### The server does not hot-reload

`scripts/cvtailor` runs uvicorn **without** `--reload` on purpose: the reloader
forks a child that survives killing the parent and leaves the port occupied
after every quit. Consequence — **after changing Python code, quit and relaunch
the app**, or you are testing stale code. This has already caused one false
"verified" result.

### The branch is unmerged

Six commits ahead of `main`, no PR. Nothing here has been merged or pushed.
