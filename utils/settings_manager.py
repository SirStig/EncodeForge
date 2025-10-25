"""
EncodeForge Settings Manager
Persistent application settings with validation and defaults
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, field

from core import path_manager

logger = logging.getLogger(__name__)


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
    provider: str = "TMDB (The Movie Database)"
    pattern: str = "{title} - {season}{episode} - {quality}"
    replace_spaces: bool = False
    lowercase: bool = False
    remove_special: bool = False
    preserve_extension: bool = True


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
    clear_temp_on_exit: bool = True
    log_level: str = "INFO"
    max_threads: int = 4
    recent_files_limit: int = 10
    language: str = "en"


class SettingsManager:
    """
    Manages application settings with persistence.
    
    Handles loading, saving, validation, and defaults for all settings.
    """
    
    _instance: Optional['SettingsManager'] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize settings manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self.settings_file = path_manager.get_settings_file()
        
        # Initialize settings with defaults
        self.encoder = EncoderSettings()
        self.subtitle = SubtitleSettings()
        self.renamer = RenamerSettings()
        self.ui = UISettings()
        self.application = ApplicationSettings()
        
        # Load settings from disk
        self.load()
        
        logger.info("Settings manager initialized")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert all settings to dictionary."""
        return {
            'encoder': asdict(self.encoder),
            'subtitle': asdict(self.subtitle),
            'renamer': asdict(self.renamer),
            'ui': asdict(self.ui),
            'application': asdict(self.application),
            'version': '0.5.0',
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """Load settings from dictionary."""
        try:
            if 'encoder' in data:
                self.encoder = EncoderSettings(**data['encoder'])
            if 'subtitle' in data:
                self.subtitle = SubtitleSettings(**data['subtitle'])
            if 'renamer' in data:
                self.renamer = RenamerSettings(**data['renamer'])
            if 'ui' in data:
                self.ui = UISettings(**data['ui'])
            if 'application' in data:
                self.application = ApplicationSettings(**data['application'])
        except Exception as e:
            logger.error(f"Error loading settings from dict: {e}")
            logger.info("Using default settings")
    
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
            
            # Save with pretty formatting
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.debug(f"Saved settings to {self.settings_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False
    
    def reset(self):
        """Reset all settings to defaults."""
        self.encoder = EncoderSettings()
        self.subtitle = SubtitleSettings()
        self.renamer = RenamerSettings()
        self.ui = UISettings()
        self.application = ApplicationSettings()
        
        self.save()
        logger.info("Reset all settings to defaults")
    
    def reset_section(self, section: str):
        """
        Reset specific settings section to defaults.
        
        Args:
            section: Section name (encoder, subtitle, renamer, ui, application)
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
        
        self.save()
        logger.info(f"Reset {section} settings to defaults")
    
    def export_settings(self, file_path: Path) -> bool:
        """
        Export settings to file.
        
        Args:
            file_path: Path to export file
            
        Returns:
            True if exported successfully
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2)
            
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
