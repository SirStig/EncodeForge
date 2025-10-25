"""
EncodeForge Encoder Tab
File list, settings panel, and queue management for video encoding
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QPushButton, QProgressBar,
    QLabel, QComboBox, QSlider, QGroupBox, QFormLayout,
    QCheckBox, QSpinBox, QFileDialog, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from utils.workers import EncoderWorker
from utils.notifications import get_notification_manager

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
        
        # Apply macOS-inspired styling
        self.setStyleSheet("""
            /* Encoder Tab Styling */
            QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            
            /* Buttons */
            QPushButton {
                background-color: #0a84ff;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #0077ed;
            }
            
            QPushButton:pressed {
                background-color: #006adc;
            }
            
            QPushButton:disabled {
                background-color: #3a3a3c;
                color: #636366;
            }
            
            /* Tables */
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #252525;
                gridline-color: #3a3a3a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            
            QTableWidget::item {
                padding: 8px;
                color: #ffffff;
            }
            
            QTableWidget::item:selected {
                background-color: #0a84ff;
            }
            
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #8e8e93;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #3a3a3a;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
            }
            
            /* Group Boxes */
            QGroupBox {
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #8e8e93;
            }
            
            /* Combo Boxes */
            QComboBox {
                background-color: #3a3a3c;
                border: 1px solid #48484a;
                border-radius: 6px;
                padding: 6px 12px;
                color: #ffffff;
                min-width: 120px;
            }
            
            QComboBox:hover {
                border-color: #0a84ff;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                selection-background-color: #0a84ff;
                color: #ffffff;
            }
            
            /* Sliders */
            QSlider::groove:horizontal {
                background-color: #3a3a3c;
                height: 6px;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background-color: #0a84ff;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            
            QSlider::handle:horizontal:hover {
                background-color: #0077ed;
            }
            
            /* Spin Boxes */
            QSpinBox {
                background-color: #3a3a3c;
                border: 1px solid #48484a;
                border-radius: 6px;
                padding: 6px 12px;
                color: #ffffff;
            }
            
            QSpinBox:hover {
                border-color: #0a84ff;
            }
            
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: transparent;
                border: none;
                width: 16px;
            }
            
            /* Check Boxes */
            QCheckBox {
                color: #ffffff;
                spacing: 8px;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #48484a;
                border-radius: 4px;
                background-color: #3a3a3c;
            }
            
            QCheckBox::indicator:checked {
                background-color: #0a84ff;
                border-color: #0a84ff;
            }
            
            QCheckBox::indicator:hover {
                border-color: #0a84ff;
            }
            
            /* Progress Bars */
            QProgressBar {
                background-color: #3a3a3c;
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            
            QProgressBar::chunk {
                background-color: #0a84ff;
                border-radius: 4px;
            }
            
            /* Labels */
            QLabel {
                color: #ffffff;
            }
            
            /* Splitter */
            QSplitter::handle {
                background-color: #3a3a3a;
                width: 1px;
            }
        """)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: File list and queue
        left_panel = self._create_file_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Settings
        right_panel = self._create_settings_panel()
        splitter.addWidget(right_panel)
        
        # Set initial sizes (70/30 split)
        splitter.setSizes([700, 300])
        
        layout.addWidget(splitter)
    
    def _create_file_panel(self) -> QWidget:
        """Create file list and queue management panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        from PySide6.QtWidgets import QStyle
        
        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.add_folder_btn = QPushButton("Add Folder")
        self.add_folder_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.clear_btn = QPushButton("Clear All")
        
        toolbar.addWidget(self.add_files_btn)
        toolbar.addWidget(self.add_folder_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # File table
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels([
            "File", "Size", "Status", "Progress", "Output"
        ])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.file_table.setAcceptDrops(True)
        
        # Enable drag and drop
        self.file_table.dragEnterEvent = self._drag_enter_event
        self.file_table.dropEvent = self._drop_event
        
        layout.addWidget(self.file_table)
        
        # Queue controls
        queue_controls = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Encoding")
        self.start_btn.setEnabled(False)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        
        queue_controls.addWidget(self.start_btn)
        queue_controls.addWidget(self.pause_btn)
        queue_controls.addWidget(self.stop_btn)
        queue_controls.addStretch()
        
        layout.addLayout(queue_controls)
        
        return panel
    
    def _create_settings_panel(self) -> QWidget:
        """Create encoder settings panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Codec settings
        codec_group = QGroupBox("Codec Settings")
        codec_layout = QFormLayout()
        
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264", "H.265/HEVC", "AV1", "VP9", "Copy"])
        codec_layout.addRow("Video Codec:", self.codec_combo)
        
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", 
            "fast", "medium", "slow", "slower", "veryslow"
        ])
        self.preset_combo.setCurrentText("medium")
        codec_layout.addRow("Preset:", self.preset_combo)
        
        codec_group.setLayout(codec_layout)
        layout.addWidget(codec_group)
        
        # Quality settings
        quality_group = QGroupBox("Quality Settings")
        quality_layout = QFormLayout()
        
        crf_layout = QHBoxLayout()
        self.crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_label = QLabel("23")
        self.crf_slider.valueChanged.connect(
            lambda v: self.crf_label.setText(str(v))
        )
        crf_layout.addWidget(self.crf_slider)
        crf_layout.addWidget(self.crf_label)
        quality_layout.addRow("CRF:", crf_layout)
        
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["AAC", "Opus", "MP3", "Copy"])
        quality_layout.addRow("Audio Codec:", self.audio_codec_combo)
        
        self.audio_bitrate = QSpinBox()
        self.audio_bitrate.setRange(64, 512)
        self.audio_bitrate.setValue(192)
        self.audio_bitrate.setSuffix(" kbps")
        quality_layout.addRow("Audio Bitrate:", self.audio_bitrate)
        
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)
        
        # Hardware acceleration
        hw_group = QGroupBox("Hardware Acceleration")
        hw_layout = QFormLayout()
        
        self.hw_accel_combo = QComboBox()
        self.hw_accel_combo.addItems([
            "None", "NVENC (NVIDIA)", "AMF (AMD)", 
            "QuickSync (Intel)", "VideoToolbox (macOS)"
        ])
        hw_layout.addRow("Acceleration:", self.hw_accel_combo)
        
        hw_group.setLayout(hw_layout)
        layout.addWidget(hw_group)
        
        # Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout()
        
        self.container_combo = QComboBox()
        self.container_combo.addItems(["MP4", "MKV", "WebM", "AVI"])
        output_layout.addRow("Container:", self.container_combo)
        
        self.two_pass_check = QCheckBox("Enable 2-pass encoding")
        output_layout.addRow("", self.two_pass_check)
        
        self.preserve_metadata_check = QCheckBox("Preserve metadata")
        self.preserve_metadata_check.setChecked(True)
        output_layout.addRow("", self.preserve_metadata_check)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        layout.addStretch()
        
        return panel
    
    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_all)
        self.start_btn.clicked.connect(self._start_encoding)
        self.stop_btn.clicked.connect(self._stop_encoding)
    
    def _drag_enter_event(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def _drop_event(self, event: QDropEvent):
        """Handle drop event."""
        urls = event.mimeData().urls()
        for url in urls:
            file_path = Path(url.toLocalFile())
            if file_path.is_file() and self._is_video_file(file_path):
                self._add_file_to_table(file_path)
            elif file_path.is_dir():
                self._add_folder_to_table(file_path)
        event.acceptProposedAction()
    
    def _is_video_file(self, file_path: Path) -> bool:
        """Check if file is a video file."""
        video_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', 
            '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'
        }
        return file_path.suffix.lower() in video_extensions
    
    def _add_files(self):
        """Open file dialog to add files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v);;All Files (*.*)"
        )
        for file in files:
            self._add_file_to_table(Path(file))
    
    def _add_folder(self):
        """Open folder dialog to add all videos in folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder"
        )
        if folder:
            self._add_folder_to_table(Path(folder))
    
    def _add_file_to_table(self, file_path: Path):
        """Add file to the encoding queue."""
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return
        
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        
        # File name
        self.file_table.setItem(row, 0, QTableWidgetItem(file_path.name))
        
        # File size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        self.file_table.setItem(row, 1, QTableWidgetItem(f"{size_mb:.2f} MB"))
        
        # Status
        self.file_table.setItem(row, 2, QTableWidgetItem("Queued"))
        
        # Progress bar
        progress = QProgressBar()
        progress.setValue(0)
        self.file_table.setCellWidget(row, 3, progress)
        
        # Output path (will be set when encoding starts)
        self.file_table.setItem(row, 4, QTableWidgetItem(""))
        
        # Store full path in item data
        self.file_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, str(file_path))
        
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
    
    def _remove_selected(self):
        """Remove selected rows from table."""
        selected_rows = sorted(
            set(index.row() for index in self.file_table.selectedIndexes()),
            reverse=True
        )
        for row in selected_rows:
            self.file_table.removeRow(row)
        
        if self.file_table.rowCount() == 0:
            self.start_btn.setEnabled(False)
    
    def _clear_all(self):
        """Clear all files from table."""
        self.file_table.setRowCount(0)
        self.start_btn.setEnabled(False)
    
    def _start_encoding(self):
        """Start encoding all queued files."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        for row in range(self.file_table.rowCount()):
            status_item = self.file_table.item(row, 2)
            if status_item.text() == "Queued":
                self._encode_file(row)
    
    def _encode_file(self, row: int):
        """Start encoding a single file."""
        file_item = self.file_table.item(row, 0)
        file_path = Path(file_item.data(Qt.ItemDataRole.UserRole))
        
        # Generate output path
        output_path = self._generate_output_path(file_path)
        self.file_table.item(row, 4).setText(str(output_path))
        
        # Update status
        self.file_table.item(row, 2).setText("Encoding...")
        
        # Get encoder settings
        settings = self._get_encoder_settings()
        
        # Create worker
        worker = EncoderWorker(file_path, output_path, settings)
        
        # Connect signals
        worker.signals.started.connect(
            lambda: self._on_encode_started(row, str(file_path))
        )
        worker.signals.progress.connect(
            lambda cur, tot, msg: self._on_encode_progress(row, cur, tot, msg)
        )
        worker.signals.result.connect(
            lambda result: self._on_encode_completed(row, str(file_path))
        )
        worker.signals.error.connect(
            lambda error: self._on_encode_error(row, str(file_path), error)
        )
        
        # Track worker
        self.active_workers[str(file_path)] = worker
        
        # Start worker
        self.thread_pool.start(worker)
        logger.info(f"Started encoding: {file_path.name}")
    
    def _generate_output_path(self, input_path: Path) -> Path:
        """Generate output file path based on settings."""
        container = self.container_combo.currentText().lower()
        output_name = f"{input_path.stem}_encoded.{container}"
        return input_path.parent / output_name
    
    def _get_encoder_settings(self) -> Dict[str, Any]:
        """Get current encoder settings as dictionary."""
        return {
            'codec': self.codec_combo.currentText(),
            'preset': self.preset_combo.currentText(),
            'crf': self.crf_slider.value(),
            'audio_codec': self.audio_codec_combo.currentText(),
            'audio_bitrate': self.audio_bitrate.value(),
            'hw_accel': self.hw_accel_combo.currentText(),
            'container': self.container_combo.currentText(),
            'two_pass': self.two_pass_check.isChecked(),
            'preserve_metadata': self.preserve_metadata_check.isChecked()
        }
    
    def _on_encode_started(self, row: int, file_path: str):
        """Handle encoding started event."""
        self.encode_started.emit(file_path)
        logger.debug(f"Encode started for row {row}: {file_path}")
    
    def _on_encode_progress(self, row: int, current: int, total: int, message: str):
        """Handle encoding progress update."""
        progress_bar = self.file_table.cellWidget(row, 3)
        if progress_bar and isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(int((current / total) * 100))
        
        file_item = self.file_table.item(row, 0)
        file_path = file_item.data(Qt.ItemDataRole.UserRole)
        self.encode_progress.emit(file_path, current, total, message)
    
    def _on_encode_completed(self, row: int, file_path: str):
        """Handle encoding completed event."""
        self.file_table.item(row, 2).setText("Completed")
        progress_bar = self.file_table.cellWidget(row, 3)
        if progress_bar:
            progress_bar.setValue(100)
        
        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        self.encode_completed.emit(file_path)
        
        # Note: Notification would be async, but we're in a sync context
        # Consider using QTimer or asyncio integration for async notifications
        logger.info(f"Encode completed: {file_path}")
        
        # Check if all done
        self._check_queue_complete()
    
    def _on_encode_error(self, row: int, file_path: str, error: tuple):
        """Handle encoding error event."""
        exc_type, value, tb = error
        error_msg = str(value)
        
        self.file_table.item(row, 2).setText(f"Error: {error_msg}")
        
        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        self.encode_error.emit(file_path, error_msg)
        
        # Note: Notification would be async, but we're in a sync context
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
            
            # Count completed
            completed = sum(
                1 for row in range(self.file_table.rowCount())
                if self.file_table.item(row, 2).text() == "Completed"
            )
            
            if completed > 0:
                # Note: Notifications would be async
                logger.info(f"Batch encoding complete: {completed} files")
