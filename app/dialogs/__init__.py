"""
EncodeForge Setup Dialogs
Standalone dialog windows for initial setup and configuration
"""

from .ffmpeg_setup_dialog import FFmpegSetupDialog
from .settings_dialog import SettingsDialog

__all__ = [
    'FFmpegSetupDialog',
    'SettingsDialog',
]

# TODO: Add when implemented
# from .whisper_setup_dialog import WhisperSetupDialog
# from .update_dialog import UpdateDialog
# from .pattern_editor_dialog import PatternEditorDialog
