"""
EncodeForge Settings Manager
Persistent application settings with validation and defaults
"""

import json
import logging
import os
import threading
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional

from core import path_manager
from core.handlers.models import ConversionSettings

logger = logging.getLogger(__name__)


def _app_version() -> str:
    """
    Stamp saved settings with the running application version.

    Read lazily so a hardcoded copy cannot drift out of sync with
    app/__init__.py during a release bump.
    """
    try:
        from app import __version__
        return __version__
    except Exception:
        return "unknown"


def _from_dict(cls, data: Any, section_name: str):
    """
    Build a settings dataclass from stored JSON, ignoring unknown keys.

    Settings files outlive the code that wrote them. Passing the stored dict
    straight into the constructor makes any removed or renamed field raise
    TypeError, so filtering to the fields the class actually declares is what
    keeps an older file loadable.
    """
    if not isinstance(data, dict):
        logger.warning(f"Settings section '{section_name}' is not an object; using defaults")
        return cls()

    valid = {f.name for f in fields(cls)}
    unknown = set(data) - valid
    if unknown:
        logger.info(
            f"Ignoring {len(unknown)} unrecognised key(s) in settings section "
            f"'{section_name}': {', '.join(sorted(unknown))}"
        )

    kwargs = {k: v for k, v in data.items() if k in valid}
    try:
        return cls(**kwargs)
    except Exception as e:
        logger.error(f"Could not load settings section '{section_name}': {e}")
        return cls()


def _conversion_from_dict(data: Dict[str, Any]) -> ConversionSettings:
    return _from_dict(ConversionSettings, data, 'conversion')


@dataclass
class EncoderSettings:
    """Encoder default settings."""
    codec: str = "H.264"
    preset: str = "medium"
    crf: int = 23
    audio_codec: str = "AAC"
    audio_bitrate: int = 192
    hw_accel: str = "None"
    container: str = "MP4"
    two_pass: bool = False
    preserve_metadata: bool = True


@dataclass
class SubtitleSettings:
    """Subtitle default settings."""
    mode: str = "download"  # download or whisper
    language: str = "English"
    fallback: bool = True
    providers: list = field(default_factory=lambda: ["OpenSubtitles", "Addic7ed", "SubDL"])
    whisper_model: str = "medium"
    whisper_device: str = "Auto"
    translate: bool = False
    subtitle_format: str = "SRT"
    encoding: str = "UTF-8"
    sync: bool = True


@dataclass
class RenamerSettings:
    """Renamer default settings."""
    media_type: str = "TV Show"
    provider: str = "auto"
    pattern: str = "{title} - S{season:02d}E{episode:02d} - {episode_title}"
    replace_spaces: bool = False
    lowercase: bool = False
    remove_special: bool = False
    preserve_extension: bool = True
    destination_root: str = ""  # empty = rename in place, same folder
    action: str = "rename"  # rename, move, copy, hardlink, symlink
    include_sidecars: bool = True  # carry .srt/.ass/.nfo along with the video


@dataclass
class UISettings:
    """UI preferences."""
    theme: str = "dark"
    window_width: int = 1400
    window_height: int = 900
    window_maximized: bool = False
    active_tab: int = 0
    show_toolbar: bool = True
    show_statusbar: bool = True


@dataclass
class ApplicationSettings:
    """Application-wide settings."""
    check_updates: bool = True
    auto_download_updates: bool = False
    update_last_check_ts: float = 0.0
    update_skipped_version: str = ""
    clear_temp_on_exit: bool = True
    log_level: str = "INFO"
    max_threads: int = 4
    recent_files_limit: int = 10
    language: str = "en"
    ffmpeg_path: str = ""
    ffprobe_path: str = ""


