"""
EncodeForge Subtitle Tab
Provider selection, Whisper AI controls, and subtitle management
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.notifications import get_notification_manager
from utils.workers import SubtitleWorker

logger = logging.getLogger(__name__)


class SubtitleTab(QWidget):
    def _on_provider_changed(self):
        # Handle provider selection changes (e.g., update All selection logic)
        all_item = self.provider_list.item(0)
        if all_item and all_item.isSelected():
            # If All is selected, select all providers
            for i in range(self.provider_list.count()):
                self.provider_list.item(i).setSelected(True)
        else:
            # If All is deselected, allow custom selection
            pass

    def _on_language_changed(self):
        # Handle language selection changes (could update UI or logic)
        pass

    def _on_search_clicked(self):
        # Handle search/generate button click
        pass

    def _on_apply_clicked(self):
        # Handle Apply button click (single file)
        pass

    def _on_batch_apply_clicked(self):
        # Handle Batch Apply button click (all files)
        pass
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
        logger.debug("Subtitle tab initialized - using base glassmorphism theme")
    
    def _setup_ui(self):
        """Set up the redesigned user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Quick Settings Bar (Top) ---
        quick_bar = QHBoxLayout()
        quick_bar.setSpacing(12)
        quick_bar.setContentsMargins(12, 12, 12, 6)

        # Mode dropdown
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Auto", "Download", "Generate"])
        self.mode_combo.setMinimumWidth(120)
        quick_bar.addWidget(QLabel("Mode:"))
        quick_bar.addWidget(self.mode_combo)

        # Search/Generate button
        self.search_btn = QPushButton("Search")
        self.search_btn.setMinimumWidth(100)
        quick_bar.addWidget(self.search_btn)

        # Language selection (list, not dropdown)
        quick_bar.addWidget(QLabel("Languages:"))
        self.language_list = QListWidget()
        self.language_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        languages = [
            "English", "Spanish", "French", "German", "Italian",
            "Portuguese", "Russian", "Japanese", "Korean", "Chinese",
            "Arabic", "Dutch", "Polish", "Swedish", "Turkish"
        ]
        for lang in languages:
            item = QListWidgetItem(lang)
            self.language_list.addItem(item)
            if lang == "English":
                item.setSelected(True)
        self.language_list.setMaximumHeight(60)
        self.language_list.setMaximumWidth(180)
        quick_bar.addWidget(self.language_list)

        # Providers selection (with All option)
        quick_bar.addWidget(QLabel("Providers:"))
        self.provider_list = QListWidget()
        self.provider_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        providers = ["All", "OpenSubtitles", "Addic7ed", "SubDL", "Subf2m", "YIFY Subtitles", "Podnapisi", "SubDivX", "Kitsunekko", "Jimaku"]
        for provider in providers:
            item = QListWidgetItem(provider)
            self.provider_list.addItem(item)
            if provider == "All":
                item.setSelected(True)
        self.provider_list.setMaximumHeight(60)
        self.provider_list.setMaximumWidth(180)
        quick_bar.addWidget(self.provider_list)

        # Whisper/OpenSubs status widgets
        self.whisper_status = QLabel("Whisper: Ready")
        self.opensubs_status = QLabel("OpenSubs: 0/5 downloads left")
        quick_bar.addWidget(self.whisper_status)
        quick_bar.addWidget(self.opensubs_status)

        quick_bar.addStretch()
        main_layout.addLayout(quick_bar)

        # --- Main Content Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: File list
        file_panel = QWidget()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(8, 0, 4, 0)
        file_layout.setSpacing(4)
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(1)
        self.file_table.setHorizontalHeaderLabels(["Files"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setMinimumWidth(200)
        file_layout.addWidget(self.file_table)
        file_panel.setMinimumWidth(220)
        splitter.addWidget(file_panel)

        # Center: Subtitles found for selected file
        subs_panel = QWidget()
        subs_layout = QVBoxLayout(subs_panel)
        subs_layout.setContentsMargins(4, 0, 4, 0)
        subs_layout.setSpacing(4)
        self.subs_table = QTableWidget()
        self.subs_table.setColumnCount(4)
        self.subs_table.setHorizontalHeaderLabels(["Language", "Provider", "Status", "Score"])
        self.subs_table.horizontalHeader().setStretchLastSection(True)
        self.subs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.subs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.subs_table.setAlternatingRowColors(True)
        self.subs_table.setMinimumWidth(320)
        subs_layout.addWidget(self.subs_table)
        subs_panel.setMinimumWidth(340)
        splitter.addWidget(subs_panel)

        # Right: Subtitle preview/info panel
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(4, 0, 8, 0)
        preview_layout.setSpacing(4)
        self.preview_label = QLabel("Subtitle Preview")
        self.preview_label.setObjectName("title_label")
        preview_layout.addWidget(self.preview_label)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Subtitle preview will appear here...")
        self.preview_text.setMinimumWidth(220)
        self.preview_text.setMaximumWidth(320)
        preview_layout.addWidget(self.preview_text)
        preview_panel.setMinimumWidth(240)
        splitter.addWidget(preview_panel)

        splitter.setSizes([220, 340, 240])
        main_layout.addWidget(splitter)

        # --- Bottom Bar: Apply/Batch Apply ---
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(12, 6, 12, 12)
        bottom_bar.setSpacing(12)
        self.apply_btn = QPushButton("Apply")
        self.batch_apply_btn = QPushButton("Batch Apply")
        self.apply_mode_combo = QComboBox()
        self.apply_mode_combo.addItems(["External File", "Embed in Video", "Burn-in"])
        self.apply_mode_combo.setMinimumWidth(120)
        bottom_bar.addWidget(self.apply_btn)
        bottom_bar.addWidget(self.batch_apply_btn)
        bottom_bar.addWidget(QLabel("Mode:"))
        bottom_bar.addWidget(self.apply_mode_combo)
        bottom_bar.addStretch()
        main_layout.addLayout(bottom_bar)

        # Connect signals for mode/provider/language changes
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.provider_list.itemSelectionChanged.connect(self._on_provider_changed)
        self.language_list.itemSelectionChanged.connect(self._on_language_changed)
        self.search_btn.clicked.connect(self._on_search_clicked)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        self.batch_apply_btn.clicked.connect(self._on_batch_apply_clicked)

        # Hide Add Files/Add Folder buttons (now only in sidebar)
        # Remove sync, encoding, format, and other legacy options

        # TODO: Implement logic for updating status widgets, populating tables, and auto-selecting best subtitles
    
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
        # All legacy buttons are removed; only connect signals for new UI if needed
        pass
    
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
        """Add file to the file list (left column)."""
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        item = QTableWidgetItem(file_path.name)
        item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        self.file_table.setItem(row, 0, item)
        self.file_table.resizeRowToContents(row)
        logger.info(f"Added file to file list: {file_path.name}")
    
    def _add_folder_to_table(self, folder_path: Path):
        """Add all video files from folder to file list."""
        count = 0
        for file_path in folder_path.rglob("*"):
            if file_path.is_file() and self._is_video_file(file_path):
                self._add_file_to_table(file_path)
                count += 1
        logger.info(f"Added {count} files from {folder_path}")
    
    def _remove_selected(self):
        """Remove selected rows from file list."""
        selected_rows = sorted(
            set(index.row() for index in self.file_table.selectedIndexes()),
            reverse=True
        )
        for row in selected_rows:
            self.file_table.removeRow(row)
    
    def _clear_all(self):
        """Clear all files from file list."""
        self.file_table.setRowCount(0)
    
    def _start_processing(self):
        """Start subtitle processing for all queued files."""
        logger.info("Starting subtitle processing")
        
        # Get selected files from file table
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item:
                file_path = Path(item.data(Qt.ItemDataRole.UserRole))
                self._process_file(row, file_path)
    
    def _process_file(self, row: int, file_path: Path):
        """Process a single file for subtitles."""
        logger.info(f"Processing subtitles for: {file_path.name}")
        
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
    
    def _get_subtitle_settings(self) -> Dict[str, Any]:
        """Get current subtitle settings as dictionary."""
        # Get selected languages
        languages = []
        if hasattr(self, 'language_list'):
            for i in range(self.language_list.count()):
                item = self.language_list.item(i)
                if item and item.isSelected():
                    # Map display name to language code
                    lang_map = {
                        'English': 'eng',
                        'Spanish': 'spa',
                        'French': 'fra',
                        'German': 'deu',
                        'Italian': 'ita',
                        'Portuguese': 'por',
                        'Japanese': 'jpn',
                        'Chinese': 'chi',
                        'Korean': 'kor',
                        'Arabic': 'ara'
                    }
                    languages.append(lang_map.get(item.text(), 'eng'))
        
        if not languages:
            languages = ['eng']  # Default to English
        
        # Get selected providers
        providers = []
        if hasattr(self, 'provider_list'):
            for i in range(self.provider_list.count()):
                item = self.provider_list.item(i)
                if item and item.isSelected() and item.text() != 'All':
                    providers.append(item.text().lower())
        
        # Get mode
        mode = 'auto'
        if hasattr(self, 'mode_combo'):
            mode = self.mode_combo.currentText().lower()
        
        # Get Whisper model if applicable
        whisper_model = 'base'
        if hasattr(self, 'model_combo'):
            whisper_model = self.model_combo.currentText().lower()
        
        return {
            'languages': languages,
            'providers': providers,
            'mode': mode,
            'whisper_model': whisper_model
        }
    
    def _on_subtitle_started(self, row: int, file_path: str):
        """Handle subtitle processing started."""
        self.subtitle_started.emit(file_path)
        logger.debug(f"Subtitle processing started for row {row}: {file_path}")
    
    def _on_subtitle_progress(self, row: int, current: int, total: int, message: str):
        """Handle subtitle processing progress."""
        self.subtitle_progress.emit("", current, total, message)
        logger.debug(f"Subtitle progress row {row}: {current}/{total} - {message}")
    
    def _on_subtitle_completed(self, row: int, file_path: str):
        """Handle subtitle processing completed."""
        self.subtitle_completed.emit(file_path)
        logger.info(f"Subtitle processing completed for: {file_path}")
        
        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        # Show notification
        self.notifier.show_notification(
            title="Subtitles Ready",
            message=f"Subtitles downloaded/generated for {Path(file_path).name}",
            notification_type="success"
        )
    
    def _on_subtitle_error(self, row: int, file_path: str, error: tuple):
        """Handle subtitle processing error."""
        error_msg = str(error[1]) if len(error) > 1 else "Unknown error"
        self.subtitle_error.emit(file_path, error_msg)
        logger.error(f"Subtitle processing error for {file_path}: {error_msg}")
        
        # Remove from active workers
        if file_path in self.active_workers:
            del self.active_workers[file_path]
        
        # Show notification
        self.notifier.show_notification(
            title="Subtitle Error",
            message=f"Failed to process subtitles for {Path(file_path).name}: {error_msg}",
            notification_type="error"
        )
    
    def _stop_processing(self):
        """Stop all subtitle processing."""
        logger.info("Stopping subtitle processing")
        
        for worker in self.active_workers.values():
            worker.stop()
        
        self.active_workers.clear()
    
    def _check_queue_complete(self):
        """Check if all subtitle processing is complete."""
        return len(self.active_workers) == 0
    
    def _load_preview(self):
        """Load subtitle preview for selected file."""
        # Get selected file
        selected_items = self.file_table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        item = self.file_table.item(row, 0)
        if not item:
            return
        
        file_path = Path(item.data(Qt.ItemDataRole.UserRole))
        
        # Look for subtitle files
        subtitle_files = list(file_path.parent.glob(f"{file_path.stem}*.srt"))
        subtitle_files.extend(list(file_path.parent.glob(f"{file_path.stem}*.ass")))
        subtitle_files.extend(list(file_path.parent.glob(f"{file_path.stem}*.vtt")))
        
        if subtitle_files and hasattr(self, 'preview_text'):
            # Load first subtitle file
            try:
                with open(subtitle_files[0], 'r', encoding='utf-8') as f:
                    content = f.read(5000)  # First 5000 chars
                    self.preview_text.setPlainText(content)
                    logger.info(f"Loaded subtitle preview: {subtitle_files[0].name}")
            except Exception as e:
                logger.error(f"Failed to load subtitle preview: {e}")
                self.preview_text.setPlainText(f"Error loading subtitle: {e}")
        elif hasattr(self, 'preview_text'):
            self.preview_text.setPlainText("No subtitle files found for this video.")
