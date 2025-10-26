"""
Settings Dialog
Comprehensive application settings interface
"""

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.path_manager import get_base_dir
from utils.settings_manager import SettingsManager
from utils.theme_manager import get_theme_manager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Main settings dialog with tabbed interface.
    
    Provides comprehensive access to all application settings
    organized by category.
    """
    
    settings_changed = Signal()  # Emitted when settings are saved
    
    def __init__(self, parent=None):
        """Initialize settings dialog."""
        super().__init__(parent)
        
        self.settings = SettingsManager()
        self._original_settings = self.settings.to_dict()  # For cancel/revert
        
        self._setup_ui()
        self._apply_theme()
        self._load_settings()
    
    def _apply_theme(self):
        """Apply glassmorphism theme to dialog."""
        try:
            theme_manager = get_theme_manager()
            theme_manager.apply_dialog_theme(self)
            logger.debug("Applied theme to settings dialog")
        except Exception as e:
            logger.warning(f"Failed to apply theme to dialog: {e}")
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("Settings - EncodeForge")
        self.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(self)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Create tabs
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_encoder_tab(), "Encoder")
        self.tabs.addTab(self._create_subtitle_tab(), "Subtitle")
        self.tabs.addTab(self._create_renamer_tab(), "Renamer")
        self.tabs.addTab(self._create_paths_tab(), "Paths")
        self.tabs.addTab(self._create_advanced_tab(), "Advanced")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.restore_defaults_btn = QPushButton("Restore Defaults")
        self.restore_defaults_btn.clicked.connect(self._restore_defaults)
        button_layout.addWidget(self.restore_defaults_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_settings)
        button_layout.addWidget(self.apply_btn)
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._save_and_close)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Create general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Application group
        app_group = QGroupBox("Application")
        app_layout = QFormLayout(app_group)
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Spanish", "French", "German", "Japanese"])
        app_layout.addRow("Language:", self.language_combo)
        
        self.check_updates_check = QCheckBox("Check for updates on startup")
        app_layout.addRow("", self.check_updates_check)
        
        self.auto_download_updates_check = QCheckBox("Automatically download updates")
        app_layout.addRow("", self.auto_download_updates_check)
        
        self.clear_temp_check = QCheckBox("Clear temporary files on exit")
        app_layout.addRow("", self.clear_temp_check)
        
        layout.addWidget(app_group)
        
        # UI group
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Auto"])
        ui_layout.addRow("Theme:", self.theme_combo)
        
        self.show_toolbar_check = QCheckBox("Show toolbar")
        ui_layout.addRow("", self.show_toolbar_check)
        
        self.show_statusbar_check = QCheckBox("Show status bar")
        ui_layout.addRow("", self.show_statusbar_check)
        
        layout.addWidget(ui_group)
        
        layout.addStretch()
        return widget
    
    def _create_encoder_tab(self) -> QWidget:
        """Create encoder settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Default encoder settings
        encoder_group = QGroupBox("Default Encoder Settings")
        encoder_layout = QFormLayout(encoder_group)
        
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264", "H.265/HEVC", "AV1", "VP9", "Auto"])
        encoder_layout.addRow("Default Codec:", self.codec_combo)
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow"
        ])
        encoder_layout.addRow("Default Preset:", self.preset_combo)
        
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(23)
        encoder_layout.addRow("Default CRF:", self.crf_spin)
        
        self.hw_accel_combo = QComboBox()
        self.hw_accel_combo.addItems(["None", "NVENC (NVIDIA)", "AMF (AMD)", "QSV (Intel)", "VideoToolbox (Apple)"])
        encoder_layout.addRow("Hardware Acceleration:", self.hw_accel_combo)
        
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["AAC", "MP3", "Opus", "AC3", "Copy"])
        encoder_layout.addRow("Audio Codec:", self.audio_codec_combo)
        
        self.audio_bitrate_spin = QSpinBox()
        self.audio_bitrate_spin.setRange(64, 512)
        self.audio_bitrate_spin.setValue(192)
        self.audio_bitrate_spin.setSuffix(" kbps")
        encoder_layout.addRow("Audio Bitrate:", self.audio_bitrate_spin)
        
        self.container_combo = QComboBox()
        self.container_combo.addItems(["MP4", "MKV", "WebM", "AVI", "MOV"])
        encoder_layout.addRow("Default Container:", self.container_combo)
        
        self.two_pass_check = QCheckBox("Enable two-pass encoding")
        encoder_layout.addRow("", self.two_pass_check)
        
        self.preserve_metadata_check = QCheckBox("Preserve metadata")
        encoder_layout.addRow("", self.preserve_metadata_check)
        
        layout.addWidget(encoder_group)
        layout.addStretch()
        return widget
    
    def _create_subtitle_tab(self) -> QWidget:
        """Create subtitle settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Subtitle settings
        subtitle_group = QGroupBox("Subtitle Settings")
        subtitle_layout = QFormLayout(subtitle_group)
        
        self.subtitle_mode_combo = QComboBox()
        self.subtitle_mode_combo.addItems(["Download", "Whisper AI"])
        subtitle_layout.addRow("Default Mode:", self.subtitle_mode_combo)
        
        self.subtitle_language_combo = QComboBox()
        self.subtitle_language_combo.addItems([
            "English", "Spanish", "French", "German", "Japanese",
            "Chinese", "Korean", "Italian", "Portuguese", "Russian"
        ])
        subtitle_layout.addRow("Default Language:", self.subtitle_language_combo)
        
        self.subtitle_format_combo = QComboBox()
        self.subtitle_format_combo.addItems(["SRT", "VTT", "ASS", "SSA"])
        subtitle_layout.addRow("Format:", self.subtitle_format_combo)
        
        self.subtitle_encoding_combo = QComboBox()
        self.subtitle_encoding_combo.addItems(["UTF-8", "UTF-16", "ASCII", "ISO-8859-1"])
        subtitle_layout.addRow("Encoding:", self.subtitle_encoding_combo)
        
        self.subtitle_fallback_check = QCheckBox("Enable fallback providers")
        subtitle_layout.addRow("", self.subtitle_fallback_check)
        
        self.subtitle_sync_check = QCheckBox("Auto-sync subtitles")
        subtitle_layout.addRow("", self.subtitle_sync_check)
        
        self.subtitle_translate_check = QCheckBox("Auto-translate with Whisper")
        subtitle_layout.addRow("", self.subtitle_translate_check)
        
        layout.addWidget(subtitle_group)
        
        # Whisper settings
        whisper_group = QGroupBox("Whisper AI Settings")
        whisper_layout = QFormLayout(whisper_group)
        
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems(["tiny", "base", "small", "medium", "large"])
        whisper_layout.addRow("Model Size:", self.whisper_model_combo)
        
        self.whisper_device_combo = QComboBox()
        self.whisper_device_combo.addItems(["Auto", "CPU", "CUDA (NVIDIA)", "MPS (Apple)"])
        whisper_layout.addRow("Device:", self.whisper_device_combo)
        
        layout.addWidget(whisper_group)
        layout.addStretch()
        return widget
    
    def _create_renamer_tab(self) -> QWidget:
        """Create renamer settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Renamer settings
        renamer_group = QGroupBox("Renaming Settings")
        renamer_layout = QFormLayout(renamer_group)
        
        self.media_type_combo = QComboBox()
        self.media_type_combo.addItems(["TV Show", "Movie", "Anime"])
        renamer_layout.addRow("Default Media Type:", self.media_type_combo)
        
        self.metadata_provider_combo = QComboBox()
        self.metadata_provider_combo.addItems([
            "TMDB (The Movie Database)",
            "TVDB (TheTVDB)",
            "OMDb",
            "AniDB (Anime)"
        ])
        renamer_layout.addRow("Metadata Provider:", self.metadata_provider_combo)
        
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("{title} - {season}{episode} - {quality}")
        renamer_layout.addRow("Default Pattern:", self.pattern_edit)
        
        pattern_help = QPushButton("Pattern Help")
        pattern_help.clicked.connect(self._show_pattern_help)
        renamer_layout.addRow("", pattern_help)
        
        self.replace_spaces_check = QCheckBox("Replace spaces with underscores")
        renamer_layout.addRow("", self.replace_spaces_check)
        
        self.lowercase_check = QCheckBox("Convert to lowercase")
        renamer_layout.addRow("", self.lowercase_check)
        
        self.remove_special_check = QCheckBox("Remove special characters")
        renamer_layout.addRow("", self.remove_special_check)
        
        self.preserve_extension_check = QCheckBox("Preserve file extension")
        renamer_layout.addRow("", self.preserve_extension_check)
        
        layout.addWidget(renamer_group)
        layout.addStretch()
        return widget
    
    def _create_paths_tab(self) -> QWidget:
        """Create paths settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # FFmpeg paths
        ffmpeg_group = QGroupBox("FFmpeg")
        ffmpeg_layout = QVBoxLayout(ffmpeg_group)
        
        ffmpeg_path_layout = QHBoxLayout()
        self.ffmpeg_path_edit = QLineEdit()
        self.ffmpeg_path_edit.setPlaceholderText("Path to ffmpeg executable...")
        ffmpeg_path_layout.addWidget(QLabel("FFmpeg:"))
        ffmpeg_path_layout.addWidget(self.ffmpeg_path_edit)
        
        ffmpeg_browse_btn = QPushButton("Browse...")
        ffmpeg_browse_btn.clicked.connect(self._browse_ffmpeg)
        ffmpeg_path_layout.addWidget(ffmpeg_browse_btn)
        
        ffmpeg_setup_btn = QPushButton("Setup...")
        ffmpeg_setup_btn.clicked.connect(self._run_ffmpeg_setup)
        ffmpeg_path_layout.addWidget(ffmpeg_setup_btn)
        
        ffmpeg_layout.addLayout(ffmpeg_path_layout)
        layout.addWidget(ffmpeg_group)
        
        # Whisper paths
        whisper_group = QGroupBox("Whisper AI")
        whisper_layout = QVBoxLayout(whisper_group)
        
        whisper_info = QLabel("Whisper models will be downloaded to:")
        whisper_layout.addWidget(whisper_info)
        
        whisper_path_layout = QHBoxLayout()
        self.whisper_path_edit = QLineEdit()
        self.whisper_path_edit.setReadOnly(True)
        self.whisper_path_edit.setText(str(get_base_dir() / "models"))
        whisper_path_layout.addWidget(self.whisper_path_edit)
        
        whisper_setup_btn = QPushButton("Setup Whisper...")
        whisper_setup_btn.clicked.connect(self._run_whisper_setup)
        whisper_path_layout.addWidget(whisper_setup_btn)
        
        whisper_layout.addLayout(whisper_path_layout)
        layout.addWidget(whisper_group)
        
        # Data directories
        dirs_group = QGroupBox("Data Directories")
        dirs_layout = QFormLayout(dirs_group)
        
        base_dir_edit = QLineEdit()
        base_dir_edit.setReadOnly(True)
        base_dir_edit.setText(str(get_base_dir()))
        dirs_layout.addRow("Base Directory:", base_dir_edit)
        
        open_base_btn = QPushButton("Open in Explorer")
        open_base_btn.clicked.connect(lambda: self._open_directory(get_base_dir()))
        dirs_layout.addRow("", open_base_btn)
        
        layout.addWidget(dirs_group)
        layout.addStretch()
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)
        
        self.max_threads_spin = QSpinBox()
        self.max_threads_spin.setRange(1, 32)
        self.max_threads_spin.setValue(4)
        perf_layout.addRow("Max Threads:", self.max_threads_spin)
        
        layout.addWidget(perf_group)
        
        # Logging settings
        log_group = QGroupBox("Logging")
        log_layout = QFormLayout(log_group)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_layout.addRow("Log Level:", self.log_level_combo)
        
        self.recent_files_spin = QSpinBox()
        self.recent_files_spin.setRange(0, 50)
        self.recent_files_spin.setValue(10)
        log_layout.addRow("Recent Files Limit:", self.recent_files_spin)
        
        layout.addWidget(log_group)
        
        layout.addStretch()
        return widget
    
    def _load_settings(self):
        """Load current settings into UI."""
        # General
        self.language_combo.setCurrentText(self.settings.application.language)
        self.check_updates_check.setChecked(self.settings.application.check_updates)
        self.auto_download_updates_check.setChecked(self.settings.application.auto_download_updates)
        self.clear_temp_check.setChecked(self.settings.application.clear_temp_on_exit)
        
        # UI
        self.theme_combo.setCurrentText(self.settings.ui.theme.capitalize())
        self.show_toolbar_check.setChecked(self.settings.ui.show_toolbar)
        self.show_statusbar_check.setChecked(self.settings.ui.show_statusbar)
        
        # Encoder
        self.codec_combo.setCurrentText(self.settings.encoder.codec)
        self.preset_combo.setCurrentText(self.settings.encoder.preset)
        self.crf_spin.setValue(self.settings.encoder.crf)
        self.hw_accel_combo.setCurrentText(self.settings.encoder.hw_accel)
        self.audio_codec_combo.setCurrentText(self.settings.encoder.audio_codec)
        self.audio_bitrate_spin.setValue(self.settings.encoder.audio_bitrate)
        self.container_combo.setCurrentText(self.settings.encoder.container)
        self.two_pass_check.setChecked(self.settings.encoder.two_pass)
        self.preserve_metadata_check.setChecked(self.settings.encoder.preserve_metadata)
        
        # Subtitle
        self.subtitle_mode_combo.setCurrentText(self.settings.subtitle.mode.capitalize())
        self.subtitle_language_combo.setCurrentText(self.settings.subtitle.language)
        self.subtitle_format_combo.setCurrentText(self.settings.subtitle.subtitle_format)
        self.subtitle_encoding_combo.setCurrentText(self.settings.subtitle.encoding)
        self.subtitle_fallback_check.setChecked(self.settings.subtitle.fallback)
        self.subtitle_sync_check.setChecked(self.settings.subtitle.sync)
        self.subtitle_translate_check.setChecked(self.settings.subtitle.translate)
        self.whisper_model_combo.setCurrentText(self.settings.subtitle.whisper_model)
        self.whisper_device_combo.setCurrentText(self.settings.subtitle.whisper_device)
        
        # Renamer
        self.media_type_combo.setCurrentText(self.settings.renamer.media_type)
        self.metadata_provider_combo.setCurrentText(self.settings.renamer.provider)
        self.pattern_edit.setText(self.settings.renamer.pattern)
        self.replace_spaces_check.setChecked(self.settings.renamer.replace_spaces)
        self.lowercase_check.setChecked(self.settings.renamer.lowercase)
        self.remove_special_check.setChecked(self.settings.renamer.remove_special)
        self.preserve_extension_check.setChecked(self.settings.renamer.preserve_extension)
        
        # Paths
        self.ffmpeg_path_edit.setText(self.settings.application.ffmpeg_path)
        
        # Advanced
        self.max_threads_spin.setValue(self.settings.application.max_threads)
        self.log_level_combo.setCurrentText(self.settings.application.log_level)
        self.recent_files_spin.setValue(self.settings.application.recent_files_limit)
    
    def _save_settings(self):
        """Save UI values to settings."""
        # General
        self.settings.application.language = self.language_combo.currentText().lower()[:2]
        self.settings.application.check_updates = self.check_updates_check.isChecked()
        self.settings.application.auto_download_updates = self.auto_download_updates_check.isChecked()
        self.settings.application.clear_temp_on_exit = self.clear_temp_check.isChecked()
        
        # UI
        self.settings.ui.theme = self.theme_combo.currentText().lower()
        self.settings.ui.show_toolbar = self.show_toolbar_check.isChecked()
        self.settings.ui.show_statusbar = self.show_statusbar_check.isChecked()
        
        # Encoder
        self.settings.encoder.codec = self.codec_combo.currentText()
        self.settings.encoder.preset = self.preset_combo.currentText()
        self.settings.encoder.crf = self.crf_spin.value()
        self.settings.encoder.hw_accel = self.hw_accel_combo.currentText()
        self.settings.encoder.audio_codec = self.audio_codec_combo.currentText()
        self.settings.encoder.audio_bitrate = self.audio_bitrate_spin.value()
        self.settings.encoder.container = self.container_combo.currentText()
        self.settings.encoder.two_pass = self.two_pass_check.isChecked()
        self.settings.encoder.preserve_metadata = self.preserve_metadata_check.isChecked()
        
        # Subtitle
        self.settings.subtitle.mode = self.subtitle_mode_combo.currentText().lower()
        self.settings.subtitle.language = self.subtitle_language_combo.currentText()
        self.settings.subtitle.subtitle_format = self.subtitle_format_combo.currentText()
        self.settings.subtitle.encoding = self.subtitle_encoding_combo.currentText()
        self.settings.subtitle.fallback = self.subtitle_fallback_check.isChecked()
        self.settings.subtitle.sync = self.subtitle_sync_check.isChecked()
        self.settings.subtitle.translate = self.subtitle_translate_check.isChecked()
        self.settings.subtitle.whisper_model = self.whisper_model_combo.currentText()
        self.settings.subtitle.whisper_device = self.whisper_device_combo.currentText()
        
        # Renamer
        self.settings.renamer.media_type = self.media_type_combo.currentText()
        self.settings.renamer.provider = self.metadata_provider_combo.currentText()
        self.settings.renamer.pattern = self.pattern_edit.text()
        self.settings.renamer.replace_spaces = self.replace_spaces_check.isChecked()
        self.settings.renamer.lowercase = self.lowercase_check.isChecked()
        self.settings.renamer.remove_special = self.remove_special_check.isChecked()
        self.settings.renamer.preserve_extension = self.preserve_extension_check.isChecked()
        
        # Paths
        self.settings.application.ffmpeg_path = self.ffmpeg_path_edit.text()
        
        # Advanced
        self.settings.application.max_threads = self.max_threads_spin.value()
        self.settings.application.log_level = self.log_level_combo.currentText()
        self.settings.application.recent_files_limit = self.recent_files_spin.value()
        
        # Save to disk
        self.settings.save()
        logger.info("Settings saved successfully")
    
    def _apply_settings(self):
        """Apply settings without closing dialog."""
        self._save_settings()
        self.settings_changed.emit()
        QMessageBox.information(self, "Settings Applied", "Settings have been saved successfully.")
    
    def _save_and_close(self):
        """Save settings and close dialog."""
        self._save_settings()
        self.settings_changed.emit()
        self.accept()
    
    def _restore_defaults(self):
        """Restore all settings to defaults."""
        result = QMessageBox.question(
            self,
            "Restore Defaults",
            "Are you sure you want to restore all settings to their default values?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            # Reset to defaults (create new instances)
            from utils.settings_manager import (
                ApplicationSettings,
                EncoderSettings,
                RenamerSettings,
                SubtitleSettings,
                UISettings,
            )
            
            self.settings.encoder = EncoderSettings()
            self.settings.subtitle = SubtitleSettings()
            self.settings.renamer = RenamerSettings()
            self.settings.ui = UISettings()
            self.settings.application = ApplicationSettings()
            
            self._load_settings()
            logger.info("Settings restored to defaults")
    
    def _browse_ffmpeg(self):
        """Browse for FFmpeg executable."""
        file_filter = "FFmpeg Executable (ffmpeg ffmpeg.exe);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FFmpeg Executable",
            "",
            file_filter
        )
        
        if path:
            self.ffmpeg_path_edit.setText(path)
    
    def _run_ffmpeg_setup(self):
        """Run FFmpeg setup dialog."""
        from app.dialogs import FFmpegSetupDialog
        
        dialog = FFmpegSetupDialog(self, required=False)
        if dialog.exec():
            # Reload FFmpeg path
            self.ffmpeg_path_edit.setText(self.settings.application.ffmpeg_path)
    
    def _run_whisper_setup(self):
        """Run Whisper setup dialog."""
        QMessageBox.information(
            self,
            "Whisper Setup",
            "Whisper AI setup dialog will be implemented soon.\n\n"
            "For now, please install PyTorch and Whisper manually:\n"
            "pip install torch whisper"
        )
    
    def _show_pattern_help(self):
        """Show pattern help dialog."""
        help_text = """
<h3>Renaming Pattern Help</h3>

<p>Available placeholders:</p>
<ul>
    <li><b>{title}</b> - Media title</li>
    <li><b>{season}</b> - Season number (S01)</li>
    <li><b>{episode}</b> - Episode number (E05)</li>
    <li><b>{year}</b> - Release year</li>
    <li><b>{quality}</b> - Video quality (1080p, 720p)</li>
    <li><b>{codec}</b> - Video codec (h264, hevc)</li>
    <li><b>{audio}</b> - Audio codec (AAC, AC3)</li>
</ul>

<p>Examples:</p>
<ul>
    <li>{title} - {season}{episode} - {quality}</li>
    <li>{title} ({year})</li>
    <li>{title}.{season}{episode}.{quality}.{codec}</li>
</ul>
        """
        
        QMessageBox.information(self, "Pattern Help", help_text)
    
    def _open_directory(self, path: Path):
        """Open directory in system file explorer."""
        import subprocess
        import sys
        
        if sys.platform == "win32":
            subprocess.run(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:  # linux
            subprocess.run(["xdg-open", str(path)])
    
    def reject(self):
        """Handle dialog cancellation."""
        # Restore original settings
        self.settings.from_dict(self._original_settings)
        super().reject()
