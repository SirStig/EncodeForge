"""
Settings Dialog
Comprehensive application settings interface
"""

import logging
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import __version__ as APP_VERSION
from core.path_manager import get_base_dir
from core.handlers.models import ConversionSettings
from utils.settings_manager import SettingsManager
from utils.theme_manager import get_theme_manager

logger = logging.getLogger(__name__)

# CRF quality descriptions used by the live indicator
_CRF_LABELS = [
    (0,  17, "Lossless / Visually perfect"),
    (18, 23, "High quality (recommended)"),
    (24, 27, "Good quality"),
    (28, 33, "Acceptable quality"),
    (34, 51, "Low quality / Small file"),
]


def _crf_description(value: int) -> str:
    for lo, hi, label in _CRF_LABELS:
        if lo <= value <= hi:
            return label
    return ""


def _hint(text: str) -> QLabel:
    """Return a small, muted helper label for additional context."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #888; font-size: 11px; margin-bottom: 4px;")
    return lbl


class SettingsPanel(QWidget):
    """
    Tabbed settings editor for use in the main window or inside SettingsDialog.
    """

    settings_changed = Signal()

    def __init__(self, parent=None, *, show_action_bar: bool = True):
        super().__init__(parent)
        self.settings = SettingsManager()
        self._original_settings = deepcopy(self.settings.to_dict())
        self._show_action_bar = show_action_bar
        self._setup_ui()
        self._apply_theme()
        self._load_settings()

    def begin_session(self) -> None:
        self._original_settings = deepcopy(self.settings.to_dict())

    def revert_unsaved(self) -> None:
        self.settings.from_dict(deepcopy(self._original_settings))
        self._load_settings()
        self.settings_changed.emit()

    def save_to_disk(self, *, notify: bool = False) -> None:
        self._save_settings()
        self.settings_changed.emit()
        self._original_settings = deepcopy(self.settings.to_dict())
        if notify:
            QMessageBox.information(
                self, "Settings Applied", "Settings have been saved successfully."
            )

    def restore_defaults(self) -> None:
        self._restore_defaults()

    def _apply_theme(self) -> None:
        try:
            theme_manager = get_theme_manager()
            theme_manager.apply_dialog_theme(self)
            logger.debug("Applied theme to settings panel")
        except Exception as e:
            logger.warning("Failed to apply theme to settings panel: %s", e)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_general_tab()), "General")
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_encoder_tab()), "Encoder")
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_subtitle_tab()), "Subtitle")
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_renamer_tab()), "Renamer")
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_accounts_tab()), "Accounts")
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_paths_tab()), "Paths")
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_advanced_tab()), "Advanced")
        self.tabs.addTab(self._wrap_in_scroll_area(self._create_about_tab()), "About")
        layout.addWidget(self.tabs, 1)
        if self._show_action_bar:
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            rd = QPushButton("Restore Defaults")
            rd.setToolTip("Reset every setting back to its factory default value.")
            rd.clicked.connect(self._restore_defaults)
            button_layout.addWidget(rd)
            rv = QPushButton("Revert")
            rv.setToolTip("Undo unsaved changes and restore values from the last save.")
            rv.clicked.connect(self.revert_unsaved)
            button_layout.addWidget(rv)
            sv = QPushButton("Save")
            sv.setDefault(True)
            sv.setToolTip("Save all changes to disk.")
            sv.clicked.connect(lambda: self.save_to_disk(notify=False))
            button_layout.addWidget(sv)
            layout.addLayout(button_layout)

    def _wrap_in_scroll_area(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    # ------------------------------------------------------------------ #
    #  General tab
    # ------------------------------------------------------------------ #
    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Application group
        app_group = QGroupBox("Application")
        app_layout = QFormLayout(app_group)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Spanish", "French", "German", "Japanese"])
        self.language_combo.setToolTip(
            "Display language for the application interface.\n"
            "A restart is required for the change to take effect."
        )
        app_layout.addRow("Language:", self.language_combo)

        self.check_updates_check = QCheckBox("Check for updates on startup")
        self.check_updates_check.setToolTip(
            "Ping GitHub on launch to see if a newer version of EncodeForge is available.\n"
            "No data is collected — only the latest version number is fetched."
        )
        app_layout.addRow("", self.check_updates_check)

        self.auto_download_updates_check = QCheckBox("Automatically download updates")
        self.auto_download_updates_check.setToolTip(
            "Download and prepare updates in the background without asking first.\n"
            "You will still be prompted before anything is installed."
        )
        app_layout.addRow("", self.auto_download_updates_check)

        self.clear_temp_check = QCheckBox("Clear temporary files on exit")
        self.clear_temp_check.setToolTip(
            "Delete intermediate files created during encoding when the app closes.\n"
            "Disable if you want to inspect or resume partial encodes."
        )
        app_layout.addRow("", self.clear_temp_check)

        layout.addWidget(app_group)

        # UI group
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Auto"])
        self.theme_combo.setToolTip(
            "Color scheme for the interface.\n"
            "Auto follows your operating system's dark / light mode preference."
        )
        ui_layout.addRow("Theme:", self.theme_combo)

        self.show_toolbar_check = QCheckBox("Show toolbar")
        self.show_toolbar_check.setToolTip("Display the quick-access toolbar at the top of the window.")
        ui_layout.addRow("", self.show_toolbar_check)

        self.show_statusbar_check = QCheckBox("Show status bar")
        self.show_statusbar_check.setToolTip("Display the status bar at the bottom of the window.")
        ui_layout.addRow("", self.show_statusbar_check)

        layout.addWidget(ui_group)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  Encoder tab
    # ------------------------------------------------------------------ #
    def _create_encoder_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        encoder_group = QGroupBox("Default Encoder Settings")
        encoder_group.setToolTip("These values pre-fill the Encoder tab. You can override them per job.")
        encoder_layout = QFormLayout(encoder_group)

        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264", "H.265/HEVC", "AV1", "VP9", "Auto"])
        self.codec_combo.setToolTip(
            "Video codec used for encoding.\n\n"
            "H.264  — Best compatibility (phones, TVs, browsers). Good quality.\n"
            "H.265  — ~50 % smaller files than H.264 at the same quality. Slightly slower to encode.\n"
            "AV1    — Best compression, completely free/open. Slow on CPU; fast with modern GPUs.\n"
            "VP9    — Google's open codec, good for web video.\n"
            "Auto   — Let EncodeForge pick based on the source file."
        )
        encoder_layout.addRow("Default Codec:", self.codec_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow"
        ])
        self.preset_combo.setToolTip(
            "Speed vs. compression trade-off.\n\n"
            "Faster presets finish sooner but produce larger files at the same quality.\n"
            "Slower presets squeeze more quality into the same file size.\n\n"
            "Recommended: 'medium' for most uses, 'slow' for archiving."
        )
        encoder_layout.addRow("Encoding Speed:", self.preset_combo)
        encoder_layout.addRow("", _hint("Slower = smaller file at the same quality. 'medium' is a good default."))

        # CRF with live quality indicator
        crf_row = QHBoxLayout()
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(23)
        self.crf_spin.setToolTip(
            "Constant Rate Factor — the primary quality knob.\n\n"
            "Lower value = higher quality = larger file.\n"
            "Higher value = lower quality = smaller file.\n\n"
            "Typical range: 18 (high quality) → 28 (smaller file).\n"
            "Default 23 is a good all-round starting point."
        )
        self.crf_quality_label = QLabel()
        self.crf_quality_label.setStyleSheet("color: #888; font-size: 11px;")
        self._update_crf_label(self.crf_spin.value())
        self.crf_spin.valueChanged.connect(self._update_crf_label)
        crf_row.addWidget(self.crf_spin)
        crf_row.addWidget(self.crf_quality_label)
        crf_row.addStretch()
        encoder_layout.addRow("CRF Quality (0–51):", crf_row)
        encoder_layout.addRow("", _hint("Lower = better quality, larger file. 18–28 covers most use cases."))

        self.hw_accel_combo = QComboBox()
        self.hw_accel_combo.addItems(["None", "NVENC (NVIDIA)", "AMF (AMD)", "QSV (Intel)", "VideoToolbox (Apple)"])
        self.hw_accel_combo.setToolTip(
            "Use your GPU to encode significantly faster (5–10×).\n\n"
            "NVENC        — NVIDIA GPUs (GTX 10xx or newer)\n"
            "AMF          — AMD GPUs (RX 400 series or newer)\n"
            "QSV          — Intel CPUs with integrated graphics (Broadwell or newer)\n"
            "VideoToolbox — Apple Silicon and Intel Macs\n\n"
            "GPU encoding is faster but may produce slightly larger files than CPU at the same CRF."
        )
        encoder_layout.addRow("Hardware Acceleration:", self.hw_accel_combo)

        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["AAC", "MP3", "Opus", "AC3", "Copy"])
        self.audio_codec_combo.setToolTip(
            "Audio codec for the output file.\n\n"
            "AAC  — Best compatibility with MP4; good quality at low bitrates.\n"
            "MP3  — Universally supported; slightly older compression.\n"
            "Opus — Best quality per bitrate; ideal for MKV/WebM.\n"
            "AC3  — Dolby Digital; common in home-theatre files.\n"
            "Copy — Pass the audio through unchanged. Fastest; no re-encoding."
        )
        encoder_layout.addRow("Audio Codec:", self.audio_codec_combo)

        self.audio_bitrate_spin = QSpinBox()
        self.audio_bitrate_spin.setRange(64, 512)
        self.audio_bitrate_spin.setValue(192)
        self.audio_bitrate_spin.setSuffix(" kbps")
        self.audio_bitrate_spin.setToolTip(
            "Audio bitrate for the re-encoded audio track.\n\n"
            "128 kbps — Decent quality for speech/podcasts.\n"
            "192 kbps — Good quality for music and film (recommended).\n"
            "320 kbps — Near-lossless; use for archiving.\n\n"
            "Ignored when Audio Codec is set to 'Copy'."
        )
        encoder_layout.addRow("Audio Bitrate:", self.audio_bitrate_spin)

        self.container_combo = QComboBox()
        self.container_combo.addItems(["MP4", "MKV", "WebM", "AVI", "MOV"])
        self.container_combo.setToolTip(
            "Output file container (wrapper format).\n\n"
            "MP4  — Most compatible with devices, streaming, and social media.\n"
            "MKV  — Supports multiple audio/subtitle tracks; great for archiving.\n"
            "WebM — Optimised for web browsers (AV1/VP9 + Opus).\n"
            "AVI  — Legacy format; avoid unless required by older software.\n"
            "MOV  — Apple QuickTime format; native on macOS/iOS."
        )
        encoder_layout.addRow("Output Container:", self.container_combo)

        self.two_pass_check = QCheckBox("Enable two-pass encoding")
        self.two_pass_check.setToolTip(
            "Encode the video in two stages:\n"
            "  Pass 1 — Analyse the whole video to understand its complexity.\n"
            "  Pass 2 — Encode using that analysis for better bit distribution.\n\n"
            "Results in better quality at the same file size, but takes roughly twice as long.\n"
            "Most useful when targeting a specific file size rather than a CRF quality level."
        )
        encoder_layout.addRow("", self.two_pass_check)

        self.preserve_metadata_check = QCheckBox("Preserve metadata")
        self.preserve_metadata_check.setToolTip(
            "Copy title, artist, date, track number, and other tags from the source file\n"
            "into the output file. Disable if you want a clean output with no embedded metadata."
        )
        encoder_layout.addRow("", self.preserve_metadata_check)

        layout.addWidget(encoder_group)
        layout.addStretch()
        return widget

    def _update_crf_label(self, value: int) -> None:
        self.crf_quality_label.setText(f"— {_crf_description(value)}")

    # ------------------------------------------------------------------ #
    #  Subtitle tab
    # ------------------------------------------------------------------ #
    def _create_subtitle_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        subtitle_group = QGroupBox("Subtitle Settings")
        subtitle_layout = QFormLayout(subtitle_group)

        self.subtitle_mode_combo = QComboBox()
        self.subtitle_mode_combo.addItems(["Download", "Whisper AI"])
        self.subtitle_mode_combo.setToolTip(
            "Default method for obtaining subtitles.\n\n"
            "Download   — Fetch pre-made subtitles from online services "
            "(OpenSubtitles, Addic7ed, SubDL, etc.).\n"
            "Whisper AI — Generate subtitles locally by transcribing the audio using OpenAI Whisper.\n"
            "             More accurate for uncommon languages; no internet required."
        )
        subtitle_layout.addRow("Default Mode:", self.subtitle_mode_combo)

        self.subtitle_language_combo = QComboBox()
        self.subtitle_language_combo.addItems([
            "English", "Spanish", "French", "German", "Japanese",
            "Chinese", "Korean", "Italian", "Portuguese", "Russian"
        ])
        self.subtitle_language_combo.setToolTip(
            "Default language to search for when downloading subtitles,\n"
            "or the target language when generating/translating with Whisper AI."
        )
        subtitle_layout.addRow("Default Language:", self.subtitle_language_combo)

        self.subtitle_format_combo = QComboBox()
        self.subtitle_format_combo.addItems(["SRT", "VTT", "ASS", "SSA"])
        self.subtitle_format_combo.setToolTip(
            "Output file format for downloaded or generated subtitles.\n\n"
            "SRT  — SubRip; most compatible with media players and devices.\n"
            "VTT  — WebVTT; standard for web browsers and streaming.\n"
            "ASS  — Advanced SubStation Alpha; supports rich styling and karaoke.\n"
            "SSA  — Sub Station Alpha; predecessor to ASS; use ASS instead."
        )
        subtitle_layout.addRow("Subtitle Format:", self.subtitle_format_combo)

        self.subtitle_encoding_combo = QComboBox()
        self.subtitle_encoding_combo.addItems(["UTF-8", "UTF-16", "ASCII", "ISO-8859-1"])
        self.subtitle_encoding_combo.setToolTip(
            "Character encoding used when writing subtitle files.\n\n"
            "UTF-8      — Recommended. Supports all languages and special characters.\n"
            "UTF-16     — Some Windows apps prefer this; larger file size.\n"
            "ASCII      — English-only; safe but loses accents and non-Latin characters.\n"
            "ISO-8859-1 — Western European; use only for legacy compatibility."
        )
        subtitle_layout.addRow("Text Encoding:", self.subtitle_encoding_combo)

        self.subtitle_fallback_check = QCheckBox("Use fallback providers if primary fails")
        self.subtitle_fallback_check.setToolTip(
            "If the primary subtitle service doesn't have a match, automatically try\n"
            "other configured providers before giving up. Slightly slower but more reliable."
        )
        subtitle_layout.addRow("", self.subtitle_fallback_check)

        self.subtitle_sync_check = QCheckBox("Auto-sync subtitles to video")
        self.subtitle_sync_check.setToolTip(
            "Attempt to automatically re-align subtitle timing so it matches the video.\n"
            "Useful when the downloaded subtitle is slightly out of sync.\n"
            "Requires FFmpeg and may add processing time. (Experimental)"
        )
        subtitle_layout.addRow("", self.subtitle_sync_check)

        self.subtitle_translate_check = QCheckBox("Auto-translate to selected language with Whisper")
        self.subtitle_translate_check.setToolTip(
            "After transcribing audio with Whisper AI, translate the result into\n"
            "the language selected above. Only applies when mode is 'Whisper AI'.\n\n"
            "Note: Translation quality depends on Whisper model size.\n"
            "'medium' or 'large' are recommended for translation."
        )
        subtitle_layout.addRow("", self.subtitle_translate_check)

        layout.addWidget(subtitle_group)

        # Whisper settings
        whisper_group = QGroupBox("Whisper AI Settings")
        whisper_group.setToolTip(
            "Settings for local AI-based subtitle generation using OpenAI Whisper.\n"
            "Only used when subtitle mode is 'Whisper AI'."
        )
        whisper_layout = QFormLayout(whisper_group)

        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems([
            "tiny   (~75 MB)",
            "base   (~142 MB)",
            "small  (~466 MB)",
            "medium (~1.5 GB)",
            "large  (~2.9 GB)",
        ])
        self.whisper_model_combo.setToolTip(
            "Whisper model size — larger models are more accurate but need more RAM and time.\n\n"
            "tiny   — Very fast; suitable for simple content. Low accuracy.\n"
            "base   — Fast; good for clear speech.\n"
            "small  — Balanced speed and accuracy (recommended starting point).\n"
            "medium — High accuracy; needs ~4 GB RAM or VRAM.\n"
            "large  — Best accuracy; needs ~8–10 GB RAM or VRAM.\n\n"
            "Models are downloaded on first use via the Whisper Setup in the Paths tab."
        )
        whisper_layout.addRow("Model Size:", self.whisper_model_combo)
        whisper_layout.addRow("", _hint(
            "Larger = more accurate, but slower and uses more memory. 'small' is a good starting point."
        ))

        self.whisper_device_combo = QComboBox()
        self.whisper_device_combo.addItems(["Auto", "CPU", "CUDA (NVIDIA)", "MPS (Apple)"])
        self.whisper_device_combo.setToolTip(
            "Processing device for Whisper AI transcription.\n\n"
            "Auto         — Automatically picks the best available device (recommended).\n"
            "CPU          — Works everywhere; slower for large models.\n"
            "CUDA         — NVIDIA GPU; much faster. Requires CUDA toolkit installed.\n"
            "MPS          — Apple Silicon GPU (M1/M2/M3); faster than CPU on Mac."
        )
        whisper_layout.addRow("Processing Device:", self.whisper_device_combo)

        layout.addWidget(whisper_group)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  Renamer tab
    # ------------------------------------------------------------------ #
    def _create_renamer_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        renamer_group = QGroupBox("Renaming Settings")
        renamer_layout = QFormLayout(renamer_group)

        self.media_type_combo = QComboBox()
        self.media_type_combo.addItems(["TV Show", "Movie", "Anime"])
        self.media_type_combo.setToolTip(
            "Type of media being renamed. Determines which metadata fields are\n"
            "available in the pattern (e.g., {season}/{episode} for TV shows)\n"
            "and which providers are most appropriate."
        )
        renamer_layout.addRow("Default Media Type:", self.media_type_combo)

        self.metadata_provider_combo = QComboBox()
        self.metadata_provider_combo.addItems([
            "TMDB (The Movie Database)",
            "TVDB (TheTVDB)",
            "OMDb",
            "Trakt",
            "TVmaze",
            "AniDB (Anime)",
            "Kitsu (Anime)",
            "Jikan (MyAnimeList)",
        ])
        self.metadata_provider_combo.setToolTip(
            "Online database used to look up titles, episode names, and other metadata.\n\n"
            "TMDB        — Recommended for movies and TV. Requires free API key.\n"
            "TVDB        — Best episode-level data for TV shows. Requires free API key.\n"
            "OMDb         — Uses IMDb data; free tier available.\n"
            "Trakt        — Community-driven; good for watch-history integration.\n"
            "TVmaze       — Free, no API key needed; good for TV episode data.\n"
            "AniDB        — Comprehensive anime database; account required.\n"
            "Kitsu        — Modern anime database; no key required.\n"
            "Jikan        — Unofficial MyAnimeList API; no key required."
        )
        renamer_layout.addRow("Metadata Provider:", self.metadata_provider_combo)

        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("{title} - {season}{episode} - {quality}")
        self.pattern_edit.setToolTip(
            "Template for the output filename. Use curly-brace placeholders that\n"
            "will be replaced with real values fetched from the metadata provider.\n\n"
            "Click 'Pattern Help' below for a full list of available placeholders."
        )
        renamer_layout.addRow("Filename Pattern:", self.pattern_edit)

        pattern_help = QPushButton("Pattern Help…")
        pattern_help.setToolTip("Show all available placeholders and example patterns.")
        pattern_help.clicked.connect(self._show_pattern_help)
        renamer_layout.addRow("", pattern_help)

        self.replace_spaces_check = QCheckBox("Replace spaces with underscores")
        self.replace_spaces_check.setToolTip(
            "Convert spaces in the filename to underscores (e.g. 'My Show' → 'My_Show').\n"
            "Useful for compatibility with scripts or Linux file systems."
        )
        renamer_layout.addRow("", self.replace_spaces_check)

        self.lowercase_check = QCheckBox("Convert filename to lowercase")
        self.lowercase_check.setToolTip(
            "Make the entire output filename lowercase.\n"
            "Helps avoid case-sensitivity issues on Linux file systems."
        )
        renamer_layout.addRow("", self.lowercase_check)

        self.remove_special_check = QCheckBox("Remove special characters")
        self.remove_special_check.setToolTip(
            "Strip characters such as !, @, #, :, ?, *, etc. from the filename.\n"
            "These characters are illegal in filenames on Windows and some other systems."
        )
        renamer_layout.addRow("", self.remove_special_check)

        self.preserve_extension_check = QCheckBox("Preserve original file extension")
        self.preserve_extension_check.setToolTip(
            "Keep the original file extension (e.g. .mkv, .mp4) after renaming.\n"
            "Disable only if you want the extension to be determined by the pattern."
        )
        renamer_layout.addRow("", self.preserve_extension_check)

        layout.addWidget(renamer_group)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  Accounts tab
    # ------------------------------------------------------------------ #
    def _create_accounts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(_hint(
            "API keys are stored locally and never transmitted except to the respective services. "
            "All fields are optional — EncodeForge works without them, but free keys unlock higher "
            "request quotas and richer metadata."
        ))

        meta = QGroupBox("Metadata API Keys (optional)")
        meta_form = QFormLayout(meta)

        self.tmdb_key_edit = QLineEdit()
        self.tmdb_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tmdb_key_edit.setPlaceholderText("Paste your TMDB v3 API key…")
        self.tmdb_key_edit.setToolTip(
            "The Movie Database — free API key at themoviedb.org/settings/api\n"
            "Used for movie and TV show metadata, posters, and episode data.\n"
            "Recommended for best results with the Renamer."
        )
        meta_form.addRow("TMDB:", self.tmdb_key_edit)

        self.tvdb_key_edit = QLineEdit()
        self.tvdb_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tvdb_key_edit.setPlaceholderText("Paste your TVDB API key…")
        self.tvdb_key_edit.setToolTip(
            "TheTVDB — free API key at thetvdb.com/dashboard\n"
            "Best database for TV show episode-level metadata and artwork."
        )
        meta_form.addRow("TVDB:", self.tvdb_key_edit)

        self.omdb_key_edit = QLineEdit()
        self.omdb_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.omdb_key_edit.setPlaceholderText("Paste your OMDb API key…")
        self.omdb_key_edit.setToolTip(
            "Open Movie Database — free tier at omdbapi.com\n"
            "Provides IMDb-sourced metadata. Free tier allows 1,000 requests/day."
        )
        meta_form.addRow("OMDb:", self.omdb_key_edit)

        self.trakt_key_edit = QLineEdit()
        self.trakt_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.trakt_key_edit.setPlaceholderText("Paste your Trakt Client ID…")
        self.trakt_key_edit.setToolTip(
            "Trakt — free API key at trakt.tv/oauth/applications\n"
            "Community-driven tracking and metadata. Good for TV ratings and history."
        )
        meta_form.addRow("Trakt:", self.trakt_key_edit)

        self.fanart_key_edit = QLineEdit()
        self.fanart_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.fanart_key_edit.setPlaceholderText("Paste your Fanart.tv API key…")
        self.fanart_key_edit.setToolTip(
            "Fanart.tv — free personal key at fanart.tv/get-an-api-key\n"
            "High-resolution artwork, logos, and backgrounds for movies and TV."
        )
        meta_form.addRow("Fanart.tv:", self.fanart_key_edit)

        self.anidb_key_edit = QLineEdit()
        self.anidb_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.anidb_key_edit.setPlaceholderText("Paste your AniDB API key…")
        self.anidb_key_edit.setToolTip(
            "AniDB — requires a free account at anidb.net\n"
            "Comprehensive anime database with detailed episode and character data."
        )
        meta_form.addRow("AniDB:", self.anidb_key_edit)

        layout.addWidget(meta)

        subs = QGroupBox("OpenSubtitles Account (optional)")
        subs_form = QFormLayout(subs)
        subs.setToolTip(
            "Log in to your OpenSubtitles account for higher download quotas.\n"
            "Anonymous users are limited to a few downloads per day.\n"
            "Free account at opensubtitles.com"
        )

        self.os_user_edit = QLineEdit()
        self.os_user_edit.setPlaceholderText("Your opensubtitles.com username…")
        self.os_user_edit.setToolTip("Username for your opensubtitles.com account.")
        subs_form.addRow("Username:", self.os_user_edit)

        self.os_pass_edit = QLineEdit()
        self.os_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.os_pass_edit.setPlaceholderText("Your opensubtitles.com password…")
        self.os_pass_edit.setToolTip("Password for your opensubtitles.com account. Stored locally only.")
        subs_form.addRow("Password:", self.os_pass_edit)

        layout.addWidget(subs)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  About tab
    # ------------------------------------------------------------------ #
    def _create_about_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        body = QLabel(
            f"<h2>EncodeForge</h2><p><b>Version {APP_VERSION}</b></p>"
            "<p>Video encoding, subtitles, and metadata-based renaming.</p>"
            '<p><a href="https://github.com/SirStig/EncodeForge">github.com/SirStig/EncodeForge</a></p>'
        )
        body.setOpenExternalLinks(True)
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  Paths tab
    # ------------------------------------------------------------------ #
    def _create_paths_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # FFmpeg paths
        ffmpeg_group = QGroupBox("FFmpeg")
        ffmpeg_group.setToolTip(
            "FFmpeg is the encoding engine that EncodeForge uses for all video and audio processing.\n"
            "Leave blank to use the FFmpeg that is on your system PATH, or specify a custom location."
        )
        ffmpeg_layout = QVBoxLayout(ffmpeg_group)

        ffmpeg_layout.addWidget(QLabel("FFmpeg executable:"))
        self.ffmpeg_path_edit = QLineEdit()
        self.ffmpeg_path_edit.setPlaceholderText("Auto-detected from system PATH (leave blank to use system default)")
        self.ffmpeg_path_edit.setToolTip(
            "Path to the ffmpeg executable.\n"
            "Leave blank to use whichever ffmpeg is found on your system PATH.\n"
            "Use Browse… to locate a specific version, or Setup… to download one automatically."
        )
        ffmpeg_edit_row = QHBoxLayout()
        ffmpeg_edit_row.addWidget(self.ffmpeg_path_edit, 1)
        ffmpeg_browse_btn = QPushButton("Browse…")
        ffmpeg_browse_btn.setToolTip("Open a file picker to locate the ffmpeg executable manually.")
        ffmpeg_browse_btn.clicked.connect(self._browse_ffmpeg)
        ffmpeg_edit_row.addWidget(ffmpeg_browse_btn)
        ffmpeg_layout.addLayout(ffmpeg_edit_row)

        ffmpeg_setup_btn = QPushButton("Setup…")
        ffmpeg_setup_btn.setToolTip(
            "Open the FFmpeg Setup wizard to auto-detect, verify, or download\n"
            "an official FFmpeg build for your platform."
        )
        ffmpeg_setup_btn.clicked.connect(self._run_ffmpeg_setup)
        ffmpeg_btn_row = QHBoxLayout()
        ffmpeg_btn_row.addWidget(ffmpeg_setup_btn)
        ffmpeg_btn_row.addStretch()
        ffmpeg_layout.addLayout(ffmpeg_btn_row)

        ffmpeg_layout.addWidget(QLabel("FFprobe executable:"))
        self.ffprobe_path_edit = QLineEdit()
        self.ffprobe_path_edit.setPlaceholderText("Auto-detected from system PATH (leave blank to use system default)")
        self.ffprobe_path_edit.setToolTip(
            "Path to the ffprobe executable (bundled with FFmpeg).\n"
            "Usually in the same directory as ffmpeg. Leave blank to auto-detect."
        )
        ffprobe_row = QHBoxLayout()
        ffprobe_row.addWidget(self.ffprobe_path_edit, 1)
        ffprobe_browse = QPushButton("Browse…")
        ffprobe_browse.setToolTip("Open a file picker to locate the ffprobe executable manually.")
        ffprobe_browse.clicked.connect(self._browse_ffprobe)
        ffprobe_row.addWidget(ffprobe_browse)
        ffmpeg_layout.addLayout(ffprobe_row)

        layout.addWidget(ffmpeg_group)

        # Whisper paths
        whisper_group = QGroupBox("Whisper AI")
        whisper_group.setToolTip(
            "Whisper AI is used for local, offline subtitle generation by transcribing audio.\n"
            "Models are large files downloaded on demand."
        )
        whisper_layout = QVBoxLayout(whisper_group)

        whisper_layout.addWidget(QLabel("Downloaded models directory (read-only):"))
        self.whisper_path_edit = QLineEdit()
        self.whisper_path_edit.setReadOnly(True)
        self.whisper_path_edit.setText(str(get_base_dir() / "models"))
        self.whisper_path_edit.setToolTip("Location where Whisper model files are stored after download.")
        whisper_edit_row = QHBoxLayout()
        whisper_edit_row.addWidget(self.whisper_path_edit, 1)
        whisper_layout.addLayout(whisper_edit_row)

        whisper_setup_btn = QPushButton("Setup Whisper…")
        whisper_setup_btn.setToolTip(
            "Open the Whisper Setup dialog to install Whisper AI, download model files,\n"
            "and check which models are already available."
        )
        whisper_setup_btn.clicked.connect(self._run_whisper_setup)
        whisper_btn_row = QHBoxLayout()
        whisper_btn_row.addWidget(whisper_setup_btn)
        whisper_btn_row.addStretch()
        whisper_layout.addLayout(whisper_btn_row)

        layout.addWidget(whisper_group)

        # Data directories
        dirs_group = QGroupBox("Data Directories")
        dirs_group.setToolTip(
            "Locations used by EncodeForge to store settings, logs, and cached data."
        )
        dirs_layout = QVBoxLayout(dirs_group)

        dirs_layout.addWidget(QLabel("Application base directory:"))
        base_dir_edit = QLineEdit()
        base_dir_edit.setReadOnly(True)
        base_dir_edit.setText(str(get_base_dir()))
        base_dir_edit.setToolTip(
            "Root directory where EncodeForge stores its settings, logs, and downloaded models."
        )
        dirs_layout.addWidget(base_dir_edit)

        open_base_btn = QPushButton("Open in File Manager")
        open_base_btn.setToolTip("Open the base directory in your system's file manager.")
        open_base_btn.clicked.connect(lambda: self._open_directory(get_base_dir()))
        dirs_btn_row = QHBoxLayout()
        dirs_btn_row.addWidget(open_base_btn)
        dirs_btn_row.addStretch()
        dirs_layout.addLayout(dirs_btn_row)

        layout.addWidget(dirs_group)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  Advanced tab
    # ------------------------------------------------------------------ #
    def _create_advanced_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(_hint(
            "These settings are for advanced users. Incorrect values may affect performance or stability."
        ))

        # Performance settings
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)

        self.max_threads_spin = QSpinBox()
        self.max_threads_spin.setRange(1, 32)
        self.max_threads_spin.setValue(4)
        self.max_threads_spin.setToolTip(
            "Maximum number of encoding jobs that can run in parallel.\n\n"
            "Higher values speed up batch processing but increase CPU and memory load.\n"
            "Recommended: 1–2 for CPU-heavy encodes, or your CPU's physical core count\n"
            "for lighter jobs. GPU encoding (NVENC/AMF/QSV) is less affected by this."
        )
        perf_layout.addRow("Max Parallel Jobs:", self.max_threads_spin)
        perf_layout.addRow("", _hint(
            "Recommended: match your CPU core count. High values can cause slowdowns."
        ))

        layout.addWidget(perf_group)

        # History settings
        history_group = QGroupBox("History")
        history_layout = QFormLayout(history_group)

        self.recent_files_spin = QSpinBox()
        self.recent_files_spin.setRange(0, 50)
        self.recent_files_spin.setValue(10)
        self.recent_files_spin.setToolTip(
            "Number of recently processed files kept in the history list.\n"
            "Set to 0 to disable recent file tracking entirely."
        )
        history_layout.addRow("Recent Files Limit:", self.recent_files_spin)

        layout.addWidget(history_group)

        # Logging settings
        log_group = QGroupBox("Logging")
        log_layout = QFormLayout(log_group)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setToolTip(
            "Verbosity of messages written to the log file.\n\n"
            "DEBUG   — Everything, including internal details. Use for troubleshooting.\n"
            "INFO    — Normal operational messages (recommended).\n"
            "WARNING — Only potential problems and unusual events.\n"
            "ERROR   — Only failures and errors."
        )
        log_layout.addRow("Log Level:", self.log_level_combo)

        layout.addWidget(log_group)

        # Extra FFmpeg arguments
        ff_extra = QGroupBox("Extra FFmpeg Arguments")
        ff_extra.setToolTip(
            "Raw FFmpeg command-line arguments appended to every encode command.\n"
            "For expert users who need fine-grained control not exposed in the UI."
        )
        ff_extra_layout = QVBoxLayout(ff_extra)
        ff_extra_layout.addWidget(_hint(
            "Arguments are appended verbatim to the FFmpeg command. "
            "Incorrect syntax will cause encodes to fail. Leave blank unless you know what you're doing."
        ))
        self.ffmpeg_extra_edit = QTextEdit()
        self.ffmpeg_extra_edit.setPlaceholderText(
            "e.g.  -map_metadata 0  -movflags +faststart  -vf 'scale=1920:-2'"
        )
        self.ffmpeg_extra_edit.setToolTip(
            "Additional FFmpeg flags and options appended to every encode command.\n"
            "Use standard FFmpeg syntax. Separate multiple arguments with spaces."
        )
        self.ffmpeg_extra_edit.setMaximumHeight(100)
        ff_extra_layout.addWidget(self.ffmpeg_extra_edit)
        layout.addWidget(ff_extra)

        layout.addStretch()
        return widget

    # ------------------------------------------------------------------ #
    #  Load / Save
    # ------------------------------------------------------------------ #
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
        # Whisper model combo now has size info — match by prefix
        whisper_model = self.settings.subtitle.whisper_model
        for i in range(self.whisper_model_combo.count()):
            if self.whisper_model_combo.itemText(i).startswith(whisper_model):
                self.whisper_model_combo.setCurrentIndex(i)
                break
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
        self.ffprobe_path_edit.setText(self.settings.application.ffprobe_path)

        # Advanced
        self.max_threads_spin.setValue(self.settings.application.max_threads)
        self.log_level_combo.setCurrentText(self.settings.application.log_level)
        self.recent_files_spin.setValue(self.settings.application.recent_files_limit)
        c = self.settings.conversion
        self.ffmpeg_extra_edit.setPlainText(c.additional_ffmpeg_args)

        self.tmdb_key_edit.setText(c.tmdb_api_key)
        self.tvdb_key_edit.setText(c.tvdb_api_key)
        self.omdb_key_edit.setText(c.omdb_api_key)
        self.trakt_key_edit.setText(c.trakt_api_key)
        self.fanart_key_edit.setText(c.fanart_api_key)
        self.anidb_key_edit.setText(c.anidb_api_key)
        self.os_user_edit.setText(c.opensubtitles_username)
        self.os_pass_edit.setText(c.opensubtitles_password)

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

        # Subtitle — extract just the model name (before the size annotation)
        self.settings.subtitle.mode = self.subtitle_mode_combo.currentText().lower()
        self.settings.subtitle.language = self.subtitle_language_combo.currentText()
        self.settings.subtitle.subtitle_format = self.subtitle_format_combo.currentText()
        self.settings.subtitle.encoding = self.subtitle_encoding_combo.currentText()
        self.settings.subtitle.fallback = self.subtitle_fallback_check.isChecked()
        self.settings.subtitle.sync = self.subtitle_sync_check.isChecked()
        self.settings.subtitle.translate = self.subtitle_translate_check.isChecked()
        raw_model = self.whisper_model_combo.currentText().split()[0]
        self.settings.subtitle.whisper_model = raw_model
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
        self.settings.application.ffprobe_path = self.ffprobe_path_edit.text()

        c = self.settings.conversion
        c.tmdb_api_key = self.tmdb_key_edit.text().strip()
        c.tvdb_api_key = self.tvdb_key_edit.text().strip()
        c.omdb_api_key = self.omdb_key_edit.text().strip()
        c.trakt_api_key = self.trakt_key_edit.text().strip()
        c.fanart_api_key = self.fanart_key_edit.text().strip()
        c.anidb_api_key = self.anidb_key_edit.text().strip()
        c.opensubtitles_username = self.os_user_edit.text().strip()
        c.opensubtitles_password = self.os_pass_edit.text().strip()
        c.additional_ffmpeg_args = self.ffmpeg_extra_edit.toPlainText().strip()

        # Advanced
        self.settings.application.max_threads = self.max_threads_spin.value()
        self.settings.application.log_level = self.log_level_combo.currentText()
        self.settings.application.recent_files_limit = self.recent_files_spin.value()

        self.settings.save()
        logger.info("Settings saved successfully")

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
            self.settings.conversion = ConversionSettings()

            self._load_settings()
            logger.info("Settings restored to defaults")

    # ------------------------------------------------------------------ #
    #  Helpers / dialogs
    # ------------------------------------------------------------------ #
    def _browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select FFmpeg Executable", "",
            "FFmpeg Executable (ffmpeg ffmpeg.exe);;All Files (*)"
        )
        if path:
            self.ffmpeg_path_edit.setText(path)

    def _browse_ffprobe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select FFprobe Executable", "",
            "FFprobe (ffprobe ffprobe.exe);;All Files (*)",
        )
        if path:
            self.ffprobe_path_edit.setText(path)

    def _run_ffmpeg_setup(self):
        from app.dialogs import FFmpegSetupDialog
        dialog = FFmpegSetupDialog(self, required=False)
        if dialog.exec():
            self.ffmpeg_path_edit.setText(self.settings.application.ffmpeg_path)

    def _run_whisper_setup(self):
        from app.dialogs.whisper_setup_dialog import WhisperSetupDialog
        dlg = WhisperSetupDialog(self)
        dlg.exec()

    def _show_pattern_help(self):
        help_text = """
