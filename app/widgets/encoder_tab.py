"""
EncodeForge Encoder Tab
File list, settings panel, and queue management for video encoding
"""

import logging
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import qtawesome as qta
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.handlers.models import ConversionSettings
from core.profile_manager import ProfileManager

from app.widgets.custom_widgets import (
    AutoResizeTable,
    GlassmorphicButton,
    GlassmorphicCard,
    StyledCheckBox,
    StyledComboBox,
    StyledLabel,
    StyledSpinBox,
)
from utils.notifications import get_notification_manager
from utils.settings_manager import get_settings_manager
from utils.workers import EncoderWorker, merge_encoder_ui_into_conversion_settings

logger = logging.getLogger(__name__)


class EncoderTab(QWidget):
    """
    Main encoder tab containing file list and settings panel.
    
    Signals:
        encode_started: Emitted when encoding begins
        encode_progress: Emitted with (file, current, total, message) during encoding
        encode_completed: Emitted when encoding completes
        encode_error: Emitted with (file, error_message) on error
    """
    
    encode_started = Signal(str)  # file path
    encode_progress = Signal(str, int, int, str)  # file, current, total, message
    encode_completed = Signal(str)  # file path
    encode_error = Signal(str, str)  # file path, error message
    
    def __init__(self, thread_pool: QThreadPool, parent=None):
        """
        Initialize encoder tab.
        
        Args:
            thread_pool: QThreadPool for parallel processing
            parent: Parent widget
        """
        super().__init__(parent)
        self.thread_pool = thread_pool
        self.notifier = get_notification_manager()
        self._profile_mgr = ProfileManager()
        self.active_workers: Dict[str, EncoderWorker] = {}
        self._mp4_subtitle_warned = False
        self._splitter_initialized = False

        self._setup_ui()
        self._connect_signals()
        self._apply_saved_encoder_defaults()

    def _configured_hw_backend(self) -> str:
        """
        Read the hardware-acceleration backend chosen in Settings.

        Returns the combo's stored value ("None", "NVENC (NVIDIA)", …), or
        "Auto" if it could not be read — in which case the encoder picks
        whichever backend the machine actually supports.
        """
        try:
            return get_settings_manager().encoder.hw_accel or "Auto"
        except Exception as e:
            logger.debug(f"Could not read hardware acceleration setting: {e}")
            return "Auto"

    def _apply_saved_encoder_defaults(self):
        try:
            s = get_settings_manager().encoder
            self.format_combo.setCurrentText(s.container)
            self.codec_combo.setCurrentText(s.codec)
            self.preset_combo.setCurrentText(s.preset)
            for i in range(self.quality_combo.count()):
                t = self.quality_combo.itemText(i)
                if f"CQ {s.crf}" in t:
                    self.quality_combo.setCurrentText(t)
                    break
            self.hw_accel_check.setChecked(s.hw_accel != "None")
            ac = s.audio_codec
            br = s.audio_bitrate
            if ac == "AAC" and br == 192:
                self.audio_handling_combo.setCurrentText("AAC 192k")
            elif ac == "AAC" and br == 320:
                self.audio_handling_combo.setCurrentText("AAC 320k")
            elif ac == "AC3":
                self.audio_handling_combo.setCurrentText("AC3")
            elif ac == "Copy":
                self.audio_handling_combo.setCurrentText("Copy")
            else:
                self.audio_handling_combo.setCurrentText("Copy")
        except Exception as e:
            logger.debug("Encoder defaults not applied: %s", e)

    def showEvent(self, event):
        super().showEvent(event)
        if self._splitter_initialized:
            return
        total = self.width()
        if total > 0 and hasattr(self, "_main_splitter"):
            self._main_splitter.setSizes([int(total * 0.70), int(total * 0.30)])
            self._splitter_initialized = True

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main splitter: Left (tables) | Right (file info)
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Settings + Tables
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top: Video Settings
        self._setup_video_settings(left_layout)
        
        # Below: Tables splitter (Queued | Processing | Completed)
        self._setup_tables_area(left_layout)
        
        self._main_splitter.addWidget(left_widget)

        # Right side: File Info sidebar
        self._setup_file_info_sidebar(self._main_splitter)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 1)

        layout.addWidget(self._main_splitter)
        
        logger.debug("Encoder tab initialized - using base glassmorphism theme")
    
    def _setup_video_settings(self, parent_layout):
        """Set up the top video settings panel with grid + compact control rows."""
        settings_widget = QWidget()
        settings_widget.setObjectName("encoder_toolbar")
        settings_main_layout = QVBoxLayout(settings_widget)
        settings_main_layout.setContentsMargins(10, 5, 10, 5)
        settings_main_layout.setSpacing(6)

        enc_grid = QGridLayout()
        enc_grid.setHorizontalSpacing(12)
        enc_grid.setVerticalSpacing(4)
        enc_grid.setContentsMargins(0, 0, 0, 0)

        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        format_label = StyledLabel("Format:")
        format_label.setAlignment(align_right)
        self.format_combo = StyledComboBox()
        self.format_combo.addItems(["MP4", "MKV", "WebM", "AVI", "MOV"])
        self.format_combo.setMinimumContentsLength(5)
        self.format_combo.setMinimumWidth(72)

        codec_label = StyledLabel("Codec:")
        codec_label.setAlignment(align_right)
        self.codec_combo = StyledComboBox()
        self.codec_combo.addItems(["H.264", "H.265/HEVC", "AV1", "VP9", "Copy", "Auto"])
        self.codec_combo.setCurrentText("Auto")
        self.codec_combo.setMinimumContentsLength(12)
        self.codec_combo.setMinimumWidth(100)

        quality_label = StyledLabel("Quality:")
        quality_label.setAlignment(align_right)
        self.quality_combo = StyledComboBox()
        self.quality_combo.addItems(["High (CQ 18)", "Medium (CQ 23)", "Low (CQ 28)", "Very Low (CQ 33)"])
        self.quality_combo.setCurrentText("Medium (CQ 23)")
        self.quality_combo.setMinimumContentsLength(18)
        self.quality_combo.setMinimumWidth(115)

        preset_label = StyledLabel("Preset:")
        preset_label.setAlignment(align_right)
        self.preset_combo = StyledComboBox()
        self.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_combo.setCurrentText("medium")
        self.preset_combo.setMinimumContentsLength(10)
        self.preset_combo.setMinimumWidth(85)

        enc_grid.addWidget(format_label, 0, 0)
        enc_grid.addWidget(self.format_combo, 0, 1)
        enc_grid.addWidget(codec_label, 0, 2)
        enc_grid.addWidget(self.codec_combo, 0, 3)
        enc_grid.addWidget(quality_label, 1, 0)
        enc_grid.addWidget(self.quality_combo, 1, 1)
        enc_grid.addWidget(preset_label, 1, 2)
        enc_grid.addWidget(self.preset_combo, 1, 3)
        enc_grid.setColumnStretch(1, 1)
        enc_grid.setColumnStretch(3, 1)
        settings_main_layout.addLayout(enc_grid)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)
        profile_label = StyledLabel("Profile:")
        profile_label.setAlignment(align_right)
        self.profile_combo = StyledComboBox()
        self.profile_combo.setMinimumContentsLength(20)
        self.profile_combo.setMinimumWidth(160)
        load_profile_btn = GlassmorphicButton("Load", qta.icon("fa5s.folder-open"))
        load_profile_btn.setToolTip("Apply the selected profile to these encoder controls")
        save_profile_btn = GlassmorphicButton("Save as…", qta.icon("fa5s.save"))
        save_profile_btn.setToolTip("Save current encoder options as a custom profile (JSON)")
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(load_profile_btn)
        profile_row.addWidget(save_profile_btn)
        settings_main_layout.addLayout(profile_row)
        load_profile_btn.clicked.connect(self._load_selected_profile)
        save_profile_btn.clicked.connect(self._save_profile_as)
        self._refresh_profile_combo()

        checks_row = QHBoxLayout()
        checks_row.setSpacing(12)
        self.hw_accel_check = StyledCheckBox("HW Accel")
        self.hw_accel_check.setChecked(True)
        self.normalize_audio_check = StyledCheckBox("Normalize")
        self.delete_original_check = StyledCheckBox("Delete Source")
        self.delete_original_check.setChecked(False)
        checks_row.addWidget(self.hw_accel_check)
        checks_row.addWidget(self.normalize_audio_check)
        checks_row.addWidget(self.delete_original_check)
        checks_row.addStretch()
        settings_main_layout.addLayout(checks_row)

        io_row = QHBoxLayout()
        io_row.setSpacing(12)
        subtitle_label = StyledLabel("Subtitles:")
        subtitle_label.setAlignment(align_right)
        self.subtitle_handling_combo = StyledComboBox()
        self.subtitle_handling_combo.addItems(["Keep/Passthrough", "Convert to SRT", "Embed", "Burn-in", "Skip"])
        self.subtitle_handling_combo.setMinimumContentsLength(18)
        self.subtitle_handling_combo.setMinimumWidth(115)
        audio_label = StyledLabel("Audio:")
        audio_label.setAlignment(align_right)
        self.audio_handling_combo = StyledComboBox()
        self.audio_handling_combo.addItems(["Copy", "AAC 192k", "AAC 320k", "AC3", "Normalize+Copy"])
        self.audio_handling_combo.setMinimumContentsLength(14)
        self.audio_handling_combo.setMinimumWidth(100)
        io_row.addWidget(subtitle_label)
        io_row.addWidget(self.subtitle_handling_combo, 1)
        io_row.addWidget(audio_label)
        io_row.addWidget(self.audio_handling_combo, 1)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setIcon(qta.icon("fa5s.stop"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumWidth(65)
        self.stop_btn.setProperty("danger", True)
        self.start_btn = QPushButton("Start Encoding")
        self.start_btn.setIcon(qta.icon("fa5s.play"))
        self.start_btn.setMinimumWidth(120)
        self.start_btn.setProperty("primary", True)
        io_row.addWidget(self.stop_btn)
        io_row.addWidget(self.start_btn)
        settings_main_layout.addLayout(io_row)

        parent_layout.addWidget(settings_widget)
    
    def _setup_tables_area(self, parent_layout):
        """Set up the single file table with all encoding states."""
        # Main table container
        table_group = GlassmorphicCard("Files")
        table_layout = table_group.content_layout()
        table_layout.setContentsMargins(0, 5, 0, 0)
        table_layout.setSpacing(8)
        
        # Single comprehensive table with custom widget
        self.files_table = AutoResizeTable()
        self.files_table.setColumns(
            headers=["#", "File Name", "Output", "Size", "New Size", "Progress", "ETA", "Status"],
            initial_widths=[40, 200, 120, 80, 80, 100, 70]  # Status column auto-stretches
        )
        
        # Additional table configuration
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        
        # Set compact row height
        self.files_table.verticalHeader().setDefaultSectionSize(22)
        
        # Enable context menu
        self.files_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_table.customContextMenuRequested.connect(self._show_context_menu)
        
        table_layout.addWidget(self.files_table, 1)  # Give table the stretch factor
        
        # Table control buttons using glassmorphic buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(8)
        
        self.add_files_btn = GlassmorphicButton("Add Files", qta.icon('fa5s.plus'))
        self.add_files_btn.clicked.connect(lambda: self._add_files())
        self.add_files_btn.setMinimumWidth(80)
        
        self.add_folder_btn = GlassmorphicButton("Add Folder", qta.icon('fa5s.folder-plus'))
        self.add_folder_btn.clicked.connect(lambda: self._add_folder())
        self.add_folder_btn.setMinimumWidth(85)
        
        self.remove_selected_btn = GlassmorphicButton("Remove Selected", qta.icon('fa5s.trash'))
        self.remove_selected_btn.clicked.connect(self._remove_selected_files)
        self.remove_selected_btn.setMinimumWidth(110)
        
        self.clear_completed_btn = GlassmorphicButton("Clear Completed", qta.icon('fa5s.broom'))
        self.clear_completed_btn.clicked.connect(self._clear_completed_files)
        self.clear_completed_btn.setMinimumWidth(110)

        self.queue_up_btn = GlassmorphicButton("Up", qta.icon("fa5s.arrow-up"))
        self.queue_up_btn.setToolTip("Move selected queued row up")
        self.queue_up_btn.clicked.connect(lambda: self._move_selected_queue(-1))
        self.queue_up_btn.setMinimumWidth(52)
        self.queue_down_btn = GlassmorphicButton("Down", qta.icon("fa5s.arrow-down"))
        self.queue_down_btn.setToolTip("Move selected queued row down")
        self.queue_down_btn.clicked.connect(lambda: self._move_selected_queue(1))
        self.queue_down_btn.setMinimumWidth(68)
        
        buttons_layout.addWidget(self.add_files_btn)
        buttons_layout.addWidget(self.add_folder_btn)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.remove_selected_btn)
        buttons_layout.addWidget(self.clear_completed_btn)
        buttons_layout.addSpacing(8)
        buttons_layout.addWidget(self.queue_up_btn)
        buttons_layout.addWidget(self.queue_down_btn)
        buttons_layout.addStretch()
        
        table_layout.addLayout(buttons_layout, 0)  # No stretch for buttons
        
        parent_layout.addWidget(table_group, 1)  # Give the whole group a stretch factor
    
    def _setup_file_info_sidebar(self, splitter):
        """Set up the file info sidebar on the right."""
        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)
        
        # Title
        title_label = StyledLabel("File Information")
        title_label.setProperty("heading", True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title_label)
        
        # Preview area
        preview_group = GlassmorphicCard("Preview")
        preview_layout = preview_group.content_layout()
        self.preview_label = StyledLabel("No file selected")
        self.preview_label.setObjectName("preview_label")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(120)
        preview_layout.addWidget(self.preview_label)
        sidebar_layout.addWidget(preview_group)
        
        # File Information Section
        file_group = GlassmorphicCard("File Details")
        file_layout = QFormLayout()
        file_layout.setSpacing(6)
        file_layout.setContentsMargins(8, 12, 8, 8)
        file_group.content_layout().addLayout(file_layout)
        
        self.name_label = StyledLabel("-")
        self.size_label = StyledLabel("-")
        self.duration_label = StyledLabel("-")
        self.path_label = StyledLabel("-")
        self.path_label.setObjectName("path_label")
        self.path_label.setWordWrap(True)
        
        file_layout.addRow("Name:", self.name_label)
        file_layout.addRow("Size:", self.size_label)
        file_layout.addRow("Duration:", self.duration_label)
        file_layout.addRow("Path:", self.path_label)
        
        sidebar_layout.addWidget(file_group)
        
        # Video Information Section
        video_group = GlassmorphicCard("Video Properties")
        video_layout = QFormLayout()
        video_layout.setSpacing(6)
        video_layout.setContentsMargins(8, 12, 8, 8)
        video_group.content_layout().addLayout(video_layout)
        
        self.codec_label = StyledLabel("-")
        self.resolution_label = StyledLabel("-")
        self.frame_rate_label = StyledLabel("-")
        self.bitrate_label = StyledLabel("-")
        
        video_layout.addRow("Codec:", self.codec_label)
        video_layout.addRow("Resolution:", self.resolution_label)
        video_layout.addRow("Frame Rate:", self.frame_rate_label)
        video_layout.addRow("Bitrate:", self.bitrate_label)
        
        sidebar_layout.addWidget(video_group)
        
        # Audio Information Section
        audio_group = GlassmorphicCard("Audio Properties")
        audio_layout = QFormLayout()
        audio_layout.setSpacing(6)
        audio_layout.setContentsMargins(8, 12, 8, 8)
        audio_group.content_layout().addLayout(audio_layout)
        
        self.audio_codec_label = StyledLabel("-")
        self.audio_channels_label = StyledLabel("-")
        self.sample_rate_label = StyledLabel("-")
        self.audio_bitrate_label = StyledLabel("-")
        
        audio_layout.addRow("Codec:", self.audio_codec_label)
        audio_layout.addRow("Channels:", self.audio_channels_label)
        audio_layout.addRow("Sample Rate:", self.sample_rate_label)
        audio_layout.addRow("Bitrate:", self.audio_bitrate_label)
        
        sidebar_layout.addWidget(audio_group)
        
        sidebar_layout.addStretch()
        
        splitter.addWidget(sidebar)
    
    def _connect_signals(self):
        """Connect widget signals to slots."""
        # Connect table signals
        self.files_table.itemSelectionChanged.connect(self._on_file_selected)
        # The context menu is already wired during table construction; connecting
        # it a second time made every right-click open the menu twice (nested
        # exec()), so dismissing one immediately showed another.

        # Button connections
        self.start_btn.clicked.connect(self._start_encoding)
        self.stop_btn.clicked.connect(self._stop_encoding)

        # MP4 subtitle warning
        self.format_combo.currentTextChanged.connect(self._check_mp4_subtitle_warning)
        self.subtitle_handling_combo.currentTextChanged.connect(self._check_mp4_subtitle_warning)

    def _check_mp4_subtitle_warning(self):
        """Show one-time warning about MP4 subtitle limitations."""
        if self._mp4_subtitle_warned:
            return
        fmt = self.format_combo.currentText()
        subtitle_mode = self.subtitle_handling_combo.currentText()
        if fmt == "MP4" and subtitle_mode != "Skip":
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self,
                "MP4 Subtitle Notice",
                "ASS/SSA styled subtitles will be converted to mov_text in MP4 containers.\n\n"
                "To preserve full subtitle formatting (fonts, positioning, styles), use MKV instead."
            )
            self._mp4_subtitle_warned = True
    
    def _is_video_file(self, file_path: Path) -> bool:
        """Check if file is a video file."""
        video_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', 
            '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'
        }
        return file_path.suffix.lower() in video_extensions
    
    def _add_file_to_table(self, file_path: Path):
        """Add file to the single files table."""
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return
        
        row = self.files_table.rowCount()
        self.files_table.insertRow(row)
        
        # Index
        self.files_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        
        # File name
        name_item = QTableWidgetItem(file_path.name)
        name_item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        self.files_table.setItem(row, 1, name_item)
        
        # Output (placeholder)
        self.files_table.setItem(row, 2, QTableWidgetItem(""))
        
        # File size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        self.files_table.setItem(row, 3, QTableWidgetItem(f"{size_mb:.2f} MB"))
        
        # New size (placeholder)
        self.files_table.setItem(row, 4, QTableWidgetItem("-"))
        
        # Progress (placeholder)
        self.files_table.setItem(row, 5, QTableWidgetItem("-"))
        
        # ETA (placeholder)
        self.files_table.setItem(row, 6, QTableWidgetItem("-"))
        
        # Status
        self.files_table.setItem(row, 7, QTableWidgetItem("Queued"))
        
        self.start_btn.setEnabled(True)
        logger.info(f"Added file to queue: {file_path.name}")
    
    def _add_folder_to_table(self, folder_path: Path):
        """Add all video files from folder to queue."""
        count = 0
        for file_path in folder_path.rglob("*"):
            if file_path.is_file() and self._is_video_file(file_path):
                self._add_file_to_table(file_path)
                count += 1
        logger.info(f"Added {count} files from {folder_path}")
    
    def _start_encoding(self):
        """Start encoding all queued files."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Find all queued files and start encoding them
        for row in range(self.files_table.rowCount()):
            status_item = self.files_table.item(row, 7)  # Status column
            if status_item and status_item.text() == "Queued":
                self._start_encoding_file(row)
    
    def _start_encoding_file(self, row: int):
        """Start encoding a file in the specified row."""
        # Get data from the table
        name_item = self.files_table.item(row, 1)
        if not name_item:
            return
        
        file_path = Path(name_item.data(Qt.ItemDataRole.UserRole))
        if not file_path:
            return
        
        # Update status to processing
        self.files_table.setItem(row, 7, QTableWidgetItem("Encoding..."))
        
        # Add progress bar to progress column
        progress = QProgressBar()
        progress.setValue(0)
        self.files_table.setCellWidget(row, 5, progress)
        
        # Update ETA
        self.files_table.setItem(row, 6, QTableWidgetItem("-"))
        
        # Start encoding
        self._encode_file(row, file_path)
    
    def _row_for_path(self, file_path: str) -> int:
        """
        Look up the current table row holding `file_path`.

        Rows shift whenever the user removes an entry mid-batch, so a row index
        captured when the encode started goes stale and updates land on the
        wrong file. The path stored in UserRole is the stable identity.

        Returns:
            The row index, or -1 if the file is no longer in the table.
        """
        for row in range(self.files_table.rowCount()):
            item = self.files_table.item(row, 1)
            if item and item.data(Qt.ItemDataRole.UserRole) == file_path:
                return row
        return -1

    def _encode_file(self, proc_row: int, file_path: Path):
        """Start encoding a single file."""
        # Generate output path
        output_path = self._generate_output_path(file_path)

        # Remember the path this job actually targets. Recomputing it later
        # would read the format combo as it is *then*, which the user may have
        # changed while the encode was running.
        name_item = self.files_table.item(proc_row, 1)
        if name_item:
            name_item.setData(Qt.ItemDataRole.UserRole + 1, str(output_path))

        # Get encoder settings
        settings = self._get_encoder_settings()

        # Create worker
        worker = EncoderWorker(file_path, output_path, settings)

        # Signals carry the file path, not the row index, and each handler
        # re-resolves the row at delivery time.
        path_str = str(file_path)
        worker.signals.started.connect(
            lambda: self._on_encode_started(self._row_for_path(path_str), path_str)
        )
        worker.signals.progress.connect(
            lambda cur, tot, msg: self._on_encode_progress(
                self._row_for_path(path_str), cur, tot, msg
            )
        )
        worker.signals.result.connect(
            lambda result: self._on_encode_completed(self._row_for_path(path_str), path_str)
        )
        worker.signals.error.connect(
            lambda error: self._on_encode_error(self._row_for_path(path_str), path_str, error)
        )

        # Track worker
        self.active_workers[str(file_path)] = worker
        
        # Start worker
        self.thread_pool.start(worker)
        logger.info(f"Started encoding: {file_path.name}")
    
    def _generate_output_path(self, input_path: Path) -> Path:
        """Generate output file path based on settings."""
        format_text = self.format_combo.currentText().lower()
        # Map format names to extensions
        format_map = {
            'mp4': 'mp4',
            'mkv': 'mkv',
            'webm': 'webm',
            'avi': 'avi',
            'mov': 'mov'
        }
        extension = format_map.get(format_text, 'mp4')
        output_name = f"{input_path.stem}_encoded.{extension}"
        return input_path.parent / output_name
    
    def _get_encoder_settings(self) -> Dict[str, Any]:
        """Get current encoder settings as dictionary."""
        subtitle_map = {
            'Keep/Passthrough': 'keep',
            'Convert to SRT': 'convert_to_srt',
            'Embed': 'embed',
            'Burn-in': 'burn_in',
            'Skip': 'skip'
        }
        audio_codec_map = {
            'Copy': 'copy',
            'AAC 192k': 'aac',
            'AAC 320k': 'aac',
            'AC3': 'ac3',
            'Normalize+Copy': 'copy'
        }
        audio_bitrate_map = {
            'AAC 192k': '192k',
            'AAC 320k': '320k',
        }
        audio_text = self.audio_handling_combo.currentText()
        return {
            'format': self.format_combo.currentText(),
            'codec': self.codec_combo.currentText(),
            'quality': self.quality_combo.currentText(),
            'preset': self.preset_combo.currentText(),
            'hw_accel': self.hw_accel_check.isChecked(),
            # Which backend the user picked in Settings. Without this the worker
            # has no way to tell NVENC from AMF/QSV/VideoToolbox and defaults
            # every machine to NVENC.
            'hw_accel_backend': self._configured_hw_backend(),
            'normalize_audio': self.normalize_audio_check.isChecked() or audio_text == 'Normalize+Copy',
            'container': self.format_combo.currentText().lower(),
            'subtitle_handling': subtitle_map.get(self.subtitle_handling_combo.currentText(), 'keep'),
            'delete_original': self.delete_original_check.isChecked(),
            'audio_codec': audio_codec_map.get(audio_text, 'copy'),
            'audio_bitrate': audio_bitrate_map.get(audio_text),
        }

    def _refresh_profile_combo(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("(select profile)")
        for name in self._profile_mgr.list_profiles():
            self.profile_combo.addItem(name)
        self.profile_combo.blockSignals(False)

    def _load_selected_profile(self) -> None:
        name = self.profile_combo.currentText()
        if not name or name.startswith("("):
            return
        cs = self._profile_mgr.load_profile(name)
        if cs is None:
            return
        self._apply_conversion_settings_to_ui(cs)

    def _save_profile_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Save encoding profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        base = deepcopy(get_settings_manager().get_merged_conversion_settings())
        merged = merge_encoder_ui_into_conversion_settings(
            base, self._get_encoder_settings()
        )
        if self._profile_mgr.save_profile(name, merged):
            self._refresh_profile_combo()
            idx = self.profile_combo.findText(name)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)

    def _apply_conversion_settings_to_ui(self, cs: ConversionSettings) -> None:
        fmt_map = {"mp4": "MP4", "mkv": "MKV", "webm": "WebM", "avi": "AVI", "mov": "MOV"}
        self.format_combo.setCurrentText(
            fmt_map.get((cs.output_format or "mp4").lower(), "MP4")
        )
        if cs.use_nvenc:
            if "hevc" in (cs.nvenc_codec or "").lower():
                self.codec_combo.setCurrentText("H.265/HEVC")
            else:
                self.codec_combo.setCurrentText("H.264")
        else:
            rev = {
                "libx264": "H.264",
                "libx265": "H.265/HEVC",
                "libaom-av1": "AV1",
                "libvpx-vp9": "VP9",
                "copy": "Copy",
            }
            self.codec_combo.setCurrentText(rev.get(cs.video_codec_fallback, "Auto"))
        nv_map = {
            "p1": "ultrafast",
            "p2": "superfast",
            "p3": "veryfast",
            "p4": "faster",
            "p5": "fast",
            "p6": "medium",
            "p7": "slow",
        }
        if cs.use_nvenc and cs.nvenc_preset:
            preset = nv_map.get(str(cs.nvenc_preset).lower(), cs.video_preset)
        else:
            preset = cs.video_preset
        pidx = self.preset_combo.findText(preset)
        if pidx >= 0:
            self.preset_combo.setCurrentIndex(pidx)
        cq = cs.nvenc_cq if cs.use_nvenc else cs.video_crf
        quality_options = [
            (18, "High (CQ 18)"),
            (23, "Medium (CQ 23)"),
            (28, "Low (CQ 28)"),
            (33, "Very Low (CQ 33)"),
        ]
        best = min(quality_options, key=lambda x: abs(x[0] - cq))
        self.quality_combo.setCurrentText(best[1])
        self.hw_accel_check.setChecked(
            bool(cs.use_nvenc or cs.use_amf or cs.use_qsv or cs.use_videotoolbox)
        )
        sh_reverse = {
            "keep": "Keep/Passthrough",
            "convert_to_srt": "Convert to SRT",
            "embed": "Embed",
            "burn_in": "Burn-in",
            "skip": "Skip",
        }
        if cs.convert_subtitles:
            self.subtitle_handling_combo.setCurrentText(
                sh_reverse.get(cs.subtitle_handling, "Keep/Passthrough")
            )
        else:
            self.subtitle_handling_combo.setCurrentText("Skip")
        ac = (cs.audio_codec or "copy").lower()
        if ac == "copy":
            self.audio_handling_combo.setCurrentText("Copy")
        elif ac == "aac":
            br = str(cs.audio_bitrate or "192k").lower().replace("k", "")
            if br == "320":
                self.audio_handling_combo.setCurrentText("AAC 320k")
            else:
                self.audio_handling_combo.setCurrentText("AAC 192k")
        elif ac == "ac3":
            self.audio_handling_combo.setCurrentText("AC3")
        else:
            self.audio_handling_combo.setCurrentText("Copy")
        self.normalize_audio_check.setChecked(cs.normalize_audio)
        self.delete_original_check.setChecked(cs.delete_original)

    def _renumber_queue_indices(self) -> None:
        for row in range(self.files_table.rowCount()):
            cell = self.files_table.item(row, 0)
            if cell:
                cell.setText(str(row + 1))

    def _swap_queue_rows(self, row_a: int, row_b: int) -> None:
        for col in range(self.files_table.columnCount()):
            a = self.files_table.takeItem(row_a, col)
            b = self.files_table.takeItem(row_b, col)
            self.files_table.setItem(row_a, col, b)
            self.files_table.setItem(row_b, col, a)
        wa = self.files_table.cellWidget(row_a, 5)
        wb = self.files_table.cellWidget(row_b, 5)
        self.files_table.removeCellWidget(row_a, 5)
        self.files_table.removeCellWidget(row_b, 5)
        if wb is not None:
            self.files_table.setCellWidget(row_a, 5, wb)
        if wa is not None:
            self.files_table.setCellWidget(row_b, 5, wa)

    def _row_queue_status(self, row: int) -> str:
        it = self.files_table.item(row, 7)
        return (it.text() if it else "") or ""

    def _move_selected_queue(self, delta: int) -> None:
        rows = sorted({ix.row() for ix in self.files_table.selectedIndexes()})
        if len(rows) != 1:
            return
        row = rows[0]
        if self._row_queue_status(row) != "Queued":
            return
        other = row + delta
        if other < 0 or other >= self.files_table.rowCount():
            return
        if self._row_queue_status(other) != "Queued":
            return
        self._swap_queue_rows(row, other)
        self._renumber_queue_indices()
        self.files_table.selectRow(other)
    
    def _on_encode_started(self, row: int, file_path: str):
        """Handle encoding started event."""
        self.encode_started.emit(file_path)
        logger.debug(f"Encode started for row {row}: {file_path}")
    
    def _on_encode_progress(self, proc_row: int, current: int, total: int, message: str):
        """Handle encoding progress update."""
        if proc_row < 0:
            return  # Row was removed from the queue while encoding
        # Parse ETA from message if encoded
        eta = "-"
        if "|eta:" in message:
            parts = message.split("|eta:", 1)
            message = parts[0]
            eta = parts[1]

        progress_bar = self.files_table.cellWidget(proc_row, 5)
        if progress_bar and isinstance(progress_bar, QProgressBar):
            if total > 0:
                progress_bar.setValue(int((current / total) * 100))

        # Update status
        status_item = self.files_table.item(proc_row, 7)
        if status_item and total > 0:
            status_item.setText(f"Encoding... {int((current / total) * 100)}%")

        # Update ETA column
        eta_item = self.files_table.item(proc_row, 6)
        if eta_item:
            eta_item.setText(eta)

        file_item = self.files_table.item(proc_row, 1)
        if file_item:
            file_path = file_item.data(Qt.ItemDataRole.UserRole)
            self.encode_progress.emit(file_path, current, total, message)
    
    def _on_encode_completed(self, proc_row: int, file_path: str):
        """Handle encoding completed event."""
        # A result can still arrive after the user pressed Stop; reporting the
        # job as "Completed" would label a truncated partial file as good.
        worker = self.active_workers.get(file_path)
        cancelled = worker is not None and getattr(worker, "_should_stop", False)

        if proc_row >= 0:
            label = "Cancelled" if cancelled else "Completed"
            colour = QColor(148, 163, 184) if cancelled else QColor(34, 197, 94)
            self.files_table.setItem(proc_row, 7, QTableWidgetItem(label))
            status_item = self.files_table.item(proc_row, 7)
            if status_item:
                status_item.setForeground(colour)

            # Update progress to 100%
            progress_bar = self.files_table.cellWidget(proc_row, 5)
            if progress_bar and isinstance(progress_bar, QProgressBar) and not cancelled:
                progress_bar.setValue(100)

            # Update ETA to completion time
            self.files_table.setItem(proc_row, 6, QTableWidgetItem("00:00"))

            # Use the output path recorded when this job started, so a format
            # change mid-encode does not leave the size column blank.
            name_item = self.files_table.item(proc_row, 1)
            recorded = name_item.data(Qt.ItemDataRole.UserRole + 1) if name_item else None
            output_path = Path(recorded) if recorded else self._generate_output_path(Path(file_path))
            if output_path.exists() and not cancelled:
                new_size = output_path.stat().st_size / (1024 * 1024)  # MB
                self.files_table.setItem(proc_row, 4, QTableWidgetItem(f"{new_size:.2f} MB"))

        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]

        if cancelled:
            logger.info(f"Encode cancelled: {file_path}")
            self._check_queue_complete()
            return

        self.encode_completed.emit(file_path)
        logger.info(f"Encode completed: {file_path}")
        
        # Check if all done
        self._check_queue_complete()
    

    
    def _on_encode_error(self, proc_row: int, file_path: str, error: tuple):
        """Handle encoding error event."""
        exc_type, value, tb = error
        error_msg = str(value)

        if proc_row >= 0:
            # Update status to error
            self.files_table.setItem(proc_row, 7, QTableWidgetItem(f"Error: {error_msg}"))
            status_item = self.files_table.item(proc_row, 7)
            if status_item:
                status_item.setForeground(QColor(239, 68, 68))  # #ef4444 error red

            # Remove progress bar
            self.files_table.removeCellWidget(proc_row, 5)

        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        self.encode_error.emit(file_path, error_msg)
        logger.error(f"Encode error for {file_path}: {error_msg}")
        
        # Check if all done
        self._check_queue_complete()
    
    def _stop_encoding(self):
        """Stop all active encoding tasks and mark their rows as cancelled."""
        stopped_paths = list(self.active_workers.keys())

        for file_path, worker in list(self.active_workers.items()):
            try:
                worker.stop()
            except RuntimeError as e:
                # The underlying QRunnable auto-deletes as soon as run() returns,
                # so a job that finished microseconds before Stop was pressed may
                # already be gone.
                logger.debug(f"Worker for {file_path} already finished: {e}")

        # Leave no row reading "Encoding…" forever.
        for file_path in stopped_paths:
            row = self._row_for_path(file_path)
            if row < 0:
                continue
            status_item = self.files_table.item(row, 7)
            if status_item and status_item.text().startswith(("Encoding", "Queued")):
                self.files_table.setItem(row, 7, QTableWidgetItem("Cancelled"))
                cancelled_item = self.files_table.item(row, 7)
                if cancelled_item:
                    cancelled_item.setForeground(QColor(148, 163, 184))
            self.files_table.removeCellWidget(row, 5)
            self.files_table.setItem(row, 6, QTableWidgetItem("-"))

        self.active_workers.clear()
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        logger.info(f"Stopped {len(stopped_paths)} encoding task(s)")
    
    def _check_queue_complete(self):
        """Check if all encoding tasks are complete."""
        if not self.active_workers:
            self.stop_btn.setEnabled(False)
            self.start_btn.setEnabled(True)
            
            # Count completed files
            completed_count = 0
            for row in range(self.files_table.rowCount()):
                status_item = self.files_table.item(row, 7)
                if status_item and status_item.text() == "Completed":
                    completed_count += 1
            
            if completed_count > 0:
                logger.info(f"Batch encoding complete: {completed_count} files")
    
    def _remove_selected_queued(self):
        """Remove selected rows from files table that are in queued status."""
        selected_rows = sorted(
            set(index.row() for index in self.files_table.selectedIndexes()),
            reverse=True
        )
        for row in selected_rows:
            status_item = self.files_table.item(row, 7)
            if status_item and status_item.text() == "Queued":
                self.files_table.removeRow(row)
        
        # Check if any queued files remain
        has_queued = False
        for row in range(self.files_table.rowCount()):
            status_item = self.files_table.item(row, 7)
            if status_item and status_item.text() == "Queued":
                has_queued = True
                break
        
        if not has_queued:
            self.start_btn.setEnabled(False)
    
    def _clear_queued(self):
        """Clear all queued files from the table."""
        rows_to_remove = []
        for row in range(self.files_table.rowCount()):
            status_item = self.files_table.item(row, 7)
            if status_item and status_item.text() == "Queued":
                rows_to_remove.append(row)
        
        # Remove in reverse order to maintain indices
        for row in sorted(rows_to_remove, reverse=True):
            self.files_table.removeRow(row)
        
        self.start_btn.setEnabled(False)
    
    def _cancel_selected_processing(self):
        """Cancel selected processing tasks."""
        selected_rows = sorted(
            set(index.row() for index in self.files_table.selectedIndexes()),
            reverse=True
        )
        for row in selected_rows:
            status_item = self.files_table.item(row, 7)
            if status_item and "Encoding" in status_item.text():
                name_item = self.files_table.item(row, 1)
                if name_item:
                    file_path = name_item.data(Qt.ItemDataRole.UserRole)
                    if file_path in self.active_workers:
                        self.active_workers[file_path].stop()
                        del self.active_workers[file_path]
                
                # Update status to cancelled
                self.files_table.setItem(row, 7, QTableWidgetItem("Cancelled"))
                # Remove progress bar
                self.files_table.removeCellWidget(row, 5)
    
    def _cancel_all_processing(self):
        """Cancel all processing tasks."""
        self._stop_encoding()
        
        # Update status for all encoding files
        for row in range(self.files_table.rowCount()):
            status_item = self.files_table.item(row, 7)
            if status_item and "Encoding" in status_item.text():
                self.files_table.setItem(row, 7, QTableWidgetItem("Cancelled"))
                self.files_table.removeCellWidget(row, 5)
    
    def _clear_completed(self):
        """Clear all completed files from the table."""
        rows_to_remove = []
        for row in range(self.files_table.rowCount()):
            status_item = self.files_table.item(row, 7)
            if status_item and status_item.text() == "Completed":
                rows_to_remove.append(row)
        
        # Remove in reverse order to maintain indices
        for row in sorted(rows_to_remove, reverse=True):
            self.files_table.removeRow(row)
    
    def _on_file_selected(self):
        """Handle file selection in the table."""
        # Get selected file path
        file_path = None
        
        selected_items = self.files_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            name_item = self.files_table.item(row, 1)
            if name_item:
                file_path = name_item.data(Qt.ItemDataRole.UserRole)
        
        if file_path:
            self._update_file_info(file_path)
    
    def _show_context_menu(self, position):
        """Show context menu for file operations."""
        # Get the row at the position
        index = self.files_table.indexAt(position)
        if not index.isValid():
            return
        
        row = index.row()
        status_item = self.files_table.item(row, 7)
        if not status_item:
            return
        
        status = status_item.text()
        
        # Get selected rows
        selected_rows = sorted(
            set(index.row() for index in self.files_table.selectedIndexes())
        )
        
        # If only one row selected or right-clicked row is selected, use single actions
        # If multiple rows selected, show batch actions
        is_multiple_selection = len(selected_rows) > 1
        
        # Create context menu
        menu = QMenu(self)
        
        if is_multiple_selection:
            # Batch actions for multiple selections
            selected_statuses = []
            for r in selected_rows:
                status_item = self.files_table.item(r, 7)
                if status_item:
                    selected_statuses.append(status_item.text())
            
            # Check if all selected have the same status
            all_same_status = len(set(selected_statuses)) == 1
            
            if all_same_status and selected_statuses[0] == "Queued":
                remove_action = menu.addAction(f"Remove {len(selected_rows)} Queued Files")
                remove_action.triggered.connect(lambda: self._remove_selected_files())
                
            elif all_same_status and "Encoding" in selected_statuses[0]:
                cancel_action = menu.addAction(f"Cancel {len(selected_rows)} Encoding Tasks")
                cancel_action.triggered.connect(lambda: self._cancel_selected_processing())
                
            elif all_same_status and selected_statuses[0] == "Completed":
                remove_action = menu.addAction(f"Remove {len(selected_rows)} Completed Files")
                remove_action.triggered.connect(lambda: self._remove_selected_files())
                
            else:
                # Mixed statuses - show individual actions
                remove_action = menu.addAction(f"Remove {len(selected_rows)} Selected Files")
                remove_action.triggered.connect(lambda: self._remove_selected_files())
        else:
            # Single file actions
            if status == "Queued":
                # Actions for queued files
                remove_action = menu.addAction("Remove from Queue")
                remove_action.triggered.connect(lambda: self._remove_file_row(row))
                
            elif "Encoding" in status:
                # Actions for encoding files
                cancel_action = menu.addAction("Cancel Encoding")
                cancel_action.triggered.connect(lambda: self._cancel_file_encoding(row))
                
            elif status == "Completed":
                # Actions for completed files
                remove_action = menu.addAction("Remove from List")
                remove_action.triggered.connect(lambda: self._remove_file_row(row))
                
                # Add option to open output folder
                open_folder_action = menu.addAction("Open Output Folder")
                open_folder_action.triggered.connect(lambda: self._open_output_folder(row))
                
            elif status == "Cancelled" or "Error" in status:
                # Actions for cancelled/error files
                retry_action = menu.addAction("Retry Encoding")
                retry_action.triggered.connect(lambda: self._retry_file_encoding(row))
                
                remove_action = menu.addAction("Remove from List")
                remove_action.triggered.connect(lambda: self._remove_file_row(row))
        
        # Show the menu at the cursor position
        if not menu.isEmpty():
            menu.exec(self.files_table.mapToGlobal(position))
    
    def _update_file_info(self, file_path: str):
        """Update the file info sidebar with information about the selected file."""
        try:
            from core.encodeforge_core import EncodeForgeCore
            core = EncodeForgeCore()
            media_info = core.get_media_info(file_path)
            
            if media_info.get('status') == 'success':
                info = media_info.get('info', {})
                
                # Update file details
                self.name_label.setText(info.get('filename', 'Unknown'))
                self.size_label.setText(f"{info.get('size_mb', 0):.2f} MB")
                self.duration_label.setText(info.get('duration', 'Unknown'))
                self.path_label.setText(file_path)
                
                # Update video properties
                self.codec_label.setText(info.get('video_codec', 'Unknown'))
                self.resolution_label.setText(f"{info.get('width', 0)}x{info.get('height', 0)}")
                self.frame_rate_label.setText(f"{info.get('frame_rate', 0):.2f} fps")
                self.bitrate_label.setText(f"{info.get('bitrate', 0)} kbps")
                
                # Update audio properties
                self.audio_codec_label.setText(info.get('audio_codec', 'Unknown'))
                self.audio_channels_label.setText(str(info.get('audio_channels', 'Unknown')))
                self.sample_rate_label.setText(f"{info.get('sample_rate', 0)} Hz")
                self.audio_bitrate_label.setText(f"{info.get('audio_bitrate', 0)} kbps")
                
                # TODO: Set preview image if available
                self.preview_label.setText("Preview not available")
            else:
                # Clear labels on error
                self._clear_file_info()
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            self._clear_file_info()
    
    def _clear_file_info(self):
        """Clear all file info labels."""
        self.name_label.setText("-")
        self.size_label.setText("-")
        self.duration_label.setText("-")
        self.path_label.setText("-")
        self.codec_label.setText("-")
        self.resolution_label.setText("-")
        self.frame_rate_label.setText("-")
        self.bitrate_label.setText("-")
        self.audio_codec_label.setText("-")
        self.audio_channels_label.setText("-")
        self.sample_rate_label.setText("-")
        self.audio_bitrate_label.setText("-")
        self.preview_label.setText("No file selected")
    
    def _add_files(self, files=None):
        """Add files to the encoding queue."""
        if files is None:
            # Open file dialog if no files provided
            file_dialog = QFileDialog(self)
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
            file_dialog.setNameFilter("Video files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg *.3gp)")
            
            if file_dialog.exec():
                files = file_dialog.selectedFiles()
            else:
                return
        
        for file_path in files:
            self._add_file_to_table(Path(file_path))
    
    def _add_folder(self, folder=None):
        """Add all video files from a folder to the encoding queue."""
        if folder is None:
            folder_dialog = QFileDialog(self)
            folder_dialog.setFileMode(QFileDialog.FileMode.Directory)
            
            if folder_dialog.exec():
                folder = folder_dialog.selectedFiles()[0]
            else:
                return
        
        self._add_folder_to_table(Path(folder))
    
    def _remove_selected_files(self):
        """Remove selected files from the table."""
        selected_rows = sorted(
            set(index.row() for index in self.files_table.selectedIndexes()),
            reverse=True
        )
        for row in selected_rows:
            # Stop encoding if file is currently being encoded
            status_item = self.files_table.item(row, 7)
            if status_item and "Encoding" in status_item.text():
                name_item = self.files_table.item(row, 1)
                if name_item:
                    file_path = name_item.data(Qt.ItemDataRole.UserRole)
                    if file_path in self.active_workers:
                        self.active_workers[file_path].stop()
                        del self.active_workers[file_path]
            
            self.files_table.removeRow(row)
        
        # Check if any queued files remain
        has_queued = False
        for row in range(self.files_table.rowCount()):
            status_item = self.files_table.item(row, 7)
            if status_item and status_item.text() == "Queued":
                has_queued = True
                break
        
        if not has_queued:
            self.start_btn.setEnabled(False)
    
    def _clear_completed_files(self):
        """Clear all completed files from the table."""
        self._clear_completed()
    
    def _remove_file_row(self, row: int):
        """Remove a specific row from the table."""
        # Stop encoding if file is currently being encoded
        status_item = self.files_table.item(row, 7)
        if status_item and "Encoding" in status_item.text():
            name_item = self.files_table.item(row, 1)
            if name_item:
                file_path = name_item.data(Qt.ItemDataRole.UserRole)
                if file_path in self.active_workers:
                    self.active_workers[file_path].stop()
                    del self.active_workers[file_path]
        
        self.files_table.removeRow(row)
        
        # Check if any queued files remain
        has_queued = False
        for r in range(self.files_table.rowCount()):
            status_item = self.files_table.item(r, 7)
            if status_item and status_item.text() == "Queued":
                has_queued = True
                break
        
        if not has_queued:
            self.start_btn.setEnabled(False)
    
    def _cancel_file_encoding(self, row: int):
        """Cancel encoding for a specific file."""
        name_item = self.files_table.item(row, 1)
        if name_item:
            file_path = name_item.data(Qt.ItemDataRole.UserRole)
            if file_path in self.active_workers:
                self.active_workers[file_path].stop()
                del self.active_workers[file_path]
            
            # Update status to cancelled
            self.files_table.setItem(row, 7, QTableWidgetItem("Cancelled"))
            # Remove progress bar
            self.files_table.removeCellWidget(row, 5)
    
    def _open_output_folder(self, row: int):
        """Open the output folder for a completed file."""
        name_item = self.files_table.item(row, 1)
        if not name_item:
            return

        file_path = Path(name_item.data(Qt.ItemDataRole.UserRole))
        # Prefer the path recorded when the encode finished; regenerating it
        # reads the current format combo, which may have changed since.
        recorded = name_item.data(Qt.ItemDataRole.UserRole + 1)
        output_path = Path(recorded) if recorded else self._generate_output_path(file_path)

        folder = output_path.parent if output_path.exists() else file_path.parent
        if not folder.exists():
            logger.warning(f"Output folder does not exist: {folder}")
            return

        # os.startfile is Windows-only; EncodeForge ships Linux and macOS builds.
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))  # noqa: F821 - Windows only
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception as e:
            logger.error(f"Could not open output folder {folder}: {e}")
    
    def _retry_file_encoding(self, row: int):
        """Retry encoding for a failed or cancelled file."""
        # Reset status to queued
        self.files_table.setItem(row, 7, QTableWidgetItem("Queued"))
        # Clear progress and ETA
        self.files_table.setItem(row, 5, QTableWidgetItem("-"))
        self.files_table.setItem(row, 6, QTableWidgetItem("-"))
        # Clear new size
        self.files_table.setItem(row, 4, QTableWidgetItem("-"))
        
        self.start_btn.setEnabled(True)
