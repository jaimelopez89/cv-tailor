#!/bin/bash
# Install CV Tailor.app so Spotlight can find it.
#
# Spotlight does not index symlinked application bundles, so this copies the app
# and bakes the project path into the copy's stub. Pass a destination to install
# somewhere other than /Applications (the tests do this).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-/Applications}"
SRC="${PROJECT_DIR}/CV Tailor.app"
TARGET="${DEST}/CV Tailor.app"

[ -d "$SRC" ] || { echo "No bundle at $SRC" >&2; exit 1; }
mkdir -p "$DEST"

# Replaces an older install, including the symlink earlier versions created.
rm -rf "$TARGET"
cp -R "$SRC" "$TARGET"

STUB="${TARGET}/Contents/MacOS/CV Tailor"
python3 - "$STUB" "$PROJECT_DIR" <<'PY'
import sys
stub, project = sys.argv[1], sys.argv[2]
with open(stub) as f:
    body = f.read()
with open(stub, "w") as f:
    f.write(body.replace("__CVTAILOR_PROJECT_DIR__", project))
PY
chmod +x "$STUB"

# Nudge LaunchServices and Spotlight so the app shows up without a logout.
touch "$TARGET"
LSREG="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREG" ] && "$LSREG" -f "$TARGET" >/dev/null 2>&1 || true
command -v mdimport >/dev/null 2>&1 && mdimport "$TARGET" >/dev/null 2>&1 || true

echo "Installed $TARGET"
echo "Project:  $PROJECT_DIR"