class SettingsManager:
    """
    Manages application settings with persistence.
    
    Handles loading, saving, validation, and defaults for all settings.
    """
    
    _instance: Optional['SettingsManager'] = None
    _lock = threading.RLock()

    def __new__(cls):
        """Singleton pattern."""
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
        return cls._instance

    def __init__(self):
        """Initialize settings manager."""
        # Worker threads construct SettingsManager() concurrently with startup.
        # The whole body must be serialised, and _initialized must only be set
        # once the attributes exist — otherwise a second thread returns early
        # from __init__ and reads an object that has no `application` yet.
        with self._lock:
            if self._initialized:
                return

            self.settings_file = path_manager.get_settings_file()

            # Initialize settings with defaults
            self.encoder = EncoderSettings()
            self.subtitle = SubtitleSettings()
            self.renamer = RenamerSettings()
            self.ui = UISettings()
            self.application = ApplicationSettings()
            self.conversion = ConversionSettings()

            # Load settings from disk
            self.load()

            self._initialized = True
            logger.info("Settings manager initialized")

    def get_merged_conversion_settings(self) -> ConversionSettings:
        c = deepcopy(self.conversion)
        ff = (self.application.ffmpeg_path or "").strip()
        if ff:
            c.ffmpeg_path = ff
        fp = (self.application.ffprobe_path or "").strip()
        if fp:
            c.ffprobe_path = fp

        # The Renamer tab's settings live in their own section (`renamer`),
        # separate from the `conversion` section RenamingHandler actually
        # reads. Without this, a pattern/destination saved in the Renamer
        # tab was silently ignored by the CLI and by RenamerWorker's
        # non-preview (real rename) path, which fell back to the
        # ConversionSettings dataclass defaults instead.
        pat = (self.renamer.pattern or "").strip()
        if pat:
            c.renaming_pattern_tv = pat
            c.renaming_pattern_movie = pat
        c.renaming_destination_root = self.renamer.destination_root or ""
        c.renaming_action = self.renamer.action or "rename"
        c.renaming_include_sidecars = self.renamer.include_sidecars
        return c
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert all settings to dictionary."""
        return {
            'encoder': asdict(self.encoder),
            'subtitle': asdict(self.subtitle),
            'renamer': asdict(self.renamer),
            'ui': asdict(self.ui),
            'application': asdict(self.application),
            'conversion': asdict(self.conversion),
            'version': _app_version(),
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """
        Load settings from a dictionary.

        Each section is loaded independently so that a problem in one cannot
        discard the others — previously a single bad key in 'encoder' meant
        'conversion' (which holds every API key) was never reached at all.
        """
        if not isinstance(data, dict):
            logger.error("Settings file does not contain an object; using defaults")
            return

        sections = (
            ('encoder', EncoderSettings),
            ('subtitle', SubtitleSettings),
            ('renamer', RenamerSettings),
            ('ui', UISettings),
            ('application', ApplicationSettings),
            ('conversion', ConversionSettings),
        )

        for name, cls in sections:
            if name in data:
                setattr(self, name, _from_dict(cls, data[name], name))
    
    def load(self) -> bool:
        """
        Load settings from file.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.settings_file.exists():
            logger.info("No settings file found, using defaults")
            self.save()  # Create default settings file
            return False
        
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.from_dict(data)
            logger.info(f"Loaded settings from {self.settings_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            logger.info("Using default settings")
            return False
    
    def save(self) -> bool:
        """
        Save settings to file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to a sibling temp file and swap it in atomically. Writing in
            # place means a crash or a full disk mid-write leaves truncated JSON
            # that fails to parse on the next launch, taking every API key and
            # preference with it.
            tmp_path = self.settings_file.with_name(self.settings_file.name + '.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.settings_file)
            self._restrict_permissions(self.settings_file)

            logger.debug(f"Saved settings to {self.settings_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except (OSError, UnboundLocalError, NameError):
                pass
            return False

    @staticmethod
    def _restrict_permissions(path: Path) -> None:
        """
        Make the settings file owner-only.

        It stores API keys in plaintext, and the default umask leaves it
        world-readable on Linux and macOS.
        """
        if os.name == 'nt':
            return
        try:
            os.chmod(path, 0o600)
        except OSError as e:
            logger.debug(f"Could not restrict permissions on {path}: {e}")
    
    def reset(self):
        """Reset all settings to defaults."""
        self.encoder = EncoderSettings()
        self.subtitle = SubtitleSettings()
        self.renamer = RenamerSettings()
        self.ui = UISettings()
        self.application = ApplicationSettings()
        self.conversion = ConversionSettings()
        
        self.save()
        logger.info("Reset all settings to defaults")
    
    def reset_section(self, section: str):
        """
        Reset specific settings section to defaults.
        
        Args:
            section: Section name (encoder, subtitle, renamer, ui, application, conversion)
        """
        if section == 'encoder':
            self.encoder = EncoderSettings()
        elif section == 'subtitle':
            self.subtitle = SubtitleSettings()
        elif section == 'renamer':
            self.renamer = RenamerSettings()
        elif section == 'ui':
            self.ui = UISettings()
        elif section == 'application':
            self.application = ApplicationSettings()
        elif section == 'conversion':
            self.conversion = ConversionSettings()
        
        self.save()
        logger.info(f"Reset {section} settings to defaults")
    
    def export_settings(self, file_path: Path, include_secrets: bool = False) -> bool:
        """
        Export settings to file.

        Args:
            file_path: Path to export file
            include_secrets: Include API keys in the export. Off by default —
                exports are commonly shared in bug reports and forum posts.

        Returns:
            True if exported successfully
        """
        try:
            data = self.to_dict()

            if not include_secrets:
                conversion = data.get('conversion', {})
                redacted = [k for k in conversion if k.endswith('_api_key') and conversion[k]]
                for key in redacted:
                    conversion[key] = ''
                if redacted:
                    logger.info(
                        f"Excluded {len(redacted)} API key(s) from export. "
                        "Pass include_secrets=True to export them."
                    )

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Exported settings to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export settings: {e}")
            return False
    
    def import_settings(self, file_path: Path) -> bool:
        """
        Import settings from file.
        
        Args:
            file_path: Path to import file
            
        Returns:
            True if imported successfully
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.from_dict(data)
            self.save()
            
            logger.info(f"Imported settings from {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to import settings: {e}")
            return False


# Singleton instance
def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance."""
    return SettingsManager()
