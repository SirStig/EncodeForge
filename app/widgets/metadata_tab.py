"""
EncodeForge Metadata Tab
Metadata fetching and pattern-based renaming
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.dialogs.rename_pattern_dialog import RenamePatternDialog
from app.widgets.custom_widgets import (
    AutoResizeTable,
    StyledCheckBox,
    StyledComboBox,
    StyledLabel,
    StyledLineEdit,
)
from core.rename_pattern import apply_filename_options, format_filename_stem
from utils.notifications import get_notification_manager
from utils.settings_manager import get_settings_manager
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
        self._rename_history: Dict[str, str] = {}
        self._setup_ui()
        self._connect_signals()
        sm = get_settings_manager()
        self.pattern_input.setText(sm.renamer.pattern)
        self.refresh_providers()
        logger.debug("Metadata tab initialized - using base glassmorphism theme")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("encoder_toolbar")
        toolbar_main = QVBoxLayout(toolbar_widget)
        toolbar_main.setContentsMargins(0, 0, 0, 0)
        toolbar_main.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(10, 5, 10, 6)
        inner_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        self.fetch_metadata_btn = QPushButton("Fetch Metadata")
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setEnabled(False)
        self.rename_btn = QPushButton("Apply Rename")
        self.rename_btn.setEnabled(False)
        self.undo_btn = QPushButton("Undo Rename")
        self.undo_btn.setEnabled(False)
        btn_row.addWidget(self.fetch_metadata_btn)
        btn_row.addWidget(self.preview_btn)
        btn_row.addWidget(self.rename_btn)
        btn_row.addWidget(self.undo_btn)
        inner_layout.addLayout(btn_row)

        align_right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.addWidget(StyledLabel("Provider:"), 0, 0, align_right)
        self.provider_combo = StyledComboBox()
        self.provider_combo.setMinimumContentsLength(26)
        grid.addWidget(self.provider_combo, 0, 1)
        grid.addWidget(StyledLabel("Language:"), 0, 2, align_right)
        self.language_combo = StyledComboBox()
        self.language_combo.addItems(["English", "Japanese", "Spanish", "French", "German", "Other"])
        self.language_combo.setMinimumContentsLength(10)
        grid.addWidget(self.language_combo, 0, 3)
        grid.addWidget(StyledLabel("Pattern:"), 2, 0, align_right)
        pat_row = QHBoxLayout()
        self.pattern_input = StyledLineEdit()
        self.pattern_input.setPlaceholderText("{title} - S{season:02d}E{episode:02d} - {episode_title}")
        self.pattern_btn = QPushButton("Format / Templates…")
        self.pattern_btn.setToolTip("Edit pattern, built-in templates, and saved custom templates.")
        pat_row.addWidget(self.pattern_input, 1)
        pat_row.addWidget(self.pattern_btn)
        grid.addLayout(pat_row, 2, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        inner_layout.addLayout(grid)

        self.replace_spaces_check = StyledCheckBox("Dots for spaces")
        self.lowercase_check = StyledCheckBox("Lowercase")
        self.remove_special_check = StyledCheckBox("No special chars")
        self.preserve_extension_check = StyledCheckBox("Keep extension")
        self.preserve_extension_check.setChecked(True)
        chk_row = QHBoxLayout()
        chk_row.setSpacing(12)
        chk_row.addWidget(self.replace_spaces_check)
        chk_row.addWidget(self.lowercase_check)
        chk_row.addWidget(self.remove_special_check)
        chk_row.addWidget(self.preserve_extension_check)
        chk_row.addStretch()
        inner_layout.addLayout(chk_row)

        scroll.setWidget(inner)
        toolbar_main.addWidget(scroll)
        main_layout.addWidget(toolbar_widget)

        # --- Content area ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

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
        content_layout.addLayout(self.comparison_layout, 1)

        main_layout.addWidget(content_widget, 1)

    def _open_pattern_dialog(self) -> None:
        dlg = RenamePatternDialog(self, self.pattern_input.text())
        if dlg.exec():
            pat = dlg.selected_pattern()
            self.pattern_input.setText(pat)
            sm = get_settings_manager()
            sm.renamer.pattern = pat
            sm.save()

    def _connect_signals(self):
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_all)
        self.fetch_metadata_btn.clicked.connect(self._fetch_metadata)
        self.preview_btn.clicked.connect(self._preview_names)
        self.rename_btn.clicked.connect(self._apply_rename)
        self.undo_btn.clicked.connect(self._undo_rename)
        self.pattern_btn.clicked.connect(self._open_pattern_dialog)
        self.pattern_input.editingFinished.connect(self._persist_pattern_from_field)

    def _persist_pattern_from_field(self) -> None:
        sm = get_settings_manager()
        t = self.pattern_input.text().strip()
        if t and t != sm.renamer.pattern:
            sm.renamer.pattern = t
            sm.save()

    def _undo_rename(self):
        """Undo the last batch of renames."""
        if not self._rename_history:
            return
        errors = 0
        for new_path_str, original_path_str in list(self._rename_history.items()):
            try:
                new_path = Path(new_path_str)
                original_path = Path(original_path_str)
                if new_path.exists():
                    new_path.rename(original_path)
                    logger.info(f"Undid rename: {new_path.name} → {original_path.name}")
            except Exception as e:
                errors += 1
                logger.error(f"Failed to undo rename: {e}")
        self._rename_history.clear()
        self.undo_btn.setEnabled(False)
        if errors == 0:
            self.notifier.show_notification(title="Undo Complete", message="Renames undone successfully", notification_type="success")

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
        
        n = self.file_table.rowCount()
        self.metadata_table.setRowCount(n)
        for i in range(n):
            self.metadata_table.setItem(i, 0, QTableWidgetItem("Fetching…"))

        provider = self._get_selected_provider()
        api_key = ""

        for row in range(n):
            file_item = self.file_table.item(row, 0)
            if not file_item:
                continue
            
            file_path = Path(file_item.data(Qt.ItemDataRole.UserRole))
            
            # Use RenamerWorker to fetch metadata
            settings = {
                'provider': provider,
                'api_key': api_key,
                'preview_only': True,
                'pattern': self.pattern_input.text() if hasattr(self, 'pattern_input') else ''
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
        if row < 0 or row >= self.metadata_table.rowCount():
            return

        meta_dict: Dict[str, Any] = {}
        if isinstance(result, dict) and result.get("status") == "success":
            md = result.get("metadata") or []
            if md and isinstance(md[0], dict):
                meta_dict = md[0]

        if isinstance(result, dict) and result.get("status") == "success" and not meta_dict:
            self.metadata_table.setItem(row, 0, QTableWidgetItem("No metadata found"))
            return

        if isinstance(result, dict) and meta_dict:
            file_item = self.file_table.item(row, 0)
            fp = Path(file_item.data(Qt.ItemDataRole.UserRole)) if file_item else None
            stem = fp.stem if fp else ""
            pat = self.pattern_input.text().strip()
            preview = format_filename_stem(meta_dict, pat, file_stem=stem) if pat else None
            if preview:
                preview = apply_filename_options(
                    preview,
                    replace_spaces=self.replace_spaces_check.isChecked(),
                    lowercase=self.lowercase_check.isChecked(),
                    remove_special=self.remove_special_check.isChecked(),
                )
                ext = fp.suffix if fp and self.preserve_extension_check.isChecked() else ""
                meta_text = f"{preview}{ext}"
            else:
                meta_text = self._metadata_fallback_label(meta_dict)
            meta_item = QTableWidgetItem(meta_text)
            meta_item.setData(Qt.ItemDataRole.UserRole, meta_dict)
            self.metadata_table.setItem(row, 0, meta_item)
        elif isinstance(result, dict) and result.get("status") == "error":
            self.metadata_table.setItem(
                row, 0, QTableWidgetItem(f"Error: {result.get('message', 'unknown')}")
            )
        else:
            self.metadata_table.setItem(row, 0, QTableWidgetItem(str(result)))
    
    def _on_metadata_error(self, row: int, error: tuple):
        """Handle metadata fetch error."""
        error_msg = str(error[1]) if len(error) > 1 else "Unknown error"
        logger.error(f"Metadata fetch error for row {row}: {error_msg}")
        if 0 <= row < self.metadata_table.rowCount():
            self.metadata_table.setItem(row, 0, QTableWidgetItem(f"Error: {error_msg}"))

    @staticmethod
    def _metadata_fallback_label(meta_dict: Dict[str, Any]) -> str:
        title = meta_dict.get("show_title") or meta_dict.get("title", "Unknown")
        year = meta_dict.get("year", "") or meta_dict.get("show_year", "")
        season = meta_dict.get("season", "")
        episode = meta_dict.get("episode", "")
        parts = [title]
        if year:
            parts.append(f"({year})")
        try:
            if season != "" and episode != "":
                parts.append(f"S{int(season):02d}E{int(episode):02d}")
        except (TypeError, ValueError):
            if season and episode:
                parts.append(f"S{season}E{episode}")
        return " ".join(parts)
    
    def refresh_providers(self) -> None:
        """Rebuild the provider combo from current settings."""
        sm = get_settings_manager()
        c = sm.conversion

        self.provider_combo.blockSignals(True)
        current = self.provider_combo.currentData() or sm.renamer.provider or "auto"
        self.provider_combo.clear()

        self.provider_combo.addItem("Auto (Best Match)", "auto")
        self.provider_combo.addItem("All Providers", "all")
        self.provider_combo.insertSeparator(self.provider_combo.count())
        self.provider_combo.addItem("TVmaze  (free)", "tvmaze")
        self.provider_combo.addItem("AniDB  (free)", "anidb")
        self.provider_combo.addItem("Kitsu  (free)", "kitsu")
        self.provider_combo.addItem("Jikan / MyAnimeList  (free)", "jikan")

        keyed = [
            (getattr(c, "tmdb_api_key", ""), "TMDB (The Movie Database)", "tmdb"),
            (getattr(c, "tvdb_api_key", ""), "TVDB (TheTVDB)", "tvdb"),
            (getattr(c, "omdb_api_key", ""), "OMDb", "omdb"),
            (getattr(c, "trakt_api_key", ""), "Trakt", "trakt"),
        ]
        has_keyed = any(k.strip() for k, _, _ in keyed)
        if has_keyed:
            self.provider_combo.insertSeparator(self.provider_combo.count())
            for key, label, data in keyed:
                if key and key.strip():
                    self.provider_combo.addItem(label, data)

        idx = self.provider_combo.findData(current)
        self.provider_combo.setCurrentIndex(max(0, idx))
        self.provider_combo.blockSignals(False)

    def _get_selected_provider(self) -> str:
        return self.provider_combo.currentData() or "auto"

    def _preview_names(self):
        pattern = self.pattern_input.text()
        n = self.file_table.rowCount()
        self.metadata_table.setRowCount(n)
        for row in range(n):
            file_item = self.file_table.item(row, 0)
            if not file_item:
                continue

            file_path = Path(file_item.data(Qt.ItemDataRole.UserRole))

            # Reuse the metadata fetched earlier instead of discarding it.
            # Replacing the cell with a bare item dropped the UserRole payload
            # that _apply_rename requires, so Fetch → Preview → Apply renamed
            # nothing at all and reported no error.
            existing = self.metadata_table.item(row, 0)
            metadata = existing.data(Qt.ItemDataRole.UserRole) if existing else None

            new_name = self._generate_new_name(file_path, pattern, metadata)
            preview_item = QTableWidgetItem(new_name)
            if metadata is not None:
                preview_item.setData(Qt.ItemDataRole.UserRole, metadata)
            self.metadata_table.setItem(row, 0, preview_item)

        self.rename_btn.setEnabled(True)
        logger.info("Generated name previews")

    def _generate_new_name(self, file_path: Path, pattern: str, metadata: Optional[dict] = None) -> str:
        ext = file_path.suffix
        stem = format_filename_stem(metadata, pattern, file_stem=file_path.stem) or file_path.stem
        stem = apply_filename_options(
            stem,
            replace_spaces=self.replace_spaces_check.isChecked(),
            lowercase=self.lowercase_check.isChecked(),
            remove_special=self.remove_special_check.isChecked(),
        )
        if self.preserve_extension_check.isChecked():
            return f"{stem}{ext}"
        return stem

    def _apply_rename(self):
        """Apply renaming to all files based on metadata."""
        if self.file_table.rowCount() == 0:
            logger.warning("No files to rename")
            return
        
        logger.info("Applying renames to files")
        
        # Get settings
        provider = self._get_selected_provider()
        api_key = ""
        pattern = self.pattern_input.text() if hasattr(self, 'pattern_input') else ''
        
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

            metadata = meta_item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(metadata, dict) or not metadata:
                logger.warning(f"Skipping {file_path.name}: No structured metadata for rename")
                continue

            new_name = self._generate_new_name(file_path, pattern, metadata)

            # Try to rename
            new_path = file_path.parent / new_name
            try:
                if new_path != file_path:
                    self._rename_history[str(new_path)] = str(file_path)
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
            self.undo_btn.setEnabled(True)
            self.rename_completed.emit(f"{renamed_count} files")
            self.notifier.show_notification(
                title="Renaming Complete",
                message=f"Renamed {renamed_count} files ({error_count} errors)",
                notification_type="success" if error_count == 0 else "warning"
            )
            logger.info(f"Batch rename complete: {renamed_count} files, {error_count} errors")

        self.rename_btn.setEnabled(False)
