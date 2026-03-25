"""
EncodeForge Setup Dialogs
Standalone dialog windows for initial setup and configuration
"""

from .ffmpeg_setup_dialog import FFmpegSetupDialog
from .settings_dialog import SettingsDialog
from .update_dialog import UpdateAvailableDialog
from .whisper_setup_dialog import WhisperSetupDialog

__all__ = [
    'FFmpegSetupDialog',
    'SettingsDialog',
    'UpdateAvailableDialog',
    'WhisperSetupDialog',
]
