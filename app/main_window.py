"""Main application window for EncodeForge.
"""

import logging
import time
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSizePolicy,
    QStackedLayout,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import __version__ as APP_VERSION
from app.widgets.app_title_bar import AppTitleBar
from app.widgets.custom_widgets import (
    GlassmorphicButton,
    GlassmorphicMainWindow,
    GlassmorphicStatusBar,
    SectionDivider,
    StyledLabel,
)
from utils.update_checker import UpdateCheckOutcome

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


class MainWindow(GlassmorphicMainWindow):
    def __init__(self):
        super().__init__()
        self._title_bar = None
        self.setWindowTitle("EncodeForge")
        
        # Enable transparency for glassmorphism effect
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)  # Keep opaque for now
        
        # Set proper window sizing with responsive constraints
        self.setMinimumSize(1000, 640)
        self.resize(1300, 750)
        
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
        self._update_toast = None

        self._setup_ui()
        self._create_statusbar()
        QTimer.singleShot(2000, self._maybe_auto_check_updates)
        logger.debug("Main window initialized - theme loaded at startup")

    def _install_title_bar_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Check for Updates…", self._manual_check_updates)
        menu.addSeparator()
        act_docs = menu.addAction("Documentation")
        act_docs.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/SirStig/EncodeForge#readme"))
        )
        act_issue = menu.addAction("Report an Issue…")
        act_issue.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/SirStig/EncodeForge/issues"))
        )
        menu.addSeparator()
        menu.addAction("Open Logs Folder", self._open_logs_folder)
        menu.addAction("Open Settings Folder", self._open_settings_folder)
        menu.addSeparator()
        menu.addAction("About EncodeForge", self._show_about)
        self._title_bar.set_menu(menu)

    def _open_logs_folder(self) -> None:
        from core.path_manager import get_logs_dir

        p = get_logs_dir()
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))

    def _open_settings_folder(self) -> None:
        from core.path_manager import get_settings_file

        p = get_settings_file().parent.resolve()
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About EncodeForge",
            f"<h3>EncodeForge</h3><p>Version {APP_VERSION}</p>"
            "<p>Desktop media toolkit for encoding, subtitles, and renaming.</p>"
            "<p><a href=\"https://github.com/SirStig/EncodeForge\">GitHub</a></p>",
        )
    
    def setWindowTitle(self, title: str) -> None:
        super().setWindowTitle(title)
        if self._title_bar is not None:
            self._title_bar.set_title(title)

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("central_root")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title_bar = AppTitleBar(self, title="EncodeForge")
        outer.addWidget(self._title_bar)
        self._install_title_bar_menu()

        body = QWidget()
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer.addWidget(body, 1)

        main_layout = QHBoxLayout(body)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar (left)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(185)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(4)

        # App name / logo area
        app_name = StyledLabel("EncodeForge")
        app_name.setObjectName("sidebar_app_title")
        app_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        app_name.setMinimumHeight(32)
        sidebar_layout.addWidget(app_name)

        # Modes section
        modes_label = StyledLabel("MODES")
        modes_label.setObjectName("section_label")
        sidebar_layout.addWidget(modes_label)
        sidebar_layout.addSpacing(2)

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
            btn.setMinimumHeight(24)
            btn.setMaximumHeight(28)
            btn.clicked.connect(lambda checked, i=idx: self._switch_mode(i))
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[key] = btn

        sidebar_layout.addSpacing(10)

        # Files section
        files_label = StyledLabel("FILES")
        files_label.setObjectName("section_label")
        sidebar_layout.addWidget(files_label)

        # Add Files / Folder buttons (styled as ToolButtons now)
        add_files_btn = QToolButton()
        add_files_btn.setText("  Add Files")
        add_files_btn.setIcon(qta.icon('fa5s.file'))
        add_files_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        add_files_btn.clicked.connect(self._handle_add_files)
        add_files_btn.setMinimumHeight(24)
        add_files_btn.setMaximumHeight(28)
        sidebar_layout.addWidget(add_files_btn)

        add_folder_btn = QToolButton()
        add_folder_btn.setText("  Add Folder")
        add_folder_btn.setIcon(qta.icon('fa5s.folder'))
        add_folder_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        add_folder_btn.clicked.connect(self._handle_add_folder)
        add_folder_btn.setMinimumHeight(24)
        add_folder_btn.setMaximumHeight(28)
        sidebar_layout.addWidget(add_folder_btn)

        sidebar_layout.addSpacing(4)
        sidebar_layout.addWidget(SectionDivider())

        # Push everything to top, system section at bottom
        sidebar_layout.addStretch()

        sidebar_layout.addSpacing(4)
        # System section at bottom
        system_label = StyledLabel("SYSTEM")
        system_label.setObjectName("section_label")
        sidebar_layout.addWidget(system_label)

        # Logs button
        logs_btn = QToolButton()
        logs_btn.setText("  Logs")
        logs_btn.setIcon(qta.icon('fa5s.list'))
        logs_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        logs_btn.setCheckable(True)
        logs_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        logs_btn.setMinimumHeight(24)
        logs_btn.setMaximumHeight(28)
        logs_btn.clicked.connect(lambda checked: self._switch_mode(3))
        sidebar_layout.addWidget(logs_btn)
        self.sidebar_buttons["logs"] = logs_btn

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
        self.processes_btn.setMinimumHeight(24)
        self.processes_btn.setMaximumHeight(28)
        sidebar_layout.addWidget(self.processes_btn)
        self.sidebar_buttons["processes"] = self.processes_btn

        # Initialize badge count
        self._update_processes_badge(0)

        # Bottom spacing
        sidebar_layout.addSpacing(8)

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
        try:
            from app.dialogs.settings_dialog import SettingsPanel

            self.settings_panel = SettingsPanel(self, show_action_bar=True)
            self.settings_panel.settings_changed.connect(self._on_settings_changed)
        except Exception:
            self.settings_panel = None
        self.processes_tab = self._create_processes_tab()

        self.tabs = [
            self.encoder_tab,
            self.subtitle_tab,
            self.metadata_tab,
            self.logs_tab,
            self.settings_panel,
            self.processes_tab,
        ]
        for tab in self.tabs:
            self.stacked_layout.addWidget(tab if tab is not None else QWidget())

        # Default mode: encoder
        self._switch_mode(0)

        # If mode widgets expose signals we want to react to, connect them safely
        self._safe_connect_signals()
    
    def _create_processes_tab(self):
        """Create the processes monitoring tab."""
        processes_widget = QWidget()
        layout = QVBoxLayout(processes_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = StyledLabel("Active Encoding Processes")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Process list
        self.process_list = QListWidget()
        self.process_list.setAlternatingRowColors(True)
        layout.addWidget(self.process_list)
        
        # Info label
        self.process_info_label = StyledLabel("No active processes")
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
            for file_path, _worker in self.encoder_tab.active_workers.items():
                item = QListWidgetItem(f"Encoding: {Path(file_path).name}")
                item.setIcon(qta.icon('fa5s.cog'))
                self.process_list.addItem(item)
                active_processes.append(file_path)
        
        if active_processes:
            self.process_info_label.setText(f"{len(active_processes)} active process(es)")
        else:
            self.process_info_label.setText("No active processes")
    


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

    def _on_settings_changed(self):
        """React to settings being saved from the dialog."""
        import logging
        from utils.settings_manager import SettingsManager
        sm = SettingsManager()
        logging.getLogger().setLevel(getattr(logging, sm.application.log_level, logging.INFO))
        if hasattr(self, 'threadpool'):
            self.threadpool.setMaxThreadCount(sm.application.max_threads)
        logger.debug("Settings applied to running application")

    def _switch_mode(self, idx: int):
        """Switch between different modes/tabs."""
        # Uncheck all sidebar buttons first
        for btn in self.sidebar_buttons.values():
            btn.setChecked(False)

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
        if idx == 4:
            return self.settings_panel
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
        self.statusbar = GlassmorphicStatusBar()
        self.statusbar.setObjectName("app_bottom_bar")
        self.setStatusBar(self.statusbar)
        self.status_label = StyledLabel("Ready")
        self.statusbar.addWidget(self.status_label)
        self.progress_label = StyledLabel("")
        self.statusbar.addPermanentWidget(self.progress_label)

    def _update_status(self, message: str):
        try:
            self.status_label.setText(message)
        except Exception:
            logger.info(message)

    def _on_encode_started(self, file_path: str):
        self._update_status(f"Encoding: {Path(file_path).name}")

    def _on_encode_progress(self, _file_path: str, current: int, total: int, message: str = ""):
        pct = int((current / total) * 100) if total else 0
        self.progress_label.setText(f"{pct}% - {message}")

    def _on_encode_completed(self, file_path: str):
        self._update_status(f"Completed: {Path(file_path).name}")
        self.progress_label.setText("")

    def _on_process_count_changed(self, *_args):
        """Update the processes badge when process count changes."""
        try:
            if self.encoder_tab is not None and hasattr(self.encoder_tab, 'active_workers'):
                count = len(self.encoder_tab.active_workers)
                self._update_processes_badge(count)
        except Exception:
            pass

    def _on_subtitle_progress(self, *_args, **_kwargs):
        pass

    def _on_rename_progress(self, *_args, **_kwargs):
        pass

    def _maybe_auto_check_updates(self) -> None:
        from utils.settings_manager import SettingsManager

        sm = SettingsManager()
        if not sm.application.check_updates:
            return
        now = time.time()
        if now - sm.application.update_last_check_ts < 6 * 3600:
            return
        self._start_update_check(auto=True)

    def _manual_check_updates(self) -> None:
        self._start_update_check(auto=False)

    def _start_update_check(self, auto: bool) -> None:
        from utils.update_runner import UpdateCheckRunnable

        runnable = UpdateCheckRunnable(APP_VERSION)
        runnable.signals.setParent(self)

        def _done(outcome: object) -> None:
            self._on_update_check_done(outcome, auto)

        runnable.signals.finished.connect(_done)
        self.threadpool.start(runnable)

    def _on_update_check_done(self, outcome: object, auto: bool) -> None:
        if not isinstance(outcome, UpdateCheckOutcome):
            return
        from utils.settings_manager import SettingsManager

        sm = SettingsManager()
        if outcome.error:
            if not auto:
                QMessageBox.warning(
                    self,
                    "Update check",
                    f"Could not reach GitHub:\n{outcome.error}",
                )
            return
        if outcome.release:
            sm.application.update_last_check_ts = time.time()
            sm.save()
        if auto:
            if not outcome.release or not outcome.is_newer:
                return
            if outcome.release.version == sm.application.update_skipped_version:
                return
            self._show_update_toast(outcome.release)
            return
        if not outcome.release:
            QMessageBox.information(
                self,
                "Updates",
                "No releases were found for this project on GitHub.",
            )
            return
        if not outcome.is_newer:
            QMessageBox.information(
                self,
                "Updates",
                f"You are up to date (v{APP_VERSION}).",
            )
            return
        from app.dialogs.update_dialog import UpdateAvailableDialog

        dlg = UpdateAvailableDialog(outcome.release, APP_VERSION, self)
        dlg.exec()

    def _show_update_toast(self, release) -> None:
        from app.widgets.update_toast import UpdateToast

        cw = self.centralWidget()
        if cw is None:
            return
        if self._update_toast is not None:
            self._update_toast.hide()
            self._update_toast.deleteLater()
            self._update_toast = None
        toast = UpdateToast(cw)
        toast.set_version_text(release.version, release.name)
        toast.later_clicked.connect(
            lambda v=release.version: self._dismiss_update_toast(v)
        )
        toast.notes_clicked.connect(lambda r=release: self._open_update_dialog(r))
        toast.download_clicked.connect(
            lambda u=release.html_url: self._open_release_page(u)
        )
        self._update_toast = toast
        toast.show()
        toast.raise_()
        self._position_update_toast()

    def _dismiss_update_toast(self, skipped_version: str) -> None:
        from utils.settings_manager import SettingsManager

        sm = SettingsManager()
        sm.application.update_skipped_version = skipped_version
        sm.save()
        if self._update_toast is not None:
            self._update_toast.hide()
            self._update_toast.deleteLater()
            self._update_toast = None

    def _open_update_dialog(self, release) -> None:
        from app.dialogs.update_dialog import UpdateAvailableDialog

        dlg = UpdateAvailableDialog(release, APP_VERSION, self)
        dlg.exec()

    def _open_release_page(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _position_update_toast(self) -> None:
        if self._update_toast is None:
            return
        parent = self._update_toast.parentWidget()
        if parent is None:
            return
        m = 24
        sb = self.statusBar()
        if sb is not None and sb.isVisible():
            sb_h = sb.height()
        else:
            sb_h = 24
        bottom_reserve = sb_h + 40
        self._update_toast.adjustSize()
        self._update_toast.move(
            max(0, parent.width() - self._update_toast.width() - m),
            max(0, parent.height() - self._update_toast.height() - bottom_reserve),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_update_toast()

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
