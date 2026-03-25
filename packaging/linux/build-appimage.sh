#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Run this script on Linux after: python3 build_nuitka.py"
  exit 1
fi

DIST="$(find dist -maxdepth 1 -name '*.dist' -type d | head -1 || true)"
if [[ -z "${DIST}" || ! -d "${DIST}" ]]; then
  echo "No Nuitka *.dist under dist/. Run: python3 build_nuitka.py"
  exit 1
fi

if ! command -v appimagetool >/dev/null 2>&1; then
  echo "appimagetool not in PATH."
  echo "Download from: https://github.com/AppImage/AppImageKit/releases"
  exit 1
fi

VERSION_PY="$(python3 -c "from app import __version__; print(__version__)")"
APPDIR="${ROOT}/dist/EncodeForge.AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}"
cp -a "${DIST}/." "${APPDIR}/"
cp "${ROOT}/packaging/linux/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun" "${APPDIR}/EncodeForge" 2>/dev/null || chmod +x "${APPDIR}/AppRun"

cp "${ROOT}/resources/icons/app-icon.png" "${APPDIR}/encodeforge.png"
ln -sf encodeforge.png "${APPDIR}/.DirIcon"

cat > "${APPDIR}/encodeforge.desktop" <<EOF
[Desktop Entry]
Name=EncodeForge
GenericName=Video encoder
Comment=Video encoding, subtitles, and media renaming
Exec=EncodeForge %F
Icon=encodeforge
Terminal=false
Type=Application
Categories=AudioVideo;Video;AudioVideoEditing;
EOF

export ARCH="$(uname -m)"
OUT="${ROOT}/dist-packages/EncodeForge-${VERSION_PY}-${ARCH}.AppImage"
mkdir -p "${ROOT}/dist-packages"
rm -f "${OUT}"
ARCH="${ARCH}" appimagetool "${APPDIR}" "${OUT}"
echo "Wrote ${OUT}"
