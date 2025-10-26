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
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedLayout,
    QStatusBar,
    QTabWidget,
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

        # All tabs in order (encoder, subtitles, metadata, logs, settings, processes)
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

        # Processes button with badge
        self.processes_btn = QToolButton()
        self.processes_btn.setText("  Processes")
        self.processes_btn.setIcon(qta.icon('fa5s.cog'))
        self.processes_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.processes_btn.setCheckable(True)
        self.processes_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.processes_btn.setObjectName("processes_btn")
        self.processes_btn.clicked.connect(lambda checked: self._switch_mode(5))
        self.processes_btn.setMinimumHeight(28)
        self.processes_btn.setMaximumHeight(34)
        sidebar_layout.addWidget(self.processes_btn)
        self.sidebar_buttons["processes"] = self.processes_btn

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

        # Pre-create and add all tab widgets in order
        self.encoder_tab = EncoderTab(self.threadpool) if EncoderTab is not None else None
        self.subtitle_tab = SubtitleTab(self.threadpool) if SubtitleTab is not None else None
        self.metadata_tab = MetadataTab(self.threadpool) if MetadataTab is not None else None
        self.logs_tab = LogsTab() if LogsTab is not None else None
        self.settings_tab = self._create_settings_tab()
        self.processes_tab = self._create_processes_tab()
        
        self.tabs = [
            self.encoder_tab,      # 0
            self.subtitle_tab,     # 1
            self.metadata_tab,     # 2
            self.logs_tab,         # 3
            self.settings_tab,     # 4
            self.processes_tab     # 5
        ]
        for tab in self.tabs:
            self.stacked_layout.addWidget(tab if tab is not None else QWidget())

        # Default mode: encoder
        self._switch_mode(0)

        # If mode widgets expose signals we want to react to, connect them safely
        self._safe_connect_signals()
    
    def _create_settings_tab(self):
        """Create the settings tab widget."""
        # Create a wrapper widget that contains the settings dialog content
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Import the settings dialog and extract its content
        from utils.settings_manager import SettingsManager
        
        settings = SettingsManager()
        
        # Create a tab widget for settings
        tabs = QTabWidget()
        
        # General Tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        app_group = QGroupBox("Application")
        app_layout = QFormLayout(app_group)
        
        self.settings_language_combo = QComboBox()
        self.settings_language_combo.addItems(["English", "Spanish", "French", "German", "Japanese"])
        self.settings_language_combo.setCurrentText(settings.application.language)
        app_layout.addRow("Language:", self.settings_language_combo)
        
        self.settings_check_updates = QCheckBox("Check for updates on startup")
        self.settings_check_updates.setChecked(settings.application.check_updates)
        app_layout.addRow("", self.settings_check_updates)
        
        general_layout.addWidget(app_group)
        
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)
        
        self.settings_theme_combo = QComboBox()
        self.settings_theme_combo.addItems(["Dark", "Light", "Auto"])
        self.settings_theme_combo.setCurrentText(settings.ui.theme.capitalize())
        ui_layout.addRow("Theme:", self.settings_theme_combo)
        
        general_layout.addWidget(ui_group)
        general_layout.addStretch()
        
        tabs.addTab(general_tab, "General")
        
        # Add more tabs as needed (simplified version)
        tabs.addTab(QLabel("Encoder settings will be available here"), "Encoder")
        tabs.addTab(QLabel("Subtitle settings will be available here"), "Subtitle")
        tabs.addTab(QLabel("Advanced settings will be available here"), "Advanced")
        
        layout.addWidget(tabs)
        
        # Add save/apply buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("Save Settings")
        save_btn.setIcon(qta.icon('fa5s.save'))
        save_btn.clicked.connect(self._save_settings_tab)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        return settings_widget
    
    def _create_processes_tab(self):
        """Create the processes monitoring tab."""
        processes_widget = QWidget()
        layout = QVBoxLayout(processes_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Active Encoding Processes")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Process list
        self.process_list = QListWidget()
        self.process_list.setAlternatingRowColors(True)
        layout.addWidget(self.process_list)
        
        # Info label
        self.process_info_label = QLabel("No active processes")
        self.process_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.process_info_label)
        
        # Setup timer to update process list
        from PySide6.QtCore import QTimer
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self._update_process_list)
        self.process_timer.start(1000)  # Update every second
        
        return processes_widget
    
    def _update_process_list(self):
        """Update the process list with current active processes."""
        if not hasattr(self, 'process_list'):
            return
            
        self.process_list.clear()
        
        active_processes = []
        if self.encoder_tab is not None and hasattr(self.encoder_tab, 'active_workers') and self.encoder_tab.active_workers:
            for file_path, worker in self.encoder_tab.active_workers.items():
                item = QListWidgetItem(f"Encoding: {Path(file_path).name}")
                item.setIcon(qta.icon('fa5s.cog'))
                self.process_list.addItem(item)
                active_processes.append(file_path)
        
        if active_processes:
            self.process_info_label.setText(f"{len(active_processes)} active process(es)")
        else:
            self.process_info_label.setText("No active processes")
    
    def _save_settings_tab(self):
        """Save settings from the settings tab."""
        from utils.settings_manager import SettingsManager
        settings = SettingsManager()
        
        # Update settings from UI
        if hasattr(self, 'settings_language_combo'):
            settings.application.language = self.settings_language_combo.currentText().lower()[:2]
        if hasattr(self, 'settings_check_updates'):
            settings.application.check_updates = self.settings_check_updates.isChecked()
        if hasattr(self, 'settings_theme_combo'):
            settings.ui.theme = self.settings_theme_combo.currentText().lower()
        
        settings.save()
        logger.info("Settings saved successfully")
        
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")


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
        # Uncheck all sidebar buttons first
        for btn in self.sidebar_buttons.values():
            btn.setChecked(False)

        # Map index to button key
        button_keys = ["encoder", "subtitles", "metadata", "logs", "settings", "processes"]
        
        # Check the appropriate button
        if 0 <= idx < len(button_keys):
            key = button_keys[idx]
            if key in self.sidebar_buttons:
                self.sidebar_buttons[key].setChecked(True)

        # Switch the stacked layout index
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
            self.processes_btn.setText(f"  Processes ({count})")
            self.processes_btn.setObjectName("processes_btn_active")
        else:
            self.processes_btn.setText("  Processes")
            self.processes_btn.setObjectName("processes_btn")
            # Re-apply style to update appearance
            self.processes_btn.style().unpolish(self.processes_btn)
            self.processes_btn.style().polish(self.processes_btn)

    def closeEvent(self, event):
        logger.info("Application closing")
        try:
            if self.threadpool:
                self.threadpool.waitForDone(2000)
        except Exception:
            pass
        super().closeEvent(event)