<h3>Renaming Pattern Help</h3>

<p>Build a filename template using the placeholders below. EncodeForge will
replace each <code>{placeholder}</code> with the real value fetched from
the selected metadata provider.</p>

<p><b>Available placeholders:</b></p>
<table cellpadding="4">
<tr><td><code>{title}</code></td><td>Media title (e.g. <i>Breaking Bad</i>)</td></tr>
<tr><td><code>{season}</code></td><td>Season number with leading zero (e.g. <i>S01</i>)</td></tr>
<tr><td><code>{episode}</code></td><td>Episode number with leading zero (e.g. <i>E05</i>)</td></tr>
<tr><td><code>{year}</code></td><td>Release year (e.g. <i>2008</i>)</td></tr>
<tr><td><code>{quality}</code></td><td>Video resolution (e.g. <i>1080p</i>, <i>720p</i>)</td></tr>
<tr><td><code>{codec}</code></td><td>Video codec short name (e.g. <i>h264</i>, <i>hevc</i>)</td></tr>
<tr><td><code>{audio}</code></td><td>Audio codec short name (e.g. <i>AAC</i>, <i>AC3</i>)</td></tr>
</table>

<p><b>Examples:</b></p>
<ul>
  <li><code>{title} - {season}{episode} - {quality}</code>
      &nbsp;→&nbsp; <i>Breaking Bad - S01E05 - 1080p</i></li>
  <li><code>{title} ({year})</code>
      &nbsp;→&nbsp; <i>Inception (2010)</i></li>
  <li><code>{title}.{season}{episode}.{quality}.{codec}</code>
      &nbsp;→&nbsp; <i>Breaking.Bad.S01E05.1080p.h264</i></li>
