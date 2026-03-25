#!/usr/bin/env python3
"""
Nuitka Build Script for EncodeForge
Cross-platform compilation script
"""

import sys
import subprocess
import platform
from pathlib import Path

# Project configuration
PROJECT_NAME = "EncodeForge"
MAIN_SCRIPT = "main.py"
VERSION = "0.5.0"
ICON_PATH = "resources/icons/app-icon.png"

# Detect platform
SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MACOS = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"


def build():
    """Build the application with Nuitka"""
    print(f"Building {PROJECT_NAME} v{VERSION} for {SYSTEM}")
    
    # Base Nuitka command
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        f"--output-dir=dist",
        f"--output-filename={PROJECT_NAME}",
        "--assume-yes-for-downloads",
        "--show-progress",
        "--show-memory",
    ]
    
    # Add icon (platform-specific)
    icon_path = Path(ICON_PATH)
    if icon_path.exists():
        if IS_WINDOWS:
            cmd.append(f"--windows-icon-from-ico={icon_path}")
        elif IS_MACOS:
            cmd.append(f"--macos-app-icon={icon_path}")
        elif IS_LINUX:
            cmd.append(f"--linux-icon={icon_path}")
    
    # Windows-specific options
    if IS_WINDOWS:
        cmd.extend([
            "--windows-console-mode=disable",  # No console window
            "--windows-company-name=EncodeForge",
            f"--windows-product-name={PROJECT_NAME}",
            f"--windows-file-version={VERSION}",
            f"--windows-product-version={VERSION}",
        ])
    
    # macOS-specific options
    if IS_MACOS:
        cmd.extend([
            f"--macos-app-name={PROJECT_NAME}",
            "--macos-app-mode=gui",
            f"--macos-app-version={VERSION}",
            "--macos-create-app-bundle",
        ])
    
    # Linux-specific options
    if IS_LINUX:
        cmd.extend([
            "--linux-icon=resources/icons/app-icon.png",
        ])
    
    # Include data files
    cmd.extend([
        "--include-data-dir=resources=resources",
        "--include-package=core",
        "--include-package=app",
        "--include-package=utils",
    ])
    
    # Optimize
    cmd.extend([
        "--lto=yes",
        "--jobs=4",
    ])
    
    # Main script
    cmd.append(MAIN_SCRIPT)
    
    # Run build
    print(f"\nRunning command:\n{' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print(f"\n✓ Build successful! Output in dist/ directory")
        
        # Show output location
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
