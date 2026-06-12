#!/bin/bash
set -e

# Always run from the repo root (this script lives in packaging/)
cd "$(dirname "$0")/.."

OUTPUT_NAME="${1:-IsotopeTrack_M.dmg}"

create-dmg \
  --volname "IsotopeTrack" \
  --volicon "images/isotrack_icon.icns" \
  --window-pos 200 120 \
  --window-size 660 400 \
  --icon-size 110 \
  --icon "IsotopeTrack.app" 203 185 \
  --hide-extension "IsotopeTrack.app" \
  --app-drop-link 485 185 \
  --background "images/dmg_background.png" \
  "$OUTPUT_NAME" \
  "dist/"