"""Main application window for EncodeForge.
"""

import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedLayout, QStatusBar, QFrame, QToolButton, QFileDialog, QSizePolicy,
    QComboBox, QSlider, QLineEdit, QCheckBox
)
from PySide6.QtCore import Qt

import qtawesome as qta

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
    from app.widgets.renamer_tab import RenamerTab
except Exception:
    RenamerTab = None

try:
    from app.widgets.logs_tab import LogsTab
except Exception:
    LogsTab = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EncodeForge")
        self.resize(1000, 720)  # Reduced default width
        self.setMinimumWidth(800)  # Set minimum width

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
        self.renamer_tab = None
        self.logs_tab = None
        self.settings_tab = None

        self._setup_ui()
        self._create_statusbar()
        self._load_styles()
    
    def _load_styles(self):
        """Load CSS styles for the main window."""
        try:
            from PySide6.QtCore import QFile, QTextStream
            
            css_file = Path(__file__).parent.parent / "resources" / "styles" / "main_window.css"
            if css_file.exists():
                file = QFile(str(css_file))
                if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
                    stream = QTextStream(file)
                    css_content = stream.readAll()
                    file.close()
                    
                    # Apply the CSS
                    self.setStyleSheet(css_content)
                    logger.debug("Main window styles loaded successfully")
                else:
                    logger.warning("Failed to open main_window.css file")
            else:
                logger.warning("main_window.css file not found")
        except Exception as e:
            logger.error(f"Failed to load main window styles: {e}")
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar (left)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)  # Reduced from 220
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        # Modes section
        modes_label = QLabel("MODES")
        modes_label.setObjectName("section_label")
        sidebar_layout.addWidget(modes_label)

        # Mode buttons
        self.sidebar_buttons = {}
        modes = [
            ("encoder", "Encoder", "fa5s.video"),
            ("subtitles", "Subtitles", "fa5s.closed-captioning"),
            ("renamer", "Renamer", "fa5s.edit"),
            ("logs", "Logs", "fa5s.list")
        ]
        for key, label, icon_name in modes:
            btn = QToolButton()
            btn.setText(label)
            btn.setIcon(qta.icon(icon_name))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.setMinimumHeight(32)
            btn.clicked.connect(lambda checked, k=key: self._switch_mode([m[0] for m in modes].index(k)))
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[key] = btn

        sidebar_layout.addSpacing(8)

        # Files section
        files_label = QLabel("FILES")
        files_label.setObjectName("section_label")
        sidebar_layout.addWidget(files_label)

        # Add Files / Folder buttons
        add_files_btn = QPushButton("Add Files")
        add_files_btn.setIcon(qta.icon('fa5s.file'))
        add_files_btn.clicked.connect(self._handle_add_files)
        add_files_btn.setMinimumHeight(32)
        sidebar_layout.addWidget(add_files_btn)

        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.setIcon(qta.icon('fa5s.folder'))
        add_folder_btn.clicked.connect(self._handle_add_folder)
        add_folder_btn.setMinimumHeight(32)
        sidebar_layout.addWidget(add_folder_btn)

        sidebar_layout.addSpacing(8)

        # System section
        system_label = QLabel("SYSTEM")
        system_label.setObjectName("section_label")
        sidebar_layout.addWidget(system_label)

        # Processes button with badge
        self.processes_btn = QToolButton()
        self.processes_btn.setText("Processes")
        self.processes_btn.setIcon(qta.icon('fa5s.cog'))
        self.processes_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.processes_btn.setObjectName("processes_btn")
        self.processes_btn.clicked.connect(self._show_processes_dialog)
        self.processes_btn.setMinimumHeight(32)
        sidebar_layout.addWidget(self.processes_btn)

        # Initialize badge count
        self._update_processes_badge(0)

        sidebar_layout.addStretch()

        # Settings at the bottom
        settings_btn = QToolButton()
        settings_btn.setText("Settings")
        settings_btn.setIcon(qta.icon('fa5s.cogs'))
        settings_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        settings_btn.setCheckable(True)
        settings_btn.clicked.connect(lambda: self._switch_mode(4))
        settings_btn.setMinimumHeight(32)
        sidebar_layout.addWidget(settings_btn)

        # Main area (right) - now uses full height
        main_area = QWidget()
        main_layout.addWidget(sidebar)
        main_layout.addWidget(main_area)

        # Stacked content area - uses full main area
        self.stacked_layout = QStackedLayout(main_area)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)

        # Default mode: encoder
        self._switch_mode(0)

        # If mode widgets expose signals we want to react to, connect them safely
        self._safe_connect_signals()

    def _safe_connect_signals(self):
        # Connect common signals if present, but don't fail if they are missing
        try:
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
            if hasattr(self.subtitle_tab, 'subtitle_progress') and callable(getattr(self.subtitle_tab, 'subtitle_progress', None)):
                self.subtitle_tab.subtitle_progress.connect(self._on_subtitle_progress)
        except Exception:
            logger.debug("Could not connect subtitle signals")

        try:
            if hasattr(self.renamer_tab, 'rename_progress') and callable(getattr(self.renamer_tab, 'rename_progress', None)):
                self.renamer_tab.rename_progress.connect(self._on_rename_progress)
        except Exception:
            logger.debug("Could not connect renamer signals")

    def _switch_mode(self, idx: int):
        # Uncheck all sidebar buttons first
        for btn in self.sidebar_buttons.values():
            try:
                btn.setChecked(False)
            except Exception:
                pass

        mode_names = ["encoder", "subtitles", "renamer", "logs", "settings"]
        if 0 <= idx < len(mode_names):
            name = mode_names[idx]
            if name in self.sidebar_buttons:
                try:
                    self.sidebar_buttons[name].setChecked(True)
                except Exception:
                    pass

        # Create tab widget if it doesn't exist
        tab_widget = None
        if idx == 0:  # encoder
            if self.encoder_tab is None and EncoderTab is not None:
                try:
                    self.encoder_tab = EncoderTab(self.threadpool)
                    self.stacked_layout.addWidget(self.encoder_tab)
                except Exception as e:
                    logger.error(f"Failed to create encoder tab: {e}")
                    return
            tab_widget = self.encoder_tab
        elif idx == 1:  # subtitles
            if self.subtitle_tab is None and SubtitleTab is not None:
                try:
                    self.subtitle_tab = SubtitleTab(self.threadpool)
                    self.stacked_layout.addWidget(self.subtitle_tab)
                except Exception as e:
                    logger.error(f"Failed to create subtitle tab: {e}")
                    return
            tab_widget = self.subtitle_tab
        elif idx == 2:  # renamer
            if self.renamer_tab is None and RenamerTab is not None:
                try:
                    self.renamer_tab = RenamerTab(self.threadpool)
                    self.stacked_layout.addWidget(self.renamer_tab)
                except Exception as e:
                    logger.error(f"Failed to create renamer tab: {e}")
                    return
            tab_widget = self.renamer_tab
        elif idx == 3:  # logs
            if self.logs_tab is None and LogsTab is not None:
                try:
                    self.logs_tab = LogsTab()
                    self.stacked_layout.addWidget(self.logs_tab)
                except Exception as e:
                    logger.error(f"Failed to create logs tab: {e}")
                    return
            tab_widget = self.logs_tab
        elif idx == 4:  # settings - for now, just use logs tab
            if self.logs_tab is None and LogsTab is not None:
                try:
                    self.logs_tab = LogsTab()
                    self.stacked_layout.addWidget(self.logs_tab)
                except Exception as e:
                    logger.error(f"Failed to create logs tab: {e}")
                    return
            tab_widget = self.logs_tab

        # Switch the stacked layout index if valid
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
            return self.renamer_tab
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
            if hasattr(self.encoder_tab, 'active_workers'):
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
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Active Processes")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Get active processes from encoder tab
        active_processes = []
        if hasattr(self.encoder_tab, 'active_workers') and self.encoder_tab.active_workers:
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

    def closeEvent(self, event):
        logger.info("Application closing")
        try:
            if self.threadpool:
                self.threadpool.waitForDone(2000)
        except Exception:
            pass
        super().closeEvent(event)
