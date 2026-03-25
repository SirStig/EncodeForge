"""
EncodeForge Encoder Tab
File list, settings panel, and queue management for video encoding
"""

import logging
from pathlib import Path
from typing import Any, Dict

import qtawesome as qta
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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
from utils.workers import EncoderWorker

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
        self.active_workers: Dict[str, EncoderWorker] = {}
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main splitter: Left (tables) | Right (file info)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Settings + Tables
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top: Video Settings
        self._setup_video_settings(left_layout)
        
        # Below: Tables splitter (Queued | Processing | Completed)
        self._setup_tables_area(left_layout)
        
        main_splitter.addWidget(left_widget)
        
        # Right side: File Info sidebar
        self._setup_file_info_sidebar(main_splitter)
        
        # Set splitter proportions (more space for tables, less for sidebar)
        main_splitter.setSizes([700, 320])
        
        layout.addWidget(main_splitter)
        
        logger.debug("Encoder tab initialized - using base glassmorphism theme")
    
    def _setup_video_settings(self, parent_layout):
        """Set up the top video settings panel with two-row layout."""
        # Settings container
        settings_widget = QWidget()
        settings_widget.setObjectName("encoder_toolbar")
        settings_main_layout = QVBoxLayout(settings_widget)
        settings_main_layout.setContentsMargins(10, 6, 10, 6)
        settings_main_layout.setSpacing(4)
        
        # Row 1: Format, Codec, Quality, Preset
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(8)
        
        # Format dropdown
        format_label = StyledLabel("Format:")
        format_label.setFixedWidth(55)
        format_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.format_combo = StyledComboBox()
        self.format_combo.addItems(["MP4", "MKV", "WebM", "AVI", "MOV"])
        self.format_combo.setFixedWidth(90)
        row1_layout.addWidget(format_label)
        row1_layout.addWidget(self.format_combo)
        row1_layout.addSpacing(12)

        # Codec dropdown
        codec_label = StyledLabel("Codec:")
        codec_label.setFixedWidth(50)
        codec_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.codec_combo = StyledComboBox()
        self.codec_combo.addItems(["H.264", "H.265/HEVC", "AV1", "VP9", "Copy", "Auto"])
        self.codec_combo.setCurrentText("Auto")
        self.codec_combo.setFixedWidth(120)
        row1_layout.addWidget(codec_label)
        row1_layout.addWidget(self.codec_combo)
        row1_layout.addSpacing(12)

        # Quality dropdown
        quality_label = StyledLabel("Quality:")
        quality_label.setFixedWidth(50)
        quality_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.quality_combo = StyledComboBox()
        self.quality_combo.addItems(["High (CQ 18)", "Medium (CQ 23)", "Low (CQ 28)", "Very Low (CQ 33)"])
        self.quality_combo.setCurrentText("Medium (CQ 23)")
        self.quality_combo.setFixedWidth(130)
        row1_layout.addWidget(quality_label)
        row1_layout.addWidget(self.quality_combo)
        row1_layout.addSpacing(12)

        # Preset dropdown
        preset_label = StyledLabel("Preset:")
        preset_label.setFixedWidth(50)
        preset_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.preset_combo = StyledComboBox()
        self.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_combo.setCurrentText("medium")
        self.preset_combo.setFixedWidth(100)
        row1_layout.addWidget(preset_label)
        row1_layout.addWidget(self.preset_combo)
        
        row1_layout.addStretch()
        settings_main_layout.addLayout(row1_layout)
        
        # Add minimal spacing between rows
        settings_main_layout.addSpacing(5)
        
        # Row 2: Checkboxes and Action Buttons
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(8)
        
        # Hardware acceleration checkbox
        self.hw_accel_check = StyledCheckBox("HW Accel")
        self.hw_accel_check.setChecked(True)
        self.hw_accel_check.setFixedWidth(90)
        self.hw_accel_check.setMaximumHeight(20)
        row2_layout.addWidget(self.hw_accel_check)
        row2_layout.addSpacing(8)

        # Normalize audio checkbox
        self.normalize_audio_check = StyledCheckBox("Normalize")
        self.normalize_audio_check.setFixedWidth(90)
        self.normalize_audio_check.setMaximumHeight(20)
        row2_layout.addWidget(self.normalize_audio_check)

        # Spacer
        row2_layout.addStretch()

        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setIcon(qta.icon('fa5s.stop'))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedWidth(70)
        self.stop_btn.setMaximumHeight(22)
        row2_layout.addWidget(self.stop_btn)
        row2_layout.addSpacing(6)

        # Start button
        self.start_btn = QPushButton("Start Encoding")
        self.start_btn.setIcon(qta.icon('fa5s.play'))
        self.start_btn.setFixedWidth(130)
        self.start_btn.setMaximumHeight(22)
        row2_layout.addWidget(self.start_btn)
        
        settings_main_layout.addLayout(row2_layout)
        parent_layout.addWidget(settings_widget)
    
    def _setup_tables_area(self, parent_layout):
        """Set up the single file table with all encoding states."""
        # Main table container
        table_group = GlassmorphicCard("Files")
        table_layout = QVBoxLayout(table_group)
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
        self.files_table.verticalHeader().setDefaultSectionSize(24)
        
        # Enable context menu
        self.files_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_table.customContextMenuRequested.connect(self._show_context_menu)
        
        table_layout.addWidget(self.files_table, 1)  # Give table the stretch factor
        
        # Table control buttons using glassmorphic buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 4, 0, 0)
        buttons_layout.setSpacing(8)
        
        self.add_files_btn = GlassmorphicButton("Add Files", qta.icon('fa5s.plus'))
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_files_btn.setMinimumWidth(80)
        
        self.add_folder_btn = GlassmorphicButton("Add Folder", qta.icon('fa5s.folder-plus'))
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.add_folder_btn.setMinimumWidth(85)
        
        self.remove_selected_btn = GlassmorphicButton("Remove Selected", qta.icon('fa5s.trash'))
        self.remove_selected_btn.clicked.connect(self._remove_selected_files)
        self.remove_selected_btn.setMinimumWidth(110)
        
        self.clear_completed_btn = GlassmorphicButton("Clear Completed", qta.icon('fa5s.broom'))
        self.clear_completed_btn.clicked.connect(self._clear_completed_files)
        self.clear_completed_btn.setMinimumWidth(110)
        
        buttons_layout.addWidget(self.add_files_btn)
        buttons_layout.addWidget(self.add_folder_btn)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.remove_selected_btn)
        buttons_layout.addWidget(self.clear_completed_btn)
        buttons_layout.addStretch()
        
        table_layout.addLayout(buttons_layout, 0)  # No stretch for buttons
        
        parent_layout.addWidget(table_group, 1)  # Give the whole group a stretch factor
    
    def _setup_file_info_sidebar(self, splitter):
        """Set up the file info sidebar on the right."""
        sidebar = QWidget()
        sidebar.setFixedWidth(320)
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
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = StyledLabel("No file selected")
        self.preview_label.setObjectName("preview_label")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(120)
        preview_layout.addWidget(self.preview_label)
        sidebar_layout.addWidget(preview_group)
        
        # File Information Section
        file_group = GlassmorphicCard("File Details")
        file_layout = QFormLayout(file_group)
        file_layout.setSpacing(6)
        file_layout.setContentsMargins(8, 12, 8, 8)
        
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
        video_layout = QFormLayout(video_group)
        video_layout.setSpacing(6)
        video_layout.setContentsMargins(8, 12, 8, 8)
        
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
        audio_layout = QFormLayout(audio_group)
        audio_layout.setSpacing(6)
        audio_layout.setContentsMargins(8, 12, 8, 8)
        
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
        self.files_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Button connections
        self.start_btn.clicked.connect(self._start_encoding)
        self.stop_btn.clicked.connect(self._stop_encoding)
    
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
    
    def _encode_file(self, proc_row: int, file_path: Path):
        """Start encoding a single file."""
        # Generate output path
        output_path = self._generate_output_path(file_path)
        
        # Get encoder settings
        settings = self._get_encoder_settings()
        
        # Create worker
        worker = EncoderWorker(file_path, output_path, settings)
        
        # Connect signals
        worker.signals.started.connect(
            lambda: self._on_encode_started(proc_row, str(file_path))
        )
        worker.signals.progress.connect(
            lambda cur, tot, msg: self._on_encode_progress(proc_row, cur, tot, msg)
        )
        worker.signals.result.connect(
            lambda result: self._on_encode_completed(proc_row, str(file_path))
        )
        worker.signals.error.connect(
            lambda error: self._on_encode_error(proc_row, str(file_path), error)
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
        return {
            'format': self.format_combo.currentText(),
            'codec': self.codec_combo.currentText(),
            'quality': self.quality_combo.currentText(),
            'preset': self.preset_combo.currentText(),
            'hw_accel': self.hw_accel_check.isChecked(),
            'normalize_audio': self.normalize_audio_check.isChecked(),
            'container': self.format_combo.currentText().lower()
        }
    
    def _on_encode_started(self, row: int, file_path: str):
        """Handle encoding started event."""
        self.encode_started.emit(file_path)
        logger.debug(f"Encode started for row {row}: {file_path}")
    
    def _on_encode_progress(self, proc_row: int, current: int, total: int, message: str):
        """Handle encoding progress update."""
        progress_bar = self.files_table.cellWidget(proc_row, 5)
        if progress_bar and isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(int((current / total) * 100))
        
        # Update status
        status_item = self.files_table.item(proc_row, 7)
        if status_item:
            status_item.setText(f"Encoding... {int((current / total) * 100)}%")
        
        file_item = self.files_table.item(proc_row, 1)
        if file_item:
            file_path = file_item.data(Qt.ItemDataRole.UserRole)
            self.encode_progress.emit(file_path, current, total, message)
    
    def _on_encode_completed(self, proc_row: int, file_path: str):
        """Handle encoding completed event."""
        # Update status to completed
        self.files_table.setItem(proc_row, 7, QTableWidgetItem("Completed"))
        
        # Update progress to 100%
        progress_bar = self.files_table.cellWidget(proc_row, 5)
        if progress_bar and isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(100)
        
        # Update ETA to completion time
        self.files_table.setItem(proc_row, 6, QTableWidgetItem("00:00"))
        
        # Update output file size if available
        output_path = self._generate_output_path(Path(file_path))
        if output_path.exists():
            new_size = output_path.stat().st_size / (1024 * 1024)  # MB
            self.files_table.setItem(proc_row, 4, QTableWidgetItem(f"{new_size:.2f} MB"))
        
        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        self.encode_completed.emit(file_path)
        logger.info(f"Encode completed: {file_path}")
        
        # Check if all done
        self._check_queue_complete()
    

    
    def _on_encode_error(self, proc_row: int, file_path: str, error: tuple):
        """Handle encoding error event."""
        exc_type, value, tb = error
        error_msg = str(value)
        
        # Update status to error
        self.files_table.setItem(proc_row, 7, QTableWidgetItem(f"Error: {error_msg}"))
        
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
        """Stop all active encoding tasks."""
        for worker in self.active_workers.values():
            worker.stop()
        
        self.active_workers.clear()
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        logger.info("Stopped all encoding tasks")
    
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
        if name_item:
            file_path = Path(name_item.data(Qt.ItemDataRole.UserRole))
            output_path = self._generate_output_path(file_path)
            if output_path.exists():
                import os
                os.startfile(str(output_path.parent))
    
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
