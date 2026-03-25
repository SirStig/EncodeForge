"""
EncodeForge Metadata Tab
Metadata fetching, pattern-based renaming, and preview
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
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidgetItem,
    QTextEdit,
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
    StyledLineEdit,
    StyledTextEdit,
)
from utils.notifications import get_notification_manager
from utils.workers import RenamerWorker

logger = logging.getLogger(__name__)

class MetadataTab(QWidget):
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
        super().__init__(parent)
        self.thread_pool = thread_pool
        self.notifier = get_notification_manager()
        self.active_workers: Dict[str, RenamerWorker] = {}
        self._setup_ui()
        self._connect_signals()
        logger.debug("Metadata tab initialized - using base glassmorphism theme")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # --- Top bar: all controls and settings ---
        top_bar = QHBoxLayout()
        from PySide6.QtWidgets import QStyle
        
        # File management buttons
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        top_bar.addWidget(self.remove_btn)
        top_bar.addWidget(self.clear_btn)
        
        # Provider selection
        top_bar.addWidget(StyledLabel("Provider:"))
        self.provider_combo = StyledComboBox()
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
        top_bar.addWidget(self.provider_combo)
        
        # Language selection
        top_bar.addWidget(StyledLabel("Language:"))
        self.language_combo = StyledComboBox()
        self.language_combo.addItems(["English", "Japanese", "Spanish", "French", "German", "Other"])
        top_bar.addWidget(self.language_combo)
        
        # API Key input
        top_bar.addWidget(StyledLabel("API Key:"))
        self.api_key_input = StyledLineEdit()
        self.api_key_input.setPlaceholderText("API Key (if required)")
        top_bar.addWidget(self.api_key_input)
        
        # Pattern input
        top_bar.addWidget(StyledLabel("Pattern:"))
        self.pattern_input = StyledLineEdit()
        self.pattern_input.setPlaceholderText("Naming pattern, e.g. {title} - {season}{episode}")
        self.pattern_input.setText("{title} - {season}{episode} - {quality}")
        top_bar.addWidget(self.pattern_input)
        
        # Options checkboxes
        self.replace_spaces_check = StyledCheckBox("Dots for spaces")
        self.lowercase_check = StyledCheckBox("Lowercase")
        self.remove_special_check = StyledCheckBox("No special chars")
        self.preserve_extension_check = StyledCheckBox("Keep extension")
        self.preserve_extension_check.setChecked(True)
        top_bar.addWidget(self.replace_spaces_check)
        top_bar.addWidget(self.lowercase_check)
        top_bar.addWidget(self.remove_special_check)
        top_bar.addWidget(self.preserve_extension_check)
        
        # Action buttons
        self.fetch_metadata_btn = QPushButton("Fetch Metadata")
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setEnabled(False)
        self.rename_btn = QPushButton("Apply Rename")
        self.rename_btn.setEnabled(False)
        top_bar.addWidget(self.fetch_metadata_btn)
        top_bar.addWidget(self.preview_btn)
        top_bar.addWidget(self.rename_btn)
        top_bar.addStretch()
        
        main_layout.addLayout(top_bar)

        # --- Comparison lists ---
        self.comparison_layout = QHBoxLayout()
        self.file_table = AutoResizeTable()
        self.file_table.setColumns(headers=["Input Files"])  # Single column auto-stretches
        self.file_table.enableDragDrop(self._drag_enter_event, self._drop_event)
        self.comparison_layout.addWidget(self.file_table, 1)  # Add stretch factor
        
        self.metadata_table = AutoResizeTable()
        self.metadata_table.setColumns(headers=["Metadata Result"])  # Single column auto-stretches
        self.metadata_table.setAlternatingRowColors(True)
        self.comparison_layout.addWidget(self.metadata_table, 1)  # Add stretch factor
        main_layout.addLayout(self.comparison_layout, 1)  # Give whole layout stretch

        # --- Preview panel below comparison lists ---
        self.preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(self.preview_group)
        self.preview_text = StyledTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Select a file to see details or preview output here.")
        preview_layout.addWidget(self.preview_text)
        main_layout.addWidget(self.preview_group, 0)  # No stretch for preview

        # Connect selection change to update preview
        self.file_table.itemSelectionChanged.connect(self._update_preview_panel)
        self.metadata_table.itemSelectionChanged.connect(self._update_preview_panel)

    def _update_preview_panel(self):
        # Show details for selected file or metadata
        file_row = self.file_table.currentRow()
        meta_row = self.metadata_table.currentRow()
        text = ""
        if file_row >= 0:
            file_item = self.file_table.item(file_row, 0)
            if file_item:
                text += f"Original: {file_item.text()}\n"
        if meta_row >= 0:
            meta_item = self.metadata_table.item(meta_row, 0)
            if meta_item:
                text += f"Suggested: {meta_item.text()}\n"
        if not text:
            text = "Select a file to see details or preview output here."
        self.preview_text.setPlainText(text)

    def _create_settings_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        type_group = QGroupBox("Media Type")
        type_layout = QVBoxLayout()
        self.type_combo = StyledComboBox()
        self.type_combo.addItems(["TV Show", "Movie", "Anime"])
        type_layout.addWidget(self.type_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        provider_group = QGroupBox("Metadata Provider")
        provider_layout = QVBoxLayout()
        self.provider_combo = StyledComboBox()
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
        api_key_layout = QHBoxLayout()
        api_key_label = StyledLabel("API Key:")
        api_key_label.setObjectName("api_key_label")
        self.api_key_input = StyledLineEdit()
        self.api_key_input.setPlaceholderText("Enter API key if required...")
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input)
        provider_layout.addLayout(api_key_layout)
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)
        pattern_group = QGroupBox("Naming Pattern")
        pattern_layout = QVBoxLayout()
        pattern_help = StyledLabel("Available variables:")
        pattern_help.setObjectName("pattern_help")
        pattern_layout.addWidget(pattern_help)
        variables_text = StyledTextEdit()
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
        self.pattern_input = StyledLineEdit()
        self.pattern_input.setText("{title} - {season}{episode} - {quality}")
        self.pattern_input.setPlaceholderText("Enter naming pattern...")
        pattern_layout.addWidget(self.pattern_input)
        presets_label = StyledLabel("Presets:")
        presets_label.setObjectName("presets_label")
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
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()
        self.replace_spaces_check = StyledCheckBox("Replace spaces with dots")
        self.lowercase_check = StyledCheckBox("Convert to lowercase")
        self.remove_special_check = StyledCheckBox("Remove special characters")
        self.preserve_extension_check = StyledCheckBox("Preserve file extension")
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
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_all)
        self.fetch_metadata_btn.clicked.connect(self._fetch_metadata)
        self.preview_btn.clicked.connect(self._preview_names)
        self.rename_btn.clicked.connect(self._apply_rename)
        # Only connect preset_list if it exists (for future pattern dialog)
        if hasattr(self, 'preset_list'):
            self.preset_list.itemClicked.connect(self._on_preset_selected)

    def _on_preset_selected(self, item: QListWidgetItem):
        self.pattern_input.setText(item.text())

    def _drag_enter_event(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            file_path = Path(url.toLocalFile())
            if file_path.is_file() and self._is_video_file(file_path):
                self._add_file_to_table(file_path)
            elif file_path.is_dir():
                self._add_folder_to_table(file_path)
        event.acceptProposedAction()

    def _is_video_file(self, file_path: Path) -> bool:
        video_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
            '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'
        }
        return file_path.suffix.lower() in video_extensions

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v);;All Files (*.*)"
        )
        for file in files:
            self._add_file_to_table(Path(file))

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder"
        )
        if folder:
            self._add_folder_to_table(Path(folder))

    def _add_file_to_table(self, file_path: Path):
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        item = QTableWidgetItem(file_path.name)
        item.setData(Qt.ItemDataRole.UserRole, str(file_path))
        self.file_table.setItem(row, 0, item)
        logger.info(f"Added file to renaming queue: {file_path.name}")

    def _add_folder_to_table(self, folder_path: Path):
        count = 0
        for file_path in folder_path.rglob("*"):
            if file_path.is_file() and self._is_video_file(file_path):
                self._add_file_to_table(file_path)
                count += 1
        logger.info(f"Added {count} files from {folder_path}")

    def _remove_selected(self):
        selected_rows = sorted(
            set(index.row() for index in self.file_table.selectedIndexes()),
            reverse=True
        )
        for row in selected_rows:
            self.file_table.removeRow(row)

    def _clear_all(self):
        self.file_table.setRowCount(0)
        self.metadata_table.setRowCount(0)
        self.preview_btn.setEnabled(False)
        self.rename_btn.setEnabled(False)

    def _fetch_metadata(self):
        """Fetch metadata for all files in the list."""
        if self.file_table.rowCount() == 0:
            logger.warning("No files to fetch metadata for")
            return
        
        logger.info("Fetching metadata for files")
        
        # Clear metadata table
        self.metadata_table.setRowCount(0)
        
        # Get provider and settings
        provider = self._get_selected_provider()
        api_key = self.api_key_input.text() if hasattr(self, 'api_key_input') else ""
        
        # Process each file
        for row in range(self.file_table.rowCount()):
            file_item = self.file_table.item(row, 0)
            if not file_item:
                continue
            
            file_path = Path(file_item.data(Qt.ItemDataRole.UserRole))
            
            # Use RenamerWorker to fetch metadata
            settings = {
                'provider': provider,
                'api_key': api_key,
                'dry_run': True,  # Just fetch, don't rename yet
                'pattern': self.pattern_input.text() if hasattr(self, 'pattern_input') else '{title} - {season}{episode}'
            }
            
            worker = RenamerWorker(file_path, settings)
            
            # Connect signals
            worker.signals.result.connect(
                lambda result, r=row: self._on_metadata_fetched(r, result)
            )
            worker.signals.error.connect(
                lambda error, r=row: self._on_metadata_error(r, error)
            )
            
            # Track worker
            self.active_workers[str(file_path)] = worker
            
            # Start worker
            self.thread_pool.start(worker)
        
        self.preview_btn.setEnabled(True)
        logger.info("Metadata fetch initiated")
    
    def _on_metadata_fetched(self, row: int, result: Dict[str, Any]):
        """Handle metadata fetch result."""
        logger.debug(f"Metadata fetched for row {row}: {result}")
        
        # Add to metadata table
        meta_row = self.metadata_table.rowCount()
        self.metadata_table.insertRow(meta_row)
        
        # Format metadata result
        if isinstance(result, dict):
            # Extract useful info
            title = result.get('title', 'Unknown')
            year = result.get('year', '')
            season = result.get('season', '')
            episode = result.get('episode', '')
            
            meta_text = f"{title}"
            if year:
                meta_text += f" ({year})"
            if season and episode:
                meta_text += f" - S{season:02d}E{episode:02d}"
            
            meta_item = QTableWidgetItem(meta_text)
            meta_item.setData(Qt.ItemDataRole.UserRole, result)
        else:
            meta_item = QTableWidgetItem(str(result))
        
        self.metadata_table.setItem(meta_row, 0, meta_item)
    
    def _on_metadata_error(self, row: int, error: tuple):
        """Handle metadata fetch error."""
        error_msg = str(error[1]) if len(error) > 1 else "Unknown error"
        logger.error(f"Metadata fetch error for row {row}: {error_msg}")
        
        # Add error to metadata table
        meta_row = self.metadata_table.rowCount()
        self.metadata_table.insertRow(meta_row)
        meta_item = QTableWidgetItem(f"Error: {error_msg}")
        self.metadata_table.setItem(meta_row, 0, meta_item)
    
    def _get_selected_provider(self) -> str:
        """Get the currently selected metadata provider."""
        if hasattr(self, 'provider_combo'):
            provider_text = self.provider_combo.currentText()
            # Map display names to provider keys
            provider_map = {
                'TMDB (The Movie Database)': 'tmdb',
                'TVDB (TheTVDB)': 'tvdb',
                'AniDB (Anime)': 'anidb',
                'Kitsu (Anime)': 'kitsu',
                'Jikan (MyAnimeList)': 'jikan',
                'TVmaze': 'tvmaze',
                'Trakt': 'trakt',
                'OMDB': 'omdb'
            }
            return provider_map.get(provider_text, 'tmdb')
        return 'tmdb'

    def _preview_names(self):
        pattern = self.pattern_input.text()
        self.metadata_table.setRowCount(0)
        for row in range(self.file_table.rowCount()):
            file_item = self.file_table.item(row, 0)
            if file_item:
                file_path = Path(file_item.data(Qt.ItemDataRole.UserRole))
                new_name = self._generate_new_name(file_path, pattern)
                meta_row = self.metadata_table.rowCount()
                self.metadata_table.insertRow(meta_row)
                meta_item = QTableWidgetItem(new_name)
                self.metadata_table.setItem(meta_row, 0, meta_item)
        self.rename_btn.setEnabled(True)
        logger.info("Generated name previews")

    def _generate_new_name(self, file_path: Path, pattern: str) -> str:
        name = file_path.stem
        ext = file_path.suffix
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
        if self.replace_spaces_check.isChecked():
            new_name = new_name.replace(" ", ".")
        if self.lowercase_check.isChecked():
            new_name = new_name.lower()
        if self.remove_special_check.isChecked():
            new_name = "".join(c for c in new_name if c.isalnum() or c in ".-_ ")
        if self.preserve_extension_check.isChecked():
            new_name += ext
        return new_name

    def _apply_rename(self):
        """Apply renaming to all files based on metadata."""
        if self.file_table.rowCount() == 0:
            logger.warning("No files to rename")
            return
        
        logger.info("Applying renames to files")
        
        # Get settings
        provider = self._get_selected_provider()
        api_key = self.api_key_input.text() if hasattr(self, 'api_key_input') else ""
        pattern = self.pattern_input.text() if hasattr(self, 'pattern_input') else '{title} - {season}{episode}'
        
        renamed_count = 0
        error_count = 0
        
        # Process each file
        for row in range(self.file_table.rowCount()):
            file_item = self.file_table.item(row, 0)
            if not file_item:
                continue
            
            file_path = Path(file_item.data(Qt.ItemDataRole.UserRole))
            
            # Check if we have metadata for this file
            meta_item = None
            if row < self.metadata_table.rowCount():
                meta_item = self.metadata_table.item(row, 0)
            
            if not meta_item or meta_item.text().startswith("Error:"):
                logger.warning(f"Skipping {file_path.name}: No valid metadata")
                continue
            
            # Get metadata
            metadata = meta_item.data(Qt.ItemDataRole.UserRole) if meta_item else {}
            
            # Generate new name using metadata and pattern
            new_name = self._apply_pattern(file_path, pattern, metadata)
            
            # Apply transformations
            if hasattr(self, 'replace_spaces_check') and self.replace_spaces_check.isChecked():
                new_name = new_name.replace(" ", ".")
            if hasattr(self, 'lowercase_check') and self.lowercase_check.isChecked():
                new_name = new_name.lower()
            if hasattr(self, 'remove_special_check') and self.remove_special_check.isChecked():
                new_name = "".join(c for c in new_name if c.isalnum() or c in ".-_ ")
            
            # Preserve extension
            if hasattr(self, 'preserve_extension_check') and self.preserve_extension_check.isChecked():
                new_name += file_path.suffix
            
            # Try to rename
            new_path = file_path.parent / new_name
            try:
                if new_path != file_path:
                    file_path.rename(new_path)
                    file_item.setText(new_name)
                    file_item.setData(Qt.ItemDataRole.UserRole, str(new_path))
                    meta_item.setText(f"✓ Renamed: {new_name}")
                    renamed_count += 1
                    logger.info(f"Renamed: {file_path.name} → {new_name}")
                else:
                    logger.debug(f"Skipped: {file_path.name} (same name)")
            except Exception as e:
                if meta_item:
                    meta_item.setText(f"✗ Error: {str(e)}")
                error_count += 1
                logger.error(f"Failed to rename {file_path.name}: {e}")
        
        # Show notification
        if renamed_count > 0:
            self.rename_completed.emit(f"{renamed_count} files")
            self.notifier.show_notification(
                title="Renaming Complete",
                message=f"Renamed {renamed_count} files ({error_count} errors)",
                notification_type="success" if error_count == 0 else "warning"
            )
            logger.info(f"Batch rename complete: {renamed_count} files, {error_count} errors")
        
        self.rename_btn.setEnabled(False)
    
    def _apply_pattern(self, file_path: Path, pattern: str, metadata: Dict[str, Any]) -> str:
        """Apply naming pattern with metadata."""
        result = pattern
        
        # Replace pattern variables with metadata values
        replacements = {
            '{title}': metadata.get('title', file_path.stem),
            '{year}': str(metadata.get('year', '')),
            '{season}': f"S{metadata.get('season', 1):02d}",
            '{episode}': f"E{metadata.get('episode', 1):02d}",
            '{quality}': metadata.get('quality', '1080p'),
            '{codec}': metadata.get('codec', 'x264'),
            '{audio}': metadata.get('audio', 'AAC'),
            '{group}': metadata.get('group', 'EncodeForge'),
            '{resolution}': metadata.get('resolution', '1920x1080'),
        }
        
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result
