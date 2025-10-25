"""
EncodeForge Renamer Tab
Metadata fetching, pattern-based renaming, and preview
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QPushButton, QProgressBar,
    QLabel, QComboBox, QGroupBox, QFormLayout, QCheckBox,
    QFileDialog, QHeaderView, QAbstractItemView, QTextEdit,
    QLineEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from utils.workers import RenamerWorker
from utils.notifications import get_notification_manager

logger = logging.getLogger(__name__)


class RenamerTab(QWidget):
    """
    Renamer tab for fetching metadata and renaming files.
    
    Signals:
        rename_started: Emitted when renaming begins
        rename_progress: Emitted with (file, current, total, message) during processing
        rename_completed: Emitted when renaming completes
        rename_error: Emitted with (file, error_message) on error
    """
    
    rename_started = Signal(str)  # file path
    rename_progress = Signal(str, int, int, str)  # file, current, total, message
    rename_completed = Signal(str)  # file path
    rename_error = Signal(str, str)  # file path, error message
    
    def __init__(self, thread_pool: QThreadPool, parent=None):
        """
        Initialize renamer tab.
        
        Args:
            thread_pool: QThreadPool for parallel processing
            parent: Parent widget
        """
        super().__init__(parent)
        self.thread_pool = thread_pool
        self.notifier = get_notification_manager()
        self.active_workers: Dict[str, RenamerWorker] = {}
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Apply macOS-inspired styling
        self.setStyleSheet("""
            /* Renamer Tab Styling */
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
            
            /* Secondary Buttons */
            QPushButton[secondary="true"] {
                background-color: #48484a;
            }
            
            QPushButton[secondary="true"]:hover {
                background-color: #5a5a5c;
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
            
            /* List Widgets */
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 4px;
            }
            
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                color: #ffffff;
            }
            
            QListWidget::item:selected {
                background-color: #0a84ff;
            }
            
            QListWidget::item:hover:!selected {
                background-color: rgba(255, 255, 255, 0.05);
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
            
            /* Line Edits */
            QLineEdit {
                background-color: #3a3a3c;
                border: 1px solid #48484a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            
            QLineEdit:hover {
                border-color: #0a84ff;
            }
            
            QLineEdit:focus {
                border-color: #0a84ff;
                border-width: 2px;
            }
            
            /* Text Edits */
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px;
                color: #ffffff;
                font-size: 12px;
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
        
        # Left panel: File list and preview
        left_panel = self._create_file_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Settings
        right_panel = self._create_settings_panel()
        splitter.addWidget(right_panel)
        
        # Set initial sizes (60/40 split)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
    
    def _create_file_panel(self) -> QWidget:
        """Create file list and preview panel."""
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
        
        # File table with preview
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels([
            "Current Name", "New Name", "Status"
        ])
        self.file_table.horizontalHeader().setStretchLastSection(False)
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.file_table.setAcceptDrops(True)
        
        # Enable drag and drop
        self.file_table.dragEnterEvent = self._drag_enter_event
        self.file_table.dropEvent = self._drop_event
        
        layout.addWidget(self.file_table)
        
        # Action buttons
        action_controls = QHBoxLayout()
        
        self.fetch_metadata_btn = QPushButton("Fetch Metadata")
        self.preview_btn = QPushButton("Preview Names")
        self.preview_btn.setEnabled(False)
        self.rename_btn = QPushButton("Apply Rename")
        self.rename_btn.setEnabled(False)
        
        action_controls.addWidget(self.fetch_metadata_btn)
        action_controls.addWidget(self.preview_btn)
        action_controls.addWidget(self.rename_btn)
        action_controls.addStretch()
        
        layout.addLayout(action_controls)
        
        return panel
    
    def _create_settings_panel(self) -> QWidget:
        """Create renaming settings panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Media type selection
        type_group = QGroupBox("Media Type")
        type_layout = QVBoxLayout()
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["TV Show", "Movie", "Anime"])
        type_layout.addWidget(self.type_combo)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Provider selection
        provider_group = QGroupBox("Metadata Provider")
        provider_layout = QVBoxLayout()
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "TMDB (The Movie Database)",
            "TVDB (TheTVDB)",
            "AniDB (Anime)",
            "Kitsu (Anime)",
            "Jikan (MyAnimeList)",
            "TVmaze",
            "Trakt",
            "OMDB"
        ])
        provider_layout.addWidget(self.provider_combo)
        
        # API Key input
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setStyleSheet("color: #8e8e93; font-size: 11px;")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter API key if required...")
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input)
        provider_layout.addLayout(api_key_layout)
        
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)
        
        # Pattern editor
        pattern_group = QGroupBox("Naming Pattern")
        pattern_layout = QVBoxLayout()
        
        pattern_help = QLabel("Available variables:")
        pattern_help.setStyleSheet("color: #8e8e93; font-size: 11px;")
        pattern_layout.addWidget(pattern_help)
        
        # Variable list
        variables_text = QTextEdit()
        variables_text.setReadOnly(True)
        variables_text.setMaximumHeight(120)
        variables_text.setPlainText(
            "{title} - Title\n"
            "{year} - Release year\n"
            "{season} - Season number (S01)\n"
            "{episode} - Episode number (E01)\n"
            "{resolution} - Video resolution\n"
            "{quality} - Quality (1080p, 720p)\n"
            "{codec} - Video codec\n"
            "{audio} - Audio codec\n"
            "{group} - Release group"
        )
        pattern_layout.addWidget(variables_text)
        
        # Pattern input
        self.pattern_input = QLineEdit()
        self.pattern_input.setText("{title} - {season}{episode} - {quality}")
        self.pattern_input.setPlaceholderText("Enter naming pattern...")
        pattern_layout.addWidget(self.pattern_input)
        
        # Preset patterns
        presets_label = QLabel("Presets:")
        presets_label.setStyleSheet("color: #8e8e93; font-size: 11px; margin-top: 8px;")
        pattern_layout.addWidget(presets_label)
        
        self.preset_list = QListWidget()
        self.preset_list.setMaximumHeight(150)
        presets = [
            "{title} {season}{episode}",
            "{title} - {season}{episode}",
            "{title} {year}",
            "{title} ({year})",
            "[{group}] {title} - {season}{episode}",
            "{title} {season}{episode} [{quality}]"
        ]
        for preset in presets:
            self.preset_list.addItem(preset)
        pattern_layout.addWidget(self.preset_list)
        
        pattern_group.setLayout(pattern_layout)
        layout.addWidget(pattern_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        
        self.replace_spaces_check = QCheckBox("Replace spaces with dots")
        self.lowercase_check = QCheckBox("Convert to lowercase")
        self.remove_special_check = QCheckBox("Remove special characters")
        self.preserve_extension_check = QCheckBox("Preserve file extension")
        self.preserve_extension_check.setChecked(True)
        
        options_layout.addWidget(self.replace_spaces_check)
        options_layout.addWidget(self.lowercase_check)
        options_layout.addWidget(self.remove_special_check)
        options_layout.addWidget(self.preserve_extension_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        layout.addStretch()
        
        return panel
    
    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_all)
        
        self.fetch_metadata_btn.clicked.connect(self._fetch_metadata)
        self.preview_btn.clicked.connect(self._preview_names)
        self.rename_btn.clicked.connect(self._apply_rename)
        
        # Pattern preset selection
        self.preset_list.itemClicked.connect(self._on_preset_selected)
    
    def _on_preset_selected(self, item: QListWidgetItem):
        """Handle pattern preset selection."""
        self.pattern_input.setText(item.text())
    
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
        """Add file to the renaming queue."""
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return
        
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        
        # Current name
        current_item = QTableWidgetItem(file_path.name)
        current_item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        self.file_table.setItem(row, 0, current_item)
        
        # New name (empty initially)
        self.file_table.setItem(row, 1, QTableWidgetItem(""))
        
        # Status
        self.file_table.setItem(row, 2, QTableWidgetItem("Ready"))
        
        logger.info(f"Added file to renaming queue: {file_path.name}")
    
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
    
    def _clear_all(self):
        """Clear all files from table."""
        self.file_table.setRowCount(0)
        self.preview_btn.setEnabled(False)
        self.rename_btn.setEnabled(False)
    
    def _fetch_metadata(self):
        """Fetch metadata for all files in queue."""
        if self.file_table.rowCount() == 0:
            return
        
        # TODO: Implement metadata fetching
        # For now, just enable preview
        self.preview_btn.setEnabled(True)
        logger.info("Metadata fetch requested (not yet implemented)")
    
    def _preview_names(self):
        """Preview new names based on pattern."""
        pattern = self.pattern_input.text()
        
        for row in range(self.file_table.rowCount()):
            current_item = self.file_table.item(row, 0)
            file_path = Path(current_item.data(Qt.ItemDataRole.UserRole))
            
            # Generate new name (simplified - will be enhanced with real metadata)
            new_name = self._generate_new_name(file_path, pattern)
            
            self.file_table.item(row, 1).setText(new_name)
            self.file_table.item(row, 2).setText("Preview")
        
        self.rename_btn.setEnabled(True)
        logger.info("Generated name previews")
    
    def _generate_new_name(self, file_path: Path, pattern: str) -> str:
        """
        Generate new filename based on pattern.
        
        This is a simplified version - will be enhanced with real metadata.
        """
        # Extract basic info from current filename
        name = file_path.stem
        ext = file_path.suffix
        
        # Simple pattern replacement (will be enhanced)
        new_name = pattern
        new_name = new_name.replace("{title}", name)
        new_name = new_name.replace("{season}", "S01")
        new_name = new_name.replace("{episode}", "E01")
        new_name = new_name.replace("{quality}", "1080p")
        new_name = new_name.replace("{year}", "2024")
        new_name = new_name.replace("{codec}", "x264")
        new_name = new_name.replace("{audio}", "AAC")
        new_name = new_name.replace("{group}", "EncodeForge")
        new_name = new_name.replace("{resolution}", "1920x1080")
        
        # Apply options
        if self.replace_spaces_check.isChecked():
            new_name = new_name.replace(" ", ".")
        
        if self.lowercase_check.isChecked():
            new_name = new_name.lower()
        
        if self.remove_special_check.isChecked():
            # Keep only alphanumeric, dots, dashes, underscores
            new_name = "".join(c for c in new_name if c.isalnum() or c in ".-_ ")
        
        # Add extension
        if self.preserve_extension_check.isChecked():
            new_name += ext
        
        return new_name
    
    def _apply_rename(self):
        """Apply the rename operation to all files."""
        renamed_count = 0
        error_count = 0
        
        for row in range(self.file_table.rowCount()):
            current_item = self.file_table.item(row, 0)
            new_name_item = self.file_table.item(row, 1)
            
            if not new_name_item.text():
                continue
            
            file_path = Path(current_item.data(Qt.ItemDataRole.UserRole))
            new_name = new_name_item.text()
            new_path = file_path.parent / new_name
            
            try:
                file_path.rename(new_path)
                self.file_table.item(row, 2).setText("Renamed")
                current_item.setText(new_name)
                current_item.setData(Qt.ItemDataRole.UserRole, str(new_path))
                renamed_count += 1
                logger.info(f"Renamed: {file_path.name} -> {new_name}")
            except Exception as e:
                self.file_table.item(row, 2).setText(f"Error: {str(e)}")
                error_count += 1
                logger.error(f"Failed to rename {file_path.name}: {e}")
        
        # Update status
        if renamed_count > 0:
            self.rename_completed.emit(f"{renamed_count} files")
            logger.info(f"Batch rename complete: {renamed_count} files, {error_count} errors")
        
        self.rename_btn.setEnabled(False)
