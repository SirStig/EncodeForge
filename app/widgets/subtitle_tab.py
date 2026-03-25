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
    QGridLayout,
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
    StyledCheckBox,
    StyledComboBox,
    StyledLabel,
    StyledTextEdit,
)
from utils.notifications import get_notification_manager
from utils.workers import SubtitleWorker, Worker, _subtitle_core_from_settings

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
        self._splitter_initialized = False

        self._setup_ui()
        self._connect_signals()
        self._update_whisper_status()
        logger.debug("Subtitle tab initialized - using base glassmorphism theme")

    def showEvent(self, event):
        super().showEvent(event)
        if self._splitter_initialized:
            return
        total = self.width()
        if total > 0 and hasattr(self, "_main_splitter"):
            self._main_splitter.setSizes(
                [
                    int(total * 0.26),
                    int(total * 0.44),
                    int(total * 0.30),
                ]
            )
            self._splitter_initialized = True
    
    def _setup_ui(self):
        """Set up the redesigned user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Quick Settings Bar (Top) ---
        quick_host = QWidget()
        quick_host.setObjectName("tab_toolbar_strip")
        quick_outer = QVBoxLayout(quick_host)
        quick_outer.setContentsMargins(10, 6, 10, 4)
        quick_outer.setSpacing(6)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        self.mode_combo = StyledComboBox()
        self.mode_combo.addItems(["Auto", "Download", "Generate"])
        self.mode_combo.setMinimumWidth(120)
        self.mode_combo.setMinimumContentsLength(9)
        mode_row.addWidget(StyledLabel("Mode:"))
        mode_row.addWidget(self.mode_combo)
        self.search_btn = QPushButton("Search")
        self.search_btn.setMinimumWidth(100)
        mode_row.addWidget(self.search_btn)
        mode_row.addStretch()
        quick_outer.addLayout(mode_row)

        lists_grid = QGridLayout()
        lists_grid.setHorizontalSpacing(16)
        lists_grid.setVerticalSpacing(4)
        lists_grid.addWidget(StyledLabel("Languages:"), 0, 0, Qt.AlignmentFlag.AlignTop)
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
        self.language_list.setMinimumWidth(160)
        lists_grid.addWidget(self.language_list, 0, 1)
        lists_grid.addWidget(StyledLabel("Providers:"), 0, 2, Qt.AlignmentFlag.AlignTop)
        self.provider_list = QListWidget()
        self.provider_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        providers = ["All", "OpenSubtitles", "Addic7ed", "SubDL", "Subf2m", "YIFY Subtitles", "Podnapisi", "SubDivX", "Kitsunekko", "Jimaku"]
        for provider in providers:
            item = QListWidgetItem(provider)
            self.provider_list.addItem(item)
            if provider == "All":
                item.setSelected(True)
        self.provider_list.setMaximumHeight(60)
        self.provider_list.setMinimumWidth(200)
        lists_grid.addWidget(self.provider_list, 0, 3)
        lists_grid.setColumnStretch(1, 1)
        lists_grid.setColumnStretch(3, 1)
        quick_outer.addLayout(lists_grid)

        status_row = QHBoxLayout()
        self.whisper_status = StyledLabel("Whisper: checking…")
        self.whisper_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.whisper_status.setToolTip("Click to open Whisper AI setup")
        self.whisper_status.mousePressEvent = lambda _: self._open_whisper_setup()
        self.opensubs_status = StyledLabel("")
        status_row.addWidget(self.whisper_status)
        status_row.addWidget(self.opensubs_status)
        status_row.addStretch()
        quick_outer.addLayout(status_row)

        # Inline banner shown when Generate mode is selected but Whisper isn't ready
        self._whisper_banner = QWidget()
        self._whisper_banner.setVisible(False)
        banner_layout = QHBoxLayout(self._whisper_banner)
        banner_layout.setContentsMargins(10, 6, 10, 6)
        banner_lbl = QLabel(
            "faster-whisper is not installed or has no model downloaded. "
            "Subtitle generation won't work until it's set up."
        )
        banner_lbl.setWordWrap(True)
        banner_lbl.setStyleSheet("color: #e8a040;")
        banner_layout.addWidget(banner_lbl, 1)
        setup_link_btn = QPushButton("Set Up Whisper")
        setup_link_btn.clicked.connect(self._open_whisper_setup)
        banner_layout.addWidget(setup_link_btn)
        self._whisper_banner.setStyleSheet(
            "background: rgba(232,160,64,0.12); border-radius: 4px;"
        )
        quick_outer.addWidget(self._whisper_banner)

        main_layout.addWidget(quick_host)

        # --- Main Content Splitter ---
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: File list
        file_panel = QWidget()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(8, 0, 4, 0)
        file_layout.setSpacing(4)
        self.file_table = AutoResizeTable()
        self.file_table.setColumns(headers=["Files"])  # Single column auto-stretches
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.file_table.setMinimumWidth(200)
        file_layout.addWidget(self.file_table)

        # File management buttons under the file table
        file_btn_layout = QHBoxLayout()
        self.add_files_btn = GlassmorphicButton("Add Files")
        self.add_files_btn.clicked.connect(self._add_files)
        self.add_folder_btn = GlassmorphicButton("Add Folder")
        self.add_folder_btn.clicked.connect(self._add_folder)
        self.remove_sub_btn = GlassmorphicButton("Remove")
        self.remove_sub_btn.clicked.connect(self._remove_selected)
        file_btn_layout.addWidget(self.add_files_btn)
        file_btn_layout.addWidget(self.add_folder_btn)
        file_btn_layout.addWidget(self.remove_sub_btn)
        file_btn_layout.addStretch()
        file_layout.addLayout(file_btn_layout)

        file_panel.setMinimumWidth(180)
        self._main_splitter.addWidget(file_panel)

        # Center: Subtitles found for selected file
        subs_panel = QWidget()
        subs_layout = QVBoxLayout(subs_panel)
        subs_layout.setContentsMargins(4, 0, 4, 0)
        subs_layout.setSpacing(4)
        self.subs_table = AutoResizeTable()
        self.subs_table.setColumns(
            headers=["Language", "Provider", "Status", "Score"],
            initial_widths=[80, 100, 80]  # Score column auto-stretches
        )
        self.subs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.subs_table.setMinimumWidth(320)
        subs_layout.addWidget(self.subs_table)
        subs_panel.setMinimumWidth(260)
        self._main_splitter.addWidget(subs_panel)

        # Right: Subtitle preview/info panel
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(4, 0, 8, 0)
        preview_layout.setSpacing(4)
        self.preview_label = StyledLabel("Subtitle Preview")
        self.preview_label.setObjectName("title_label")
        preview_layout.addWidget(self.preview_label)
        self.preview_text = StyledTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Subtitle preview will appear here...")
        self.preview_text.setMinimumWidth(220)
        # Don't set maximum width for QTextEdit in splitter layouts
        preview_layout.addWidget(self.preview_text)
        preview_panel.setMinimumWidth(180)
        self._main_splitter.addWidget(preview_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 2)
        self._main_splitter.setStretchFactor(2, 1)

        main_layout.addWidget(self._main_splitter)

        # --- Bottom Bar: Apply/Batch Apply ---
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(12, 6, 12, 12)
        bottom_bar.setSpacing(12)
        self.apply_btn = QPushButton("Apply")
        self.batch_apply_btn = QPushButton("Batch Apply")
        self.apply_mode_combo = StyledComboBox()
        self.apply_mode_combo.addItems(["External File", "Embed in Video", "Burn-in"])
        self.apply_mode_combo.setMinimumWidth(120)
        self.apply_mode_combo.setMinimumContentsLength(16)
        bottom_bar.addWidget(self.apply_btn)
        bottom_bar.addWidget(self.batch_apply_btn)
        bottom_bar.addWidget(StyledLabel("Mode:"))
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
        self.subs_table.itemSelectionChanged.connect(self._on_subtitle_selected)

        # Hide Add Files/Add Folder buttons (now only in sidebar)
        # Remove sync, encoding, format, and other legacy options

        self._subtitle_rows: List[Dict[str, Any]] = []

    def _current_video_path(self) -> Optional[Path]:
        row = self.file_table.currentRow()
        if row < 0:
            row = 0
        if self.file_table.rowCount() == 0:
            return None
        item = self.file_table.item(row, 0)
        if not item:
            return None
        return Path(item.data(Qt.ItemDataRole.UserRole))

    def _apply_mode_to_core(self, label: str) -> str:
        m = {
            "External File": "external",
            "Embed in Video": "embed",
            "Burn-in": "burn-in",
        }.get(label, "external")
        return m

    def _on_provider_changed(self):
        all_item = self.provider_list.item(0)
        if all_item and all_item.isSelected():
            for i in range(1, self.provider_list.count()):
                self.provider_list.item(i).setSelected(True)

    def _on_language_changed(self):
        pass

    def _on_search_clicked(self):
        path = self._current_video_path()
        if not path or not path.is_file():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Subtitles", "Add and select a video file first.")
            return
        mode = self.mode_combo.currentText()
        subs = self._get_subtitle_settings()

        if mode in ("Generate", "Auto"):
            self._run_whisper_or_search(path, subs, prefer_whisper=(mode == "Generate"))
        else:
            self._run_search_only(path, subs)

    def _run_search_only(self, path: Path, subs: Dict[str, Any]):
        def job(progress_callback=None):
            core = _subtitle_core_from_settings(subs)
            return core.search_subtitles(str(path), subs.get("languages", ["eng"]), progress_callback)

        worker = Worker(job)
        worker.signals.result.connect(self._on_search_result)
        worker.signals.error.connect(lambda e: self._on_search_error(e))
        self.thread_pool.start(worker)
        self.search_btn.setEnabled(False)

    def _run_whisper_or_search(self, path: Path, subs: Dict[str, Any], prefer_whisper: bool):
        if prefer_whisper:
            lang = subs.get("languages", ["eng"])[0] if subs.get("languages") else None

            def gen_job(progress_callback=None):
                core = _subtitle_core_from_settings(subs)
                return core.generate_subtitles(str(path), language=lang, progress_callback=progress_callback)

            worker = Worker(gen_job)
            worker.signals.result.connect(self._on_generate_result)
            worker.signals.error.connect(lambda e: self._on_search_error(e))
            self.thread_pool.start(worker)
            self.search_btn.setEnabled(False)
            return
        self._run_search_only(path, subs)

    def _on_search_result(self, result: Any):
        self.search_btn.setEnabled(True)
        self.subs_table.setRowCount(0)
        self._subtitle_rows = []
        if not isinstance(result, dict) or result.get("status") != "success":
            return
        for sub in result.get("subtitles", []):
            r = self.subs_table.rowCount()
            self.subs_table.insertRow(r)
            lang = sub.get("language", "")
            prov = sub.get("provider", "")
            fmt = sub.get("format", "")
            score = str(sub.get("score", ""))
            self.subs_table.setItem(r, 0, QTableWidgetItem(lang))
            self.subs_table.setItem(r, 1, QTableWidgetItem(prov))
            self.subs_table.setItem(r, 2, QTableWidgetItem(fmt))
            self.subs_table.setItem(r, 3, QTableWidgetItem(score))
            it = self.subs_table.item(r, 0)
            if it:
                it.setData(Qt.ItemDataRole.UserRole, sub)
            self._subtitle_rows.append(sub)

    def _on_generate_result(self, result: Any):
        self.search_btn.setEnabled(True)
        self.subs_table.setRowCount(0)
        self._subtitle_rows = []
        if isinstance(result, dict) and result.get("status") == "success":
            info = result.get("subtitle") or {}
            sp = result.get("subtitle_path") or info.get("path") or info.get("subtitle_path")
            if sp:
                sub = {"language": "generated", "provider": "whisper", "format": "srt", "score": 100, "local_path": sp}
                self.subs_table.insertRow(0)
                self.subs_table.setItem(0, 0, QTableWidgetItem("generated"))
                self.subs_table.setItem(0, 1, QTableWidgetItem("Whisper"))
                self.subs_table.setItem(0, 2, QTableWidgetItem("srt"))
                self.subs_table.setItem(0, 3, QTableWidgetItem("100"))
                it = self.subs_table.item(0, 0)
                if it:
                    it.setData(Qt.ItemDataRole.UserRole, sub)

    def _on_search_error(self, error: tuple):
        self.search_btn.setEnabled(True)
        logger.error("Subtitle search/generate error: %s", error)

    def _on_apply_clicked(self):
        path = self._current_video_path()
        if not path:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Subtitles", "Select a video file.")
            return
        items = self.subs_table.selectedItems()
        if not items:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Subtitles", "Select a subtitle row first.")
            return
        row = items[0].row()
        lang_item = self.subs_table.item(row, 0)
        sub = lang_item.data(Qt.ItemDataRole.UserRole) if lang_item else None
        if not isinstance(sub, dict):
            return
        mode = self._apply_mode_to_core(self.apply_mode_combo.currentText())
        subs = self._get_subtitle_settings()

        def job(progress_callback=None):
            core = _subtitle_core_from_settings(subs)
            if sub.get("local_path"):
                paths = [sub["local_path"]]
            else:
                dl = core.download_subtitle(
                    sub.get("file_id", ""),
                    sub.get("provider", ""),
                    str(path),
                    sub.get("language", "eng"),
                    sub.get("download_url", ""),
                )
                if dl.get("status") != "success":
                    return dl
                paths = [dl.get("subtitle_path") or dl.get("path", "")]
            return core.apply_subtitles(
                str(path), [p for p in paths if p], output_path=None, mode=mode,
                language=sub.get("language", "eng"), progress_callback=progress_callback
            )

        worker = Worker(job)
        worker.signals.finished.connect(lambda: None)
        worker.signals.result.connect(lambda r: self._on_apply_done(r, str(path)))
        worker.signals.error.connect(lambda e: self._on_subtitle_error(0, str(path), e))
        self.thread_pool.start(worker)

    def _on_apply_done(self, result: Any, file_path: str):
        if isinstance(result, dict) and result.get("status") == "success":
            self.subtitle_completed.emit(file_path)

    def _on_batch_apply_clicked(self):
        from PySide6.QtWidgets import QMessageBox
        if self.file_table.rowCount() == 0:
            QMessageBox.warning(self, "Subtitles", "No files in the list.")
            return
        subs = self._get_subtitle_settings()
        mode = self._apply_mode_to_core(self.apply_mode_combo.currentText())

        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if not item:
                continue
            fp = Path(item.data(Qt.ItemDataRole.UserRole))
            worker = SubtitleWorker(fp, subs)
            worker.signals.result.connect(
                lambda res, p=str(fp): self._on_batch_download_then_apply(res, p, mode)
            )
            worker.signals.error.connect(
                lambda err, p=str(fp): self._on_subtitle_error(0, p, err)
            )
            self.thread_pool.start(worker)

    def _on_batch_download_then_apply(self, result: Any, video_path: str, mode: str):
        if not isinstance(result, dict) or result.get("status") != "success":
            return
        downloaded = result.get("subtitles_downloaded") or []
        paths = []
        for d in downloaded:
            p = d.get("subtitle_path") or d.get("path")
            if p:
                paths.append(p)
        if not paths:
            return
        subs = self._get_subtitle_settings()

        def job(progress_callback=None):
            core = _subtitle_core_from_settings(subs)
            return core.apply_subtitles(
                video_path, paths, output_path=None, mode=mode,
                language=subs.get("languages", ["eng"])[0], progress_callback=progress_callback
            )

        w = Worker(job)
        w.signals.result.connect(lambda r: self._on_apply_done(r, video_path))
        self.thread_pool.start(w)

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
        self.file_table = AutoResizeTable()
        self.file_table.setColumns(
            headers=["File", "Language", "Status", "Progress", "Method"],
            initial_widths=[250, 100, 100, 100]  # Method column auto-stretches
        )
        self.file_table.enableDragDrop(self._drag_enter_event, self._drop_event)
        
        layout.addWidget(self.file_table, 1)  # Give table full stretch
        
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
        
        self.download_radio = StyledCheckBox("Download from Providers")
        self.download_radio.setChecked(True)
        self.whisper_radio = StyledCheckBox("Generate with Whisper AI")
        
        mode_layout.addWidget(self.download_radio)
        mode_layout.addWidget(self.whisper_radio)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Language selection
        lang_group = QGroupBox("Language Settings")
        lang_layout = QFormLayout()
        
        self.language_combo = StyledComboBox()
        self.language_combo.addItems([
            "English", "Spanish", "French", "German", "Italian",
            "Portuguese", "Russian", "Japanese", "Korean", "Chinese",
            "Arabic", "Dutch", "Polish", "Swedish", "Turkish"
        ])
        lang_layout.addRow("Primary Language:", self.language_combo)
        
        self.fallback_check = StyledCheckBox("Try other languages if not found")
        self.fallback_check.setChecked(True)
        lang_layout.addRow("", self.fallback_check)
        
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)
        
        # Provider selection (for download mode)
        self.provider_group = QGroupBox("Subtitle Providers")
        provider_layout = QVBoxLayout()
        
        providers_label = StyledLabel("Select providers to search:")
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
        
        self.whisper_model_combo = StyledComboBox()
        self.whisper_model_combo.addItems([
            "tiny (fastest, least accurate)",
            "base",
            "small",
            "medium (recommended)",
            "large (best quality, slowest)"
        ])
        self.whisper_model_combo.setCurrentIndex(3)  # medium
        whisper_layout.addRow("Model:", self.whisper_model_combo)
        
        self.whisper_device_combo = StyledComboBox()
        self.whisper_device_combo.addItems(["Auto", "CPU", "CUDA (GPU)", "MPS (Apple Silicon)"])
        whisper_layout.addRow("Device:", self.whisper_device_combo)
        
        self.translate_check = StyledCheckBox("Translate to English")
        whisper_layout.addRow("", self.translate_check)
        
        self.whisper_group.setLayout(whisper_layout)
        self.whisper_group.setVisible(False)  # Hidden by default
        layout.addWidget(self.whisper_group)
        
        # Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout()
        
        self.subtitle_format_combo = StyledComboBox()
        self.subtitle_format_combo.addItems(["SRT", "VTT", "ASS/SSA"])
        output_layout.addRow("Format:", self.subtitle_format_combo)
        
        self.encoding_combo = StyledComboBox()
        self.encoding_combo.addItems(["UTF-8", "UTF-8 BOM", "ASCII", "ISO-8859-1"])
        output_layout.addRow("Encoding:", self.encoding_combo)
        
        self.sync_check = StyledCheckBox("Attempt to sync subtitles")
        self.sync_check.setChecked(True)
        output_layout.addRow("", self.sync_check)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Preview section
        preview_group = QGroupBox("Subtitle Preview")
        preview_layout = QVBoxLayout()
        
        self.preview_text = StyledTextEdit()
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
        mode = self.mode_combo.currentText()
        show_providers = mode in ("Auto", "Download")
        self.provider_list.setEnabled(show_providers)
        if mode == "Generate":
            self._update_whisper_status()
        else:
            self._whisper_banner.setVisible(False)

    def _update_whisper_status(self):
        """Check faster-whisper availability and update the status label + banner."""
        try:
            from core.providers.subtitle.whisper_manager import WhisperManager
            mgr = WhisperManager()
            if mgr.whisper_available and mgr.installed_models:
                model_list = ", ".join(mgr.installed_models)
                self.whisper_status.setText(f"Whisper: ready ({model_list})")
                self.whisper_status.setStyleSheet("color: #3fc66d;")
                self._whisper_banner.setVisible(False)
            elif mgr.whisper_available:
                self.whisper_status.setText("Whisper: installed — no model downloaded")
                self.whisper_status.setStyleSheet("color: #e8a040;")
                self._whisper_banner.setVisible(
                    self.mode_combo.currentText() == "Generate"
                )
            else:
                self.whisper_status.setText("Whisper: not installed — click to set up")
                self.whisper_status.setStyleSheet("color: #e05050;")
                self._whisper_banner.setVisible(
                    self.mode_combo.currentText() == "Generate"
                )
        except Exception:
            self.whisper_status.setText("Whisper: unavailable")
            self.whisper_status.setStyleSheet("color: #e05050;")

    def _open_whisper_setup(self):
        """Open the Whisper setup dialog and refresh status on close."""
        from app.dialogs.whisper_setup_dialog import WhisperSetupDialog
        dlg = WhisperSetupDialog(self)
        dlg.exec()
        self._update_whisper_status()
    
    def _on_subtitle_selected(self):
        """Show subtitle preview when user selects a subtitle in the results table."""
        selected = self.subs_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        item = self.subs_table.item(row, 0)
        if not item:
            return
        subtitle_path = item.data(Qt.ItemDataRole.UserRole)
        if subtitle_path and Path(subtitle_path).exists():
            try:
                with open(subtitle_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                preview = ''.join(lines[:50])
                self.preview_text.setPlainText(preview)
            except Exception as e:
                self.preview_text.setPlainText(f"Error loading preview: {e}")

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
        
        whisper_model = 'medium'
        try:
            from utils.settings_manager import get_settings_manager
            whisper_model = get_settings_manager().subtitle.whisper_model
        except Exception:
            pass
        
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
    
    def _on_subtitle_completed(self, _row: int, file_path: str):
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
    
    def _on_subtitle_error(self, _row: int, file_path: str, error: tuple):
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
