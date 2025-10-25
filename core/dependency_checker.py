#!/usr/bin/env python3
"""
Dependency Checker - Utility for checking and installing Python packages
Called by Java DependencyManager to manage Python dependencies
"""

import importlib
import json
import subprocess
import sys
from typing import Dict, List, Tuple


def check_package(package_name: str) -> bool:
    """Check if a package is importable"""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False


def check_required_packages() -> Dict[str, bool]:
    """Check all required packages"""
    return {
        "beautifulsoup4": check_package("bs4"),  # bs4 is the import name
        "lxml": check_package("lxml")
    }


def check_optional_packages() -> Dict[str, bool]:
    """Check all optional AI packages"""
    return {
        "whisper": check_package("whisper"),
        "torch": check_package("torch"),
        "numba": check_package("numba")
    }


def install_package(package_spec: str, target_dir: str = None) -> Tuple[bool, str]:
    """
    Install a package via pip
    
    Args:
        package_spec: Package specification (e.g., "requests>=2.31.0")
        target_dir: Target directory for installation (optional)
    
    Returns:
        Tuple of (success: bool, output: str)
    """
    cmd = [sys.executable, "-m", "pip", "install", package_spec]
    
    if target_dir:
        cmd.extend(["--target", target_dir])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        success = result.returncode == 0
        output = result.stdout + "\n" + result.stderr
        
        return (success, output)
        
    except subprocess.TimeoutExpired:
        return (False, "Installation timed out after 5 minutes")
    except Exception as e:
        return (False, f"Installation failed: {str(e)}")


def install_packages_from_file(requirements_file: str, target_dir: str = None) -> Tuple[bool, str]:
    """
    Install packages from a requirements file
    
    Args:
        requirements_file: Path to requirements.txt file
        target_dir: Target directory for installation (optional)
    
    Returns:
        Tuple of (success: bool, output: str)
    """
    cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
    
    if target_dir:
        cmd.extend(["--target", target_dir])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for bulk installs
        )
        
        success = result.returncode == 0
        output = result.stdout + "\n" + result.stderr
        
        return (success, output)
        
    except subprocess.TimeoutExpired:
        return (False, "Installation timed out after 10 minutes")
    except Exception as e:
        return (False, f"Installation failed: {str(e)}")


def main():
    """CLI interface for dependency checking"""
    if len(sys.argv) < 2:
        print("Usage: dependency_checker.py [check-required|check-optional|install <package>]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check-required":
        result = check_required_packages()
        print(json.dumps(result, indent=2))
    
    elif command == "check-optional":
        result = check_optional_packages()
        print(json.dumps(result, indent=2))
    
    elif command == "install" and len(sys.argv) >= 3:
        package_spec = sys.argv[2]
        target_dir = sys.argv[3] if len(sys.argv) >= 4 else None
        
        success, output = install_package(package_spec, target_dir)
        
        result = {
            "success": success,
            "output": output
        }
        print(json.dumps(result, indent=2))
        
        sys.exit(0 if success else 1)
    
    else:
        print("Invalid command")
        sys.exit(1)


if __name__ == "__main__":
    main()

