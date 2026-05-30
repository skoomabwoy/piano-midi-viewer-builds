#!/bin/bash
# Deploy website to Codeberg Pages (pages branch)
# Usage: ./website/deploy.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEBSITE_DIR="$REPO_ROOT/website"
PAGES_BRANCH="pages"
TMPDIR="$(mktemp -d)"

cd "$REPO_ROOT"

CURRENT_BRANCH="$(git branch --show-current)"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Error: You have uncommitted changes. Commit or stash them first."
    rm -rf "$TMPDIR"
    exit 1
fi

# Stage files to temp dir BEFORE switching branches
echo "Staging files..."
cp "$WEBSITE_DIR/index.html" "$TMPDIR/"
cp "$WEBSITE_DIR/guide.html" "$TMPDIR/"
cp "$WEBSITE_DIR/style.css" "$TMPDIR/"
cp "$WEBSITE_DIR/script.js" "$TMPDIR/"

# Assets (font, icons) — now packaged under piano_viewer/resources/
cp "$REPO_ROOT/piano_viewer/resources/images/icon.png" "$TMPDIR/"
cp "$REPO_ROOT/piano_viewer/resources/images/icon.svg" "$TMPDIR/"
cp "$REPO_ROOT/piano_viewer/resources/fonts/JetBrainsMono-Regular.ttf" "$TMPDIR/"

# Screenshots used by the website (now under docs/screenshots/)
mkdir -p "$TMPDIR/screenshots"
cp "$REPO_ROOT/docs/screenshots/sustained-blue-2-octaves-velocity.png" "$TMPDIR/screenshots/"
cp "$REPO_ROOT/docs/screenshots/pencil-tool-red-4-octaves.png" "$TMPDIR/screenshots/"
# Guide screenshots (copied individually so missing files don't abort the deploy)
for f in guide-zoom guide-meet guide-discord guide-telegram \
          guide-obs-scene guide-obs-webcam guide-obs-capture guide-obs-layout \
          guide-obs-virtualcam guide-obs-incall; do
    [ -f "$REPO_ROOT/docs/screenshots/$f.png" ] && cp "$REPO_ROOT/docs/screenshots/$f.png" "$TMPDIR/screenshots/"
done

# Demo videos
if [ -d "$WEBSITE_DIR/media" ]; then
    mkdir -p "$TMPDIR/media"
    find "$WEBSITE_DIR/media" -maxdepth 1 -name "*.mp4" -exec cp {} "$TMPDIR/media/" \;
fi

# Flatten dev paths for production: resource images/fonts land at the site root,
# screenshots under screenshots/.
# Use portable sed (no -i flag) for macOS compatibility.
for f in index.html guide.html; do
    sed 's|\.\./piano_viewer/resources/images/||g; s|\.\./piano_viewer/resources/fonts/||g; s|\.\./docs/screenshots/|screenshots/|g' \
        "$TMPDIR/$f" > "$TMPDIR/$f.tmp" && mv "$TMPDIR/$f.tmp" "$TMPDIR/$f"
done
sed 's|\.\./piano_viewer/resources/fonts/||g; s|\.\./piano_viewer/resources/images/||g' \
    "$TMPDIR/style.css" > "$TMPDIR/style.css.tmp" && mv "$TMPDIR/style.css.tmp" "$TMPDIR/style.css"

# Single source of truth for the version: the app's VERSION in __init__.py.
# Inject it into the deployed script.js as FALLBACK_TAG, so the site never needs
# a manual version edit. (The live version is still fetched from the Codeberg API
# at runtime; this fallback only shows if that API call fails.)
APP_VERSION="$(sed -n 's/^VERSION = "\([^"]*\)".*/\1/p' "$REPO_ROOT/piano_viewer/__init__.py")"
if [ -n "$APP_VERSION" ]; then
    sed "s/const FALLBACK_TAG = '[^']*';/const FALLBACK_TAG = 'v${APP_VERSION}';/" \
        "$TMPDIR/script.js" > "$TMPDIR/script.js.tmp" && mv "$TMPDIR/script.js.tmp" "$TMPDIR/script.js"
    echo "Injected version v${APP_VERSION} into script.js"
else
    echo "Warning: could not read VERSION from __init__.py — keeping script.js fallback as-is"
fi

# Switch to pages branch
if ! git show-ref --verify --quiet "refs/heads/$PAGES_BRANCH"; then
    echo "Creating orphan '$PAGES_BRANCH' branch..."
    git checkout --orphan "$PAGES_BRANCH"
    git rm -rf . > /dev/null 2>&1 || true
    git clean -fd > /dev/null 2>&1
else
    git checkout "$PAGES_BRANCH"
    git rm -rf . > /dev/null 2>&1 || true
    git clean -fd > /dev/null 2>&1
fi

# Copy staged files into the clean branch
cp -r "$TMPDIR"/* .
rm -rf "$TMPDIR"

git add -A
git commit -m "Deploy website"
git push origin "$PAGES_BRANCH" --force

git checkout "$CURRENT_BRANCH"

echo ""
echo "Deployed! Site will be at:"
echo "  https://skoomabwoy.codeberg.page/piano-midi-viewer/"
