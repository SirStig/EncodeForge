#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP="${1:-}"
IDENTITY="${2:-}"
ENTITLEMENTS="${3:-$SCRIPT_DIR/entitlements.plist}"

if [[ -z "$APP" || -z "$IDENTITY" ]]; then
  echo "Usage: $0 <path-to.app> <codesign-identity> [entitlements.plist]"
  exit 1
fi

if [[ ! -d "$APP" ]]; then
  echo "Not a directory: $APP"
  exit 1
fi

if ! security find-identity -v -p codesigning | grep -qF "$IDENTITY"; then
  echo "Identity not found: $IDENTITY"
  echo ""
  echo "Available code signing identities:"
  security find-identity -v -p codesigning
  exit 1
fi

main_exe="$APP/Contents/MacOS/EncodeForge"
if [[ ! -f "$main_exe" ]]; then
  main_exe=""
fi

depth_sort() {
  while IFS= read -r p; do
    echo "$(echo "$p" | tr -cd / | wc -c | tr -d ' ') $p"
  done | sort -rn | cut -d' ' -f2-
}

list_macho() {
  find "$APP" -type f -print0 | while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q Mach-O; then
      echo "$f"
    fi
  done
}

list_frameworks() {
  find "$APP" -type d -name "*.framework" | while IFS= read -r f; do
    echo "$f"
  done
}

echo "Signing nested binaries (deepest first)..."
list_macho | depth_sort | while IFS= read -r f; do
  if [[ "$f" == "$APP" ]]; then continue; fi
  if [[ -n "$main_exe" && "$f" == "$main_exe" ]]; then
    echo "  $f (with entitlements)"
    codesign --force --options runtime --timestamp -s "$IDENTITY" --entitlements "$ENTITLEMENTS" "$f"
  else
    echo "  $f"
    codesign --force --options runtime --timestamp -s "$IDENTITY" "$f"
  fi
done

echo "Signing .framework bundles (deepest first)..."
list_frameworks | depth_sort | while IFS= read -r fw; do
  echo "  $fw"
  codesign --force --options runtime --timestamp -s "$IDENTITY" "$fw"
done

echo "Signing app bundle..."
codesign --force --options runtime --timestamp -s "$IDENTITY" --entitlements "$ENTITLEMENTS" "$APP"

echo "Verifying..."
codesign -vv --deep --strict "$APP"
echo "Done."
