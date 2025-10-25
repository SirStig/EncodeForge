"""
Unified path management for EncodeForge application data.
All application data is stored in a single location:
- Windows: AppData/Local/EncodeForge/
- Unix/Linux: ~/.local/share/EncodeForge/
- macOS: ~/Library/Application Support/EncodeForge/
"""

import os
import platform
from pathlib import Path
from typing import Optional

APP_NAME = "EncodeForge"
_base_dir: Optional[Path] = None


def get_base_dir() -> Path:
    """Get the base application data directory"""
    global _base_dir
    if _base_dir is None:
        _base_dir = _determine_base_dir()
        # Ensure the directory exists
        _base_dir.mkdir(parents=True, exist_ok=True)
    return _base_dir


def get_settings_dir() -> Path:
    """Get the settings directory"""
    return _get_sub_dir("settings")


def get_logs_dir() -> Path:
    """Get the logs directory"""
    return _get_sub_dir("logs")


def get_cache_dir() -> Path:
    """Get the cache directory"""
    return _get_sub_dir("cache")


def get_temp_dir() -> Path:
    """Get the temp directory"""
    return _get_sub_dir("temp")


def get_backups_dir() -> Path:
    """Get the backups directory"""
    return _get_sub_dir("backups")


def get_profiles_dir() -> Path:
    """Get the profiles directory"""
    return _get_sub_dir("profiles")


def get_models_dir() -> Path:
    """Get the models directory"""
    return _get_sub_dir("models")


def get_settings_file() -> Path:
    """Get the settings file path"""
    return get_settings_dir() / "settings.json"


def get_conversion_state_file() -> Path:
    """Get the conversion state file path"""
    return get_temp_dir() / "conversion_state.json"


def _get_sub_dir(sub_dir_name: str) -> Path:
    """Get a subdirectory under the base directory"""
    sub_dir = get_base_dir() / sub_dir_name
    sub_dir.mkdir(parents=True, exist_ok=True)
    return sub_dir


def _determine_base_dir() -> Path:
    """Determine the base directory based on the operating system"""
    system = platform.system().lower()
    
    if system == "windows":
        # Windows: AppData/Local/EncodeForge/
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / APP_NAME
        else:
            # Fallback to user home
            return Path.home() / "AppData" / "Local" / APP_NAME
    elif system == "darwin":
        # macOS: ~/Library/Application Support/EncodeForge/
        return Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        # Linux/Unix: ~/.local/share/EncodeForge/
        return Path.home() / ".local" / "share" / APP_NAME


def get_base_dir_string() -> str:
    """Get the base directory as a string (for backward compatibility)"""
    return str(get_base_dir())


def get_settings_file_path() -> str:
    """Get the settings file path as a string (for backward compatibility)"""
    return str(get_settings_file())


def create_temp_file(prefix: str, suffix: str) -> Path:
    """Create a temporary file in the application's temp directory"""
    import tempfile
    temp_dir = get_temp_dir()
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=temp_dir)
    os.close(fd)  # Close the file descriptor, we only need the path
    return Path(path)


def create_temp_directory(prefix: str) -> Path:
    """Create a temporary directory in the application's temp directory"""
    import tempfile
    temp_dir = get_temp_dir()
    return Path(tempfile.mkdtemp(prefix=prefix, dir=temp_dir))
