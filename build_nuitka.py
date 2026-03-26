#!/usr/bin/env python3
"""
Nuitka Build Script for EncodeForge
Cross-platform compilation script
"""

import os
import re
import sys
import subprocess
import platform
from pathlib import Path

from app import __version__ as VERSION

PROJECT_NAME = "EncodeForge"
MAIN_SCRIPT = "main.py"
ICON_DIR = Path("resources/icons")
ICON_PNG = ICON_DIR / "app-icon.png"
ICON_ICO = ICON_DIR / "app-icon.ico"

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
    ]

    if os.environ.get("NUITKA_ONEFILE", "").lower() in ("1", "true", "yes"):
        cmd.append("--onefile")

    cmd.extend([
        "--enable-plugin=pyside6",
        "--output-dir=dist",
        f"--output-filename={PROJECT_NAME}",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
    ])

    if IS_WINDOWS:
        if ICON_ICO.exists():
            cmd.append(f"--windows-icon-from-ico={ICON_ICO}")
    elif IS_MACOS and ICON_PNG.exists():
        cmd.append(f"--macos-app-icon={ICON_PNG}")
    elif IS_LINUX and ICON_PNG.exists():
        cmd.append(f"--linux-icon={ICON_PNG}")

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

    cmd.extend([
        "--include-data-dir=resources=resources",
        "--include-package=core",
        "--include-package=app",
        "--include-package=utils",
    ])

    for mod in NOFOLLOW_IMPORT_TO:
        cmd.append(f"--nofollow-import-to={mod}")

    override = os.environ.get("NUITKA_LTO", "").lower()
    if override in ("1", "true", "yes"):
        lto = "yes"
    elif override in ("0", "false", "no"):
        lto = "no"
    else:
        ci = os.environ.get("CI", "").lower() in ("1", "true", "yes")
        lto = "no" if ci else "yes"

    cmd.extend([
        f"--lto={lto}",
        "--jobs=4",
    ])

    cmd.append(MAIN_SCRIPT)

    print(f"\nRunning command:\n{' '.join(cmd)}\n")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    result = subprocess.run(cmd, env=env)

    if result.returncode == 0:
        print("\nBuild successful. Output in dist/ directory")

        if IS_MACOS:
            print(f"macOS App Bundle: dist/{PROJECT_NAME}.app")
        elif IS_WINDOWS:
            print(f"Windows Executable: dist/{PROJECT_NAME}.exe")
        else:
            print(f"Linux Binary: dist/{PROJECT_NAME}")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build()