</ul>
"""
        QMessageBox.information(self, "Pattern Help", help_text)

    def _open_directory(self, path: Path):
        import subprocess
        import sys
        if sys.platform == "win32":
            subprocess.run(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])


class SettingsDialog(QDialog):
    """Modal settings window wrapping SettingsPanel (same content as the inline Settings tab)."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings - EncodeForge")
        self.setMinimumSize(560, 520)
        layout = QVBoxLayout(self)
        self.panel = SettingsPanel(self, show_action_bar=False)
        self.panel.settings_changed.connect(self.settings_changed.emit)
        layout.addWidget(self.panel)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        restore_btn = QPushButton("Restore Defaults")
        restore_btn.setToolTip("Reset every setting back to its factory default value.")
        restore_btn.clicked.connect(self.panel.restore_defaults)
        button_layout.addWidget(restore_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setToolTip("Discard unsaved changes and close this dialog.")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        apply_btn = QPushButton("Apply")
        apply_btn.setToolTip("Save changes without closing the dialog.")
        apply_btn.clicked.connect(lambda: self.panel.save_to_disk(notify=True))
        button_layout.addWidget(apply_btn)
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.setToolTip("Save changes and close the dialog.")
        ok_btn.clicked.connect(self._accept_ok)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)
        self.panel.begin_session()

    def _accept_ok(self) -> None:
        self.panel.save_to_disk(notify=False)
        self.accept()

    def reject(self) -> None:
        self.panel.revert_unsaved()
        super().reject()
