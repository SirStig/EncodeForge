"""Main application window for EncodeForge.
"""

import logging
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedLayout,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    # Optional project logging config (if present, apply it)
    from utils import logging_config
    # Note: setup_logging() is called in main.py, don't call it again here
except Exception:
    # If logging_config is absent or fails, proceed with default logging
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Lazy imports of widgets (fall back to simple placeholders if unavailable)
try:
    from app.widgets.encoder_tab import EncoderTab
except Exception:
    EncoderTab = None

try:
    from app.widgets.subtitle_tab import SubtitleTab
except Exception:
    SubtitleTab = None

try:
    from app.widgets.metadata_tab import MetadataTab
except Exception:
    MetadataTab = None

try:
    from app.widgets.logs_tab import LogsTab
except Exception:
    LogsTab = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EncodeForge")
        
        # Enable transparency for glassmorphism effect
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)  # Keep opaque for now
        
        # Set proper window sizing with responsive constraints
        self.setMinimumSize(1250, 700)  # Reasonable minimum for toolbar and content
        self.resize(1300, 750)  # Standard default size
        
        # Initialize thread pool
        from PySide6.QtCore import QThreadPool
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(4)  # Reasonable limit for encoding tasks
        
        # Initialize notifier
        try:
            from utils.notifications import get_notification_manager
            self.notifier = get_notification_manager()
        except Exception:
            self.notifier = None

        # Mode widgets
        self.encoder_tab = None
        self.subtitle_tab = None
        self.metadata_tab = None
        self.logs_tab = None
        self.settings_tab = None

        self._setup_ui()
        self._create_statusbar()
        logger.debug("Main window initialized - theme loaded at startup")
    
    def _setup_ui(self):
        central = QWidget()
        central.setStyleSheet("background-color: #1a1a1c;")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar (left)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(170)  # Narrower sidebar for better content space
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        # Modes section
        modes_label = QLabel("MODES")
        modes_label.setObjectName("section_label")
        sidebar_layout.addWidget(modes_label)

        # Unified modes list (excluding settings, logs, processes - they go at bottom)
        self.modes = [
            ("encoder", "Encoder", "fa5s.video"),
            ("subtitles", "Subtitles", "fa5s.closed-captioning"),
            ("metadata", "Metadata", "fa5s.edit"),
        ]
        self.sidebar_buttons = {}
        
        for idx, (key, label, icon_name) in enumerate(self.modes):
            btn = QToolButton()
            btn.setText(f"  {label}")  # Add space for icon spacing
            btn.setIcon(qta.icon(icon_name))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.setMinimumHeight(28)
            btn.setMaximumHeight(34)
            btn.clicked.connect(lambda checked, i=idx: self._switch_mode(i))
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[key] = btn

        sidebar_layout.addSpacing(8)

        # Files section
        files_label = QLabel("FILES")
        files_label.setObjectName("section_label")
        sidebar_layout.addWidget(files_label)

        # Add Files / Folder buttons (styled as ToolButtons now)
        add_files_btn = QToolButton()
        add_files_btn.setText("  Add Files")
        add_files_btn.setIcon(qta.icon('fa5s.file'))
        add_files_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        add_files_btn.clicked.connect(self._handle_add_files)
        add_files_btn.setMinimumHeight(28)
        add_files_btn.setMaximumHeight(34)
        sidebar_layout.addWidget(add_files_btn)

        add_folder_btn = QToolButton()
        add_folder_btn.setText("  Add Folder")
        add_folder_btn.setIcon(qta.icon('fa5s.folder'))
        add_folder_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        add_folder_btn.clicked.connect(self._handle_add_folder)
        add_folder_btn.setMinimumHeight(28)
        add_folder_btn.setMaximumHeight(34)
        sidebar_layout.addWidget(add_folder_btn)

        # Push everything to top, system section at bottom
        sidebar_layout.addStretch()

        # System section at bottom
        system_label = QLabel("SYSTEM")
        system_label.setObjectName("section_label")
        sidebar_layout.addWidget(system_label)

        # Logs button
        logs_btn = QToolButton()
        logs_btn.setText("  Logs")
        logs_btn.setIcon(qta.icon('fa5s.list'))
        logs_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        logs_btn.setCheckable(True)
        logs_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        logs_btn.setMinimumHeight(28)
        logs_btn.setMaximumHeight(34)
        logs_btn.clicked.connect(lambda checked: self._switch_mode(3))
        sidebar_layout.addWidget(logs_btn)
        self.sidebar_buttons["logs"] = logs_btn

        # Processes button with badge
        self.processes_btn = QToolButton()
        self.processes_btn.setText("  Processes")
        self.processes_btn.setIcon(qta.icon('fa5s.cog'))
        self.processes_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.processes_btn.setObjectName("processes_btn")
        self.processes_btn.clicked.connect(self._show_processes_dialog)
        self.processes_btn.setMinimumHeight(28)
        self.processes_btn.setMaximumHeight(34)
        sidebar_layout.addWidget(self.processes_btn)

        # Settings button
        settings_btn = QToolButton()
        settings_btn.setText("  Settings")
        settings_btn.setIcon(qta.icon('fa5s.cogs'))
        settings_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        settings_btn.setCheckable(True)
        settings_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        settings_btn.setMinimumHeight(28)
        settings_btn.setMaximumHeight(34)
        settings_btn.clicked.connect(lambda checked: self._switch_mode(4))
        sidebar_layout.addWidget(settings_btn)
        self.sidebar_buttons["settings"] = settings_btn

        # Initialize badge count
        self._update_processes_badge(0)

        # Bottom spacing
        sidebar_layout.addSpacing(12)

        # Main area (right) - now uses full height
        main_area = QWidget()
        main_layout.addWidget(sidebar)
        main_layout.addWidget(main_area)

        # Stacked content area - uses full main area
        self.stacked_layout = QStackedLayout(main_area)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)

        # Pre-create and add all tab widgets in modes order
        self.encoder_tab = EncoderTab(self.threadpool) if EncoderTab is not None else None
        self.subtitle_tab = SubtitleTab(self.threadpool) if SubtitleTab is not None else None
        self.metadata_tab = MetadataTab(self.threadpool) if MetadataTab is not None else None
        self.logs_tab = LogsTab() if LogsTab is not None else None
        # For now, settings uses logs_tab as placeholder
        self.settings_tab = self.logs_tab
        self.tabs = [
            self.encoder_tab,
            self.subtitle_tab,
            self.metadata_tab,
            self.logs_tab,
            self.settings_tab
        ]
        for tab in self.tabs:
            self.stacked_layout.addWidget(tab if tab is not None else QWidget())

        # Default mode: encoder
        self._switch_mode(0)

        # If mode widgets expose signals we want to react to, connect them safely
        self._safe_connect_signals()

    def _safe_connect_signals(self):
        # Connect common signals if present, but don't fail if they are missing
        try:
            if self.encoder_tab is not None:
                if hasattr(self.encoder_tab, 'encode_started') and callable(getattr(self.encoder_tab, 'encode_started', None)):
                    self.encoder_tab.encode_started.connect(self._on_encode_started)
                    self.encoder_tab.encode_started.connect(self._on_process_count_changed)
                if hasattr(self.encoder_tab, 'encode_progress') and callable(getattr(self.encoder_tab, 'encode_progress', None)):
                    self.encoder_tab.encode_progress.connect(self._on_encode_progress)
                if hasattr(self.encoder_tab, 'encode_completed') and callable(getattr(self.encoder_tab, 'encode_completed', None)):
                    self.encoder_tab.encode_completed.connect(self._on_encode_completed)
                    self.encoder_tab.encode_completed.connect(self._on_process_count_changed)
                if hasattr(self.encoder_tab, 'encode_error') and callable(getattr(self.encoder_tab, 'encode_error', None)):
                    self.encoder_tab.encode_error.connect(self._on_process_count_changed)
        except Exception:
            logger.debug("Could not connect encoder signals")

        try:
            if self.subtitle_tab is not None:
                if hasattr(self.subtitle_tab, 'subtitle_progress') and callable(getattr(self.subtitle_tab, 'subtitle_progress', None)):
                    self.subtitle_tab.subtitle_progress.connect(self._on_subtitle_progress)
        except Exception:
            logger.debug("Could not connect subtitle signals")

        try:
            if self.metadata_tab is not None:
                if hasattr(self.metadata_tab, 'rename_progress') and callable(getattr(self.metadata_tab, 'rename_progress', None)):
                    self.metadata_tab.rename_progress.connect(self._on_rename_progress)
        except Exception:
            logger.debug("Could not connect metadata signals")

    def _switch_mode(self, idx: int):
        """Switch between different modes/tabs."""
        # Special handling for settings (last index)
        if idx == len(self.modes) - 1:  # Settings is last in modes list
            self._open_settings()
            return

        # Uncheck all sidebar buttons first
        for btn in self.sidebar_buttons.values():
            try:
                btn.setChecked(False)
            except Exception:
                pass

        if 0 <= idx < len(self.modes):
            name = self.modes[idx][0]
            if name in self.sidebar_buttons:
                try:
                    self.sidebar_buttons[name].setChecked(True)
                except Exception:
                    pass

        # Only switch the stacked layout index
        if 0 <= idx < self.stacked_layout.count():
            self.stacked_layout.setCurrentIndex(idx)

    # -------------------- Basic handlers --------------------
    def _current_mode_widget(self):
        idx = self.stacked_layout.currentIndex()
        if idx == 0:
            return self.encoder_tab
        if idx == 1:
            return self.subtitle_tab
        if idx == 2:
            return self.metadata_tab
        if idx == 3:
            return self.logs_tab
        return None

    def _handle_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add Files")
        if not files:
            return
        widget = self._current_mode_widget()
        # try a few common handler names
        for method_name in ('add_files', '_add_files', 'add_files_from_paths'):
            if hasattr(widget, method_name):
                try:
                    getattr(widget, method_name)(files)
                    return
                except Exception:
                    logger.exception("Failed to call mode add-files handler")
        # last-resort: log selected files
        logger.info("Files selected: %s", files)

    def _handle_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Add Folder")
        if not folder:
            return
        widget = self._current_mode_widget()
        for method_name in ('add_folder', '_add_folder', 'add_directory'):
            if hasattr(widget, method_name):
                try:
                    getattr(widget, method_name)(folder)
                    return
                except Exception:
                    logger.exception("Failed to call mode add-folder handler")
        logger.info("Folder selected: %s", folder)

    # -------------------- Status & callbacks --------------------
    def _create_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label)
        self.progress_label = QLabel("")
        self.statusbar.addPermanentWidget(self.progress_label)

    def _update_status(self, message: str):
        try:
            self.status_label.setText(message)
        except Exception:
            logger.info(message)

    def _on_encode_started(self, file_path: str):
        self._update_status(f"Encoding: {Path(file_path).name}")

    def _on_encode_progress(self, file_path: str, current: int, total: int, message: str = ""):
        pct = int((current / total) * 100) if total else 0
        self.progress_label.setText(f"{pct}% - {message}")

    def _on_encode_completed(self, file_path: str):
        self._update_status(f"Completed: {Path(file_path).name}")
        self.progress_label.setText("")

    def _on_process_count_changed(self, *args):
        """Update the processes badge when process count changes."""
        try:
            if self.encoder_tab is not None and hasattr(self.encoder_tab, 'active_workers'):
                count = len(self.encoder_tab.active_workers)
                self._update_processes_badge(count)
        except Exception:
            pass

    def _on_subtitle_progress(self, *args, **kwargs):
        # Placeholder for subtitle progress updates
        pass

    def _on_rename_progress(self, *args, **kwargs):
        # Placeholder for renamer progress updates
        pass

    def _update_processes_badge(self, count: int):
        """Update the processes button badge with the current count."""
        if count > 0:
            self.processes_btn.setText(f"Processes ({count})")
            self.processes_btn.setObjectName("processes_btn_active")
        else:
            self.processes_btn.setText("Processes")
            self.processes_btn.setObjectName("processes_btn")

    def _show_processes_dialog(self):
        """Show a dialog with current encoding processes."""
        from PySide6.QtWidgets import (
            QDialog,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QVBoxLayout,
        )
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Active Processes")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Get active processes from encoder tab
        active_processes = []
        if self.encoder_tab is not None and hasattr(self.encoder_tab, 'active_workers') and self.encoder_tab.active_workers:
            for file_path, worker in self.encoder_tab.active_workers.items():
                active_processes.append(f"Encoding: {Path(file_path).name}")
        
        if active_processes:
            list_widget = QListWidget()
            for process in active_processes:
                item = QListWidgetItem(process)
                item.setIcon(qta.icon('fa5s.cog'))
                list_widget.addItem(item)
            layout.addWidget(list_widget)
        else:
            no_processes_label = QLabel("No active processes")
            no_processes_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_processes_label)
        
        dialog.exec()
    
    def _open_settings(self):
        """Open the settings dialog."""
        from app.dialogs import SettingsDialog
        
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._on_settings_changed)
        
        # Uncheck settings button after dialog closes
        dialog.exec()
        if "settings" in self.sidebar_buttons:
            self.sidebar_buttons["settings"].setChecked(False)
    
    def _on_settings_changed(self):
        """Handle settings changes."""
        logger.info("Settings have been updated")
        # TODO: Apply settings changes to active tabs
        # - Reload encoder defaults
        # - Update subtitle providers
        # - Refresh metadata provider
        # - Update thread pool size
        # - Etc.

    def closeEvent(self, event):
        logger.info("Application closing")
        try:
            if self.threadpool:
                self.threadpool.waitForDone(2000)
        except Exception:
            pass
        super().closeEvent(event)
