#!/usr/bin/env python3
"""
Nuitka Build Script for EncodeForge
Cross-platform compilation script
"""

import re
import sys
import subprocess
import platform
from pathlib import Path

from app import __version__ as VERSION

PROJECT_NAME = "EncodeForge"
MAIN_SCRIPT = "main.py"
ICON_PATH = "resources/icons/app-icon.png"

# Do not follow legacy / unused ML stacks (faster-whisper uses CTranslate2, not PyTorch).
NOFOLLOW_IMPORT_TO = (
    "torch",
    "torchvision",
    "torchaudio",
    "transformers",
    "tensorflow",
    "tensorboard",
)


def _windows_pe_version(app_ver: str) -> str:
    """Win32 VERSIONINFO requires a numeric a.b.c.d quad."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", app_ver)
    if not m:
        return "0.0.0.1"
    a, b, c = m.group(1), m.group(2), m.group(3)
    alpha = re.search(r"-alpha-(\d+)", app_ver)
    if alpha:
        return f"{a}.{b}.{c}.{alpha.group(1)}"
    return f"{a}.{b}.{c}.0"


SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MACOS = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"


def build():
    """Build the application with Nuitka"""
    print(f"Building {PROJECT_NAME} v{VERSION} for {SYSTEM}")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--output-dir=dist",
        f"--output-filename={PROJECT_NAME}",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
    ]

    icon_path = Path(ICON_PATH)
    if icon_path.exists():
        if IS_WINDOWS:
            cmd.append(f"--windows-icon-from-ico={icon_path}")
        elif IS_MACOS:
            cmd.append(f"--macos-app-icon={icon_path}")
        elif IS_LINUX:
            cmd.append(f"--linux-icon={icon_path}")

    if IS_WINDOWS:
        wver = _windows_pe_version(VERSION)
        cmd.extend([
            "--windows-console-mode=disable",
            "--windows-company-name=EncodeForge",
            f"--windows-product-name={PROJECT_NAME}",
            f"--windows-file-version={wver}",
            f"--windows-product-version={wver}",
        ])

    if IS_MACOS:
        cmd.extend([
            f"--macos-app-name={PROJECT_NAME}",
            "--macos-app-mode=gui",
            f"--macos-app-version={VERSION}",
            "--macos-create-app-bundle",
        ])

    if IS_LINUX:
        cmd.extend([
            "--linux-icon=resources/icons/app-icon.png",
        ])

    cmd.extend([
        "--include-data-dir=resources=resources",
        "--include-package=core",
        "--include-package=app",
        "--include-package=utils",
    ])

    for mod in NOFOLLOW_IMPORT_TO:
        cmd.append(f"--nofollow-import-to={mod}")

    cmd.extend([
        "--lto=yes",
        "--jobs=4",
    ])

    cmd.append(MAIN_SCRIPT)

    print(f"\nRunning command:\n{' '.join(cmd)}\n")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n✓ Build successful! Output in dist/ directory")

        if IS_MACOS:
            print(f"macOS App Bundle: dist/{PROJECT_NAME}.app")
        elif IS_WINDOWS:
            print(f"Windows Executable: dist/{PROJECT_NAME}.exe")
        else:
            print(f"Linux Binary: dist/{PROJECT_NAME}")
    else:
        print(f"\n✗ Build failed with code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()
