#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DEST="$HOME/Library/LaunchAgents/com.mcg.mtg-app.stage2.plist"

cp "$REPO_ROOT/scripts/com.mcg.mtg-app.stage2.plist" "$PLIST_DEST"
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"
echo "Installed. Status:"
launchctl list | grep com.mcg.mtg-app.stage2 || echo "(not showing yet — check again in a moment)"
