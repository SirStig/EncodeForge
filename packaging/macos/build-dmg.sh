#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Run on macOS after: python3 build_nuitka.py"
  exit 1
fi

APP="${ROOT}/dist/EncodeForge.app"
if [[ ! -d "${APP}" ]]; then
  echo "Missing ${APP}. Run: python3 build_nuitka.py"
  exit 1
fi

VERSION_PY="$(python3 -c "from app import __version__; print(__version__)")"
mkdir -p "${ROOT}/dist-packages"
DMG="${ROOT}/dist-packages/EncodeForge-${VERSION_PY}-macos.dmg"
rm -f "${DMG}"
hdiutil create -volname "EncodeForge ${VERSION_PY}" -srcfolder "${APP}" -ov -format UDZO "${DMG}"
echo "Wrote ${DMG}"
