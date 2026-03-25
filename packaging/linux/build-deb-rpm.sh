#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Run this script on Linux after: python3 build_nuitka.py"
  exit 1
fi

if ! command -v fpm >/dev/null 2>&1; then
  echo "fpm not found. Install: gem install fpm"
  echo "Also need: sudo apt install ruby ruby-dev build-essential  (Debian/Ubuntu)"
  exit 1
fi

DIST="$(find dist -maxdepth 1 -name '*.dist' -type d | head -1 || true)"
if [[ -z "${DIST}" || ! -d "${DIST}" ]]; then
  echo "No Nuitka *.dist under dist/. Run: python3 build_nuitka.py"
  exit 1
fi

VERSION_PY="$(python3 -c "from app import __version__; print(__version__)")"
DEB_VER="$(VERSION_PY="${VERSION_PY}" python3 -c "import os,re; v=os.environ['VERSION_PY']; v=re.sub(r'-alpha-(\d+)', r'~alpha\1', v); v=re.sub(r'-beta-(\d+)', r'~beta\1', v); print(v)")"
RPM_VER="$(VERSION_PY="${VERSION_PY}" python3 -c "import os,re; v=os.environ['VERSION_PY']; v=re.sub(r'-alpha-(\d+)', r'.alpha\1', v); v=re.sub(r'-beta-(\d+)', r'.beta\1', v); v=v.replace('-', '_'); print(v)")"

mkdir -p dist-packages
STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT

mkdir -p "${STAGE}/opt/EncodeForge"
cp -a "${DIST}/." "${STAGE}/opt/EncodeForge/"
mkdir -p "${STAGE}/usr/share/applications" "${STAGE}/usr/share/pixmaps"
cp "${ROOT}/packaging/linux/encodeforge.desktop" "${STAGE}/usr/share/applications/encodeforge.desktop"
cp "${ROOT}/resources/icons/app-icon.png" "${STAGE}/usr/share/pixmaps/encodeforge.png"

ARCH="$(uname -m)"
FPM_ARCH="${ARCH}"
[[ "${ARCH}" == "x86_64" ]] && FPM_ARCH="amd64"
[[ "${ARCH}" == "aarch64" ]] && FPM_ARCH="arm64"

COMMON=(
  -s dir
  -n encodeforge
  --license MIT
  --maintainer "EncodeForge <https://github.com/SirStig/EncodeForge>"
  --url "https://github.com/SirStig/EncodeForge"
  --description "Desktop video encoding, subtitles, and media tools (PySide6)."
  -C "${STAGE}"
  opt
  usr
)

fpm "${COMMON[@]}" -t deb -v "${DEB_VER}" -a "${FPM_ARCH}" \
  -p "${ROOT}/dist-packages/encodeforge_${DEB_VER}-1_${FPM_ARCH}.deb"

fpm "${COMMON[@]}" -t rpm -v "${RPM_VER}" -a native \
  -p "${ROOT}/dist-packages/encodeforge-${RPM_VER}-1.${ARCH}.rpm"

echo "Wrote packages under dist-packages/"
