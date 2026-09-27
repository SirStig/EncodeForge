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

ARCH="$(uname -m)"

# Nuitka's standalone mode never bundles glibc itself (doing so is broadly
# considered unsafe: NSS modules for DNS/user lookups have to match the host
# exactly), so the AppImage's minimum glibc requirement is whatever glibc
# happens to be installed on *this* build machine. The AppImage catalog's
# "not self-contained ... references glibc X.Y" check is really measuring
# that. Building on a fresh/rolling distro (Fedora, Arch, Ubuntu 24.04+,
# etc.) produces an AppImage that only runs on equally new systems. Build on
# the oldest still-supported base you want to support instead — e.g. Debian
# 11 "bullseye" (glibc 2.31) or a manylinux_2_28 container (glibc 2.28) — and
# re-run this script there.
GLIBC_VERSION="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}' || true)"
if [[ -n "${GLIBC_VERSION}" ]]; then
  echo "Building against glibc ${GLIBC_VERSION} on this machine — the AppImage will require at least this version to run."
  if [[ "$(printf '%s\n' "${GLIBC_VERSION}" "2.31" | sort -V | head -1)" != "${GLIBC_VERSION}" ]]; then
    echo "WARNING: glibc ${GLIBC_VERSION} is newer than Debian 11/Ubuntu 20.04 (2.31)." >&2
    echo "         The resulting AppImage will fail to start on older systems." >&2
    echo "         Build inside an older distro or container for a compatible release artifact." >&2
  fi
fi

# AppImage/AppImageKit (the old repo people usually find first) has been
# unmaintained since ~2020 and its appimagetool releases embed the old
# FUSE-dependent AppImage runtime, which is what the AppImage catalog's
# "uses an old AppImage runtime that needs ... libfuse2" check flags.
# AppImage/appimagetool is the maintained successor and embeds the current
# static runtime, which doesn't need libfuse2 on the target system. Pull a
# pinned build of that instead of trusting whatever "appimagetool" happens
# to be on PATH.
APPIMAGETOOL_VERSION="continuous"
APPIMAGETOOL="${ROOT}/dist/appimagetool-${ARCH}.AppImage"
if [[ ! -x "${APPIMAGETOOL}" ]]; then
  mkdir -p "${ROOT}/dist"
  URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage"
  echo "Fetching appimagetool (${APPIMAGETOOL_VERSION}) from ${URL}"
  curl -fL -o "${APPIMAGETOOL}" "${URL}"
  chmod +x "${APPIMAGETOOL}"
fi
# appimagetool is itself an AppImage; running it inside containers/CI
# without FUSE needs this instead of a real mount.
export APPIMAGE_EXTRACT_AND_RUN=1

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

OUT="${ROOT}/dist-packages/EncodeForge-${VERSION_PY}-${ARCH}.AppImage"
mkdir -p "${ROOT}/dist-packages"
rm -f "${OUT}"
ARCH="${ARCH}" "${APPIMAGETOOL}" "${APPDIR}" "${OUT}"
echo "Wrote ${OUT}"
