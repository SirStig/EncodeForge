"""
EncodeForge Subtitle Tab
Provider selection, Whisper AI controls, and subtitle management
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QPushButton, QProgressBar,
    QLabel, QComboBox, QGroupBox, QFormLayout, QCheckBox,
    QSpinBox, QFileDialog, QHeaderView, QAbstractItemView,
    QTextEdit, QListWidget, QListWidgetItem, QLineEdit
)
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from utils.workers import SubtitleWorker
from utils.notifications import get_notification_manager

logger = logging.getLogger(__name__)


class SubtitleTab(QWidget):
    """
    Subtitle tab for downloading and generating subtitles.
    
    Signals:
        subtitle_started: Emitted when subtitle processing begins
        subtitle_progress: Emitted with (file, current, total, message) during processing
        subtitle_completed: Emitted when subtitle processing completes
        subtitle_error: Emitted with (file, error_message) on error
    """
    
    subtitle_started = Signal(str)  # file path
    subtitle_progress = Signal(str, int, int, str)  # file, current, total, message
    subtitle_completed = Signal(str)  # file path
    subtitle_error = Signal(str, str)  # file path, error message
    
    def __init__(self, thread_pool: QThreadPool, parent=None):
        """
        Initialize subtitle tab.
        
        Args:
            thread_pool: QThreadPool for parallel processing
            parent: Parent widget
        """
        super().__init__(parent)
        self.thread_pool = thread_pool
        self.notifier = get_notification_manager()
        self.active_workers: Dict[str, SubtitleWorker] = {}
        
        self._setup_ui()
        self._connect_signals()
        self._load_styles()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Apply macOS-inspired styling
        # self.setStyleSheet("""...""")  # Moved to external CSS file
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: File list and queue
        left_panel = self._create_file_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Settings and preview
        right_panel = self._create_settings_panel()
        splitter.addWidget(right_panel)
        
        # Set initial sizes (60/40 split)
        splitter.setSizes([600, 400])
        
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
            "File", "Language", "Status", "Progress", "Method"
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
        
        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setEnabled(False)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        
        queue_controls.addWidget(self.start_btn)
        queue_controls.addWidget(self.stop_btn)
        queue_controls.addStretch()
        
        layout.addLayout(queue_controls)
        
        return panel
    
    def _create_settings_panel(self) -> QWidget:
        """Create subtitle settings panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Mode selection
        mode_group = QGroupBox("Processing Mode")
        mode_layout = QVBoxLayout()
        
        self.download_radio = QCheckBox("Download from Providers")
        self.download_radio.setChecked(True)
        self.whisper_radio = QCheckBox("Generate with Whisper AI")
        
        mode_layout.addWidget(self.download_radio)
        mode_layout.addWidget(self.whisper_radio)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Language selection
        lang_group = QGroupBox("Language Settings")
        lang_layout = QFormLayout()
        
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "English", "Spanish", "French", "German", "Italian",
            "Portuguese", "Russian", "Japanese", "Korean", "Chinese",
            "Arabic", "Dutch", "Polish", "Swedish", "Turkish"
        ])
        lang_layout.addRow("Primary Language:", self.language_combo)
        
        self.fallback_check = QCheckBox("Try other languages if not found")
        self.fallback_check.setChecked(True)
        lang_layout.addRow("", self.fallback_check)
        
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)
        
        # Provider selection (for download mode)
        self.provider_group = QGroupBox("Subtitle Providers")
        provider_layout = QVBoxLayout()
        
        providers_label = QLabel("Select providers to search:")
        providers_label.setObjectName("providers_label")
        provider_layout.addWidget(providers_label)
        
        self.provider_list = QListWidget()
        self.provider_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        
        providers = [
            "OpenSubtitles",
            "Addic7ed",
            "SubDL",
            "Subf2m",
            "YIFY Subtitles",
            "Podnapisi",
            "SubDivX",
            "Kitsunekko (Anime)",
            "Jimaku (Japanese)"
        ]
        
        for provider in providers:
            item = QListWidgetItem(provider)
            self.provider_list.addItem(item)
            # Select first 3 by default
            if providers.index(provider) < 3:
                item.setSelected(True)
        
        provider_layout.addWidget(self.provider_list)
        
        self.provider_group.setLayout(provider_layout)
        layout.addWidget(self.provider_group)
        
        # Whisper AI settings (for generation mode)
        self.whisper_group = QGroupBox("Whisper AI Settings")
        whisper_layout = QFormLayout()
        
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems([
            "tiny (fastest, least accurate)",
            "base",
            "small",
            "medium (recommended)",
            "large (best quality, slowest)"
        ])
        self.whisper_model_combo.setCurrentIndex(3)  # medium
        whisper_layout.addRow("Model:", self.whisper_model_combo)
        
        self.whisper_device_combo = QComboBox()
        self.whisper_device_combo.addItems(["Auto", "CPU", "CUDA (GPU)", "MPS (Apple Silicon)"])
        whisper_layout.addRow("Device:", self.whisper_device_combo)
        
        self.translate_check = QCheckBox("Translate to English")
        whisper_layout.addRow("", self.translate_check)
        
        self.whisper_group.setLayout(whisper_layout)
        self.whisper_group.setVisible(False)  # Hidden by default
        layout.addWidget(self.whisper_group)
        
        # Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout()
        
        self.subtitle_format_combo = QComboBox()
        self.subtitle_format_combo.addItems(["SRT", "VTT", "ASS/SSA"])
        output_layout.addRow("Format:", self.subtitle_format_combo)
        
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["UTF-8", "UTF-8 BOM", "ASCII", "ISO-8859-1"])
        output_layout.addRow("Encoding:", self.encoding_combo)
        
        self.sync_check = QCheckBox("Attempt to sync subtitles")
        self.sync_check.setChecked(True)
        output_layout.addRow("", self.sync_check)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Preview section
        preview_group = QGroupBox("Subtitle Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Subtitle preview will appear here...")
        self.preview_text.setMaximumHeight(150)
        
        preview_layout.addWidget(self.preview_text)
        
        preview_buttons = QHBoxLayout()
        self.load_preview_btn = QPushButton("Load Subtitle")
        self.load_preview_btn.setProperty("secondary", True)
        preview_buttons.addWidget(self.load_preview_btn)
        preview_buttons.addStretch()
        
        preview_layout.addLayout(preview_buttons)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        layout.addStretch()
        
        return panel
    
    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_all)
        self.start_btn.clicked.connect(self._start_processing)
        self.stop_btn.clicked.connect(self._stop_processing)
        
        # Mode switching
        self.download_radio.toggled.connect(self._on_mode_changed)
        self.whisper_radio.toggled.connect(self._on_mode_changed)
        
        # Preview
        self.load_preview_btn.clicked.connect(self._load_preview)
    
    def _load_styles(self):
        """Load CSS styles for the subtitle tab."""
        try:
            from PySide6.QtCore import QFile, QTextStream
            
            css_file = Path(__file__).parent.parent.parent / "resources" / "styles" / "subtitle_tab.css"
            if css_file.exists():
                file = QFile(str(css_file))
                if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
                    stream = QTextStream(file)
                    css_content = stream.readAll()
                    file.close()
                    
                    # Apply the CSS
                    self.setStyleSheet(css_content)
                    logger.debug("Subtitle tab styles loaded successfully")
                else:
                    logger.warning("Failed to open subtitle_tab.css file")
            else:
                logger.warning("subtitle_tab.css file not found")
        except Exception as e:
            logger.error(f"Failed to load subtitle tab styles: {e}")
    
    def _on_mode_changed(self):
        """Handle processing mode change."""
        download_mode = self.download_radio.isChecked()
        self.provider_group.setVisible(download_mode)
        self.whisper_group.setVisible(not download_mode)
    
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
        """Add file to the subtitle queue."""
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return
        
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        
        # File name
        self.file_table.setItem(row, 0, QTableWidgetItem(file_path.name))
        
        # Language
        language = self.language_combo.currentText()
        self.file_table.setItem(row, 1, QTableWidgetItem(language))
        
        # Status
        self.file_table.setItem(row, 2, QTableWidgetItem("Queued"))
        
        # Progress bar
        progress = QProgressBar()
        progress.setValue(0)
        self.file_table.setCellWidget(row, 3, progress)
        
        # Method
        method = "Download" if self.download_radio.isChecked() else "Whisper AI"
        self.file_table.setItem(row, 4, QTableWidgetItem(method))
        
        # Store full path in item data
        self.file_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, str(file_path))
        
        self.start_btn.setEnabled(True)
        logger.info(f"Added file to subtitle queue: {file_path.name}")
    
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
    
    def _start_processing(self):
        """Start processing all queued files."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        for row in range(self.file_table.rowCount()):
            status_item = self.file_table.item(row, 2)
            if status_item.text() == "Queued":
                self._process_file(row)
    
    def _process_file(self, row: int):
        """Start processing a single file."""
        file_item = self.file_table.item(row, 0)
        file_path = Path(file_item.data(Qt.ItemDataRole.UserRole))
        
        # Update status
        self.file_table.item(row, 2).setText("Processing...")
        
        # Get subtitle settings
        settings = self._get_subtitle_settings()
        
        # Create worker
        worker = SubtitleWorker(file_path, settings)
        
        # Connect signals
        worker.signals.started.connect(
            lambda: self._on_subtitle_started(row, str(file_path))
        )
        worker.signals.progress.connect(
            lambda cur, tot, msg: self._on_subtitle_progress(row, cur, tot, msg)
        )
        worker.signals.result.connect(
            lambda result: self._on_subtitle_completed(row, str(file_path))
        )
        worker.signals.error.connect(
            lambda error: self._on_subtitle_error(row, str(file_path), error)
        )
        
        # Track worker
        self.active_workers[str(file_path)] = worker
        
        # Start worker
        self.thread_pool.start(worker)
        logger.info(f"Started subtitle processing: {file_path.name}")
    
    def _get_subtitle_settings(self) -> Dict[str, Any]:
        """Get current subtitle settings as dictionary."""
        settings = {
            'mode': 'download' if self.download_radio.isChecked() else 'whisper',
            'language': self.language_combo.currentText(),
            'fallback': self.fallback_check.isChecked(),
            'format': self.subtitle_format_combo.currentText(),
            'encoding': self.encoding_combo.currentText(),
            'sync': self.sync_check.isChecked()
        }
        
        if settings['mode'] == 'download':
            settings['providers'] = [
                item.text() for item in self.provider_list.selectedItems()
            ]
        else:
            # Extract model name (remove description)
            model_text = self.whisper_model_combo.currentText()
            settings['whisper_model'] = model_text.split()[0]
            settings['whisper_device'] = self.whisper_device_combo.currentText()
            settings['translate'] = self.translate_check.isChecked()
        
        return settings
    
    def _on_subtitle_started(self, row: int, file_path: str):
        """Handle subtitle processing started event."""
        self.subtitle_started.emit(file_path)
        logger.debug(f"Subtitle processing started for row {row}: {file_path}")
    
    def _on_subtitle_progress(self, row: int, current: int, total: int, message: str):
        """Handle subtitle processing progress update."""
        progress_bar = self.file_table.cellWidget(row, 3)
        if progress_bar and isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(int((current / total) * 100))
        
        file_item = self.file_table.item(row, 0)
        file_path = file_item.data(Qt.ItemDataRole.UserRole)
        self.subtitle_progress.emit(file_path, current, total, message)
    
    def _on_subtitle_completed(self, row: int, file_path: str):
        """Handle subtitle processing completed event."""
        self.file_table.item(row, 2).setText("Completed")
        progress_bar = self.file_table.cellWidget(row, 3)
        if progress_bar:
            progress_bar.setValue(100)
        
        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        self.subtitle_completed.emit(file_path)
        logger.info(f"Subtitle processing completed: {file_path}")
        
        # Check if all done
        self._check_queue_complete()
    
    def _on_subtitle_error(self, row: int, file_path: str, error: tuple):
        """Handle subtitle processing error event."""
        exc_type, value, tb = error
        error_msg = str(value)
        
        self.file_table.item(row, 2).setText(f"Error: {error_msg}")
        
        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        self.subtitle_error.emit(file_path, error_msg)
        logger.error(f"Subtitle processing error for {file_path}: {error_msg}")
        
        # Check if all done
        self._check_queue_complete()
    
    def _stop_processing(self):
        """Stop all active subtitle processing tasks."""
        for worker in self.active_workers.values():
            worker.stop()
        
        self.active_workers.clear()
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        logger.info("Stopped all subtitle processing tasks")
    
    def _check_queue_complete(self):
        """Check if all subtitle processing tasks are complete."""
        if not self.active_workers:
            self.stop_btn.setEnabled(False)
            self.start_btn.setEnabled(True)
            
            # Count completed
            completed = sum(
                1 for row in range(self.file_table.rowCount())
                if self.file_table.item(row, 2).text() == "Completed"
            )
            
            if completed > 0:
                logger.info(f"Batch subtitle processing complete: {completed} files")
    
    def _load_preview(self):
        """Load a subtitle file for preview."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitle File",
            "",
            "Subtitle Files (*.srt *.vtt *.ass *.ssa);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(5000)  # Read first 5000 chars
                    if len(content) == 5000:
                        content += "\n\n... (preview truncated)"
                    self.preview_text.setPlainText(content)
                logger.info(f"Loaded subtitle preview: {file_path}")
            except Exception as e:
                logger.error(f"Failed to load subtitle preview: {e}")
                self.preview_text.setPlainText(f"Error loading subtitle: {e}")
