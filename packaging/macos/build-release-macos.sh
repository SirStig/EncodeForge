#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

APP_BUNDLE="EncodeForge.app"
DIST="$ROOT/dist"
DIST_PKG="$ROOT/dist-packages"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IDENTITY="${CODESIGN_IDENTITY:-Developer ID Application: Project Yoked LLC (2XK2CQX4AS)}"
NOTARY_PROFILE="${NOTARY_PROFILE:-AC_PASSWORD}"

echo "Installing build dependencies..."
python3 -m pip install -q -r requirements.txt
python3 -m pip install -q nuitka ordered-set zstandard imageio

echo "Building with Nuitka..."
python3 build_nuitka.py

APP_PATH="$DIST/$APP_BUNDLE"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Missing $APP_PATH after build."
  exit 1
fi

echo "Signing..."
bash "$SCRIPT_DIR/sign-macos-app.sh" "$APP_PATH" "$IDENTITY"

ZIP_PATH="$ROOT/.encodeforge-notarize.zip"
rm -f "$ZIP_PATH"

if command -v xcrun >/dev/null 2>&1 && xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" &>/dev/null; then
  echo "Notarizing..."
  ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
  NOTARY_OUT=$(xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$NOTARY_PROFILE" --wait 2>&1) || true
  echo "$NOTARY_OUT"
  SUBMISSION_ID=$(echo "$NOTARY_OUT" | sed -n 's/^  id: //p' | head -1)
  if echo "$NOTARY_OUT" | grep -q "status: Invalid"; then
    echo ""
    echo "Notarization rejected. Apple's log:"
    xcrun notarytool log "$SUBMISSION_ID" --keychain-profile "$NOTARY_PROFILE" 2>&1 || true
    rm -f "$ZIP_PATH"
    exit 1
  fi
  if echo "$NOTARY_OUT" | grep -q "status: Accepted"; then
    xcrun stapler staple "$APP_PATH"
    echo "Notarization complete."
  fi
  rm -f "$ZIP_PATH"
else
  echo "Skipping notarization (configure 'notarytool store-credentials $NOTARY_PROFILE' with your Apple ID to enable)."
fi

VERSION_PY="$(python3 -c "from app import __version__; print(__version__)")"
mkdir -p "$DIST_PKG"
DMG="$DIST_PKG/EncodeForge-${VERSION_PY}-macos.dmg"
rm -f "$DMG"

echo "Creating DMG..."
hdiutil create -volname "EncodeForge ${VERSION_PY}" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG"

echo "Done. Output: $APP_PATH and $DMG"
