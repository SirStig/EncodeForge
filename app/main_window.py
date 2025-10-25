"""
EncodeForge Main Window
Beautiful macOS-inspired PySide6 main application window
"""

import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QMenu, QToolBar, QLabel
)
from PySide6.QtCore import Qt, Signal, QThreadPool, QSize
from PySide6.QtGui import QAction, QIcon, QPalette, QColor
from desktop_notifier import DesktopNotifier

from app.widgets.encoder_tab import EncoderTab
from app.widgets.subtitle_tab import SubtitleTab
from app.widgets.renamer_tab import RenamerTab
from app.widgets.logs_tab import LogsTab

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with beautiful macOS-inspired design"""
    
    # Signals
    status_message = Signal(str)
    progress_update = Signal(int, str)
    
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.notifier = DesktopNotifier(app_name="EncodeForge")
        
        logger.info(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")
        
        self.setWindowTitle("EncodeForge")
        self.resize(1400, 900)
        self.setMinimumSize(1200, 700)
        
        self._setup_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        self._apply_macos_styling()
        
        # Connect signals
        self.status_message.connect(self._update_status)
        
        logger.info("Main window initialized")
    

    def _setup_ui(self):
        """Set up the main UI layout with macOS-inspired design (sidebar + stacked layout)"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar.setFixedWidth(170)

        # Sidebar buttons
        from PySide6.QtWidgets import QPushButton, QSizePolicy
        from PySide6.QtCore import Qt as QtCoreQt
        self.sidebar_buttons = {}
        sidebar_items = [
            ("Encoder", "🎬"),
            ("Subtitles", "📝"),
            ("Renamer", "🔤"),
            ("Logs", "📄"),
            ("Settings", "⚙️"),
        ]
        for idx, (name, emoji) in enumerate(sidebar_items):
            btn = QPushButton(f"  {emoji}  {name}")
            btn.setObjectName(f"sidebar_{name.lower()}_btn")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(48)
            btn.setStyleSheet("font-size: 15px; text-align: left; padding-left: 18px;")
            btn.clicked.connect(lambda checked, i=idx: self._switch_mode(i))
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[name.lower()] = btn
        sidebar_layout.addStretch()

        # Main area (vertical: quick settings + stacked content)
        main_area = QWidget()
        main_area_layout = QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(0, 0, 0, 0)
        main_area_layout.setSpacing(0)

        # Quick settings panel (placeholder, will update per mode)
        self.quick_settings_panel = QWidget()
        self.quick_settings_layout = QHBoxLayout(self.quick_settings_panel)
        self.quick_settings_layout.setContentsMargins(12, 8, 12, 8)
        self.quick_settings_layout.setSpacing(12)
        # Placeholder label
        self.quick_settings_label = QLabel("Quick Settings (mode-specific)")
        self.quick_settings_layout.addWidget(self.quick_settings_label)
        self.quick_settings_layout.addStretch()
        main_area_layout.addWidget(self.quick_settings_panel)

        # Stacked layout for mode panels
        from PySide6.QtWidgets import QStackedLayout
        self.stacked_layout = QStackedLayout()
        # Instantiate mode panels
        self.encoder_tab = EncoderTab(self.threadpool)
        self.subtitle_tab = SubtitleTab(self.threadpool)
        self.renamer_tab = RenamerTab(self.threadpool)
        self.logs_tab = LogsTab()
        # Placeholder for settings panel (to be implemented)
        self.settings_panel = QLabel("Settings panel coming soon...")
        self.settings_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Add panels to stacked layout
        self.stacked_layout.addWidget(self.encoder_tab)
        self.stacked_layout.addWidget(self.subtitle_tab)
        self.stacked_layout.addWidget(self.renamer_tab)
        self.stacked_layout.addWidget(self.logs_tab)
        self.stacked_layout.addWidget(self.settings_panel)
        # Add stacked layout to main area
        main_area_layout.addLayout(self.stacked_layout)

        # Connect signals for status updates
        self.encoder_tab.encode_started.connect(self._on_encode_started)
        self.encoder_tab.encode_progress.connect(self._on_encode_progress)
        self.encoder_tab.encode_completed.connect(self._on_encode_completed)
        self.encoder_tab.encode_error.connect(self._on_encode_error)
        self.subtitle_tab.subtitle_started.connect(self._on_subtitle_started)
        self.subtitle_tab.subtitle_progress.connect(self._on_subtitle_progress)
        self.subtitle_tab.subtitle_completed.connect(self._on_subtitle_completed)
        self.subtitle_tab.subtitle_error.connect(self._on_subtitle_error)
        self.renamer_tab.rename_started.connect(self._on_rename_started)
        self.renamer_tab.rename_progress.connect(self._on_rename_progress)
        self.renamer_tab.rename_completed.connect(self._on_rename_completed)
        self.renamer_tab.rename_error.connect(self._on_rename_error)

        # Layout: sidebar | main area
        main_layout.addWidget(sidebar)
        main_layout.addWidget(main_area)

        # Set default mode
        self._switch_mode(0)


    def _switch_mode(self, idx):
        # Uncheck all sidebar buttons
        for btn in self.sidebar_buttons.values():
            btn.setChecked(False)
        # Check the selected button
        mode_names = ["encoder", "subtitles", "renamer", "logs", "settings"]
        if 0 <= idx < len(mode_names):
            self.sidebar_buttons[mode_names[idx]].setChecked(True)
        self.stacked_layout.setCurrentIndex(idx)
        self._update_quick_settings(idx)

    def _clear_quick_settings(self):
        # Remove all widgets from quick settings layout
        while self.quick_settings_layout.count():
            item = self.quick_settings_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _update_quick_settings(self, idx):
        self._clear_quick_settings()
        mode_names = ["encoder", "subtitles", "renamer", "logs", "settings"]
        mode = mode_names[idx]
        from PySide6.QtWidgets import QLabel, QPushButton
        if mode == "encoder":
            # Encoder quick settings: codec, preset, CRF, start button
            codec_label = QLabel("Codec:")
            codec_combo = self.encoder_tab.codec_combo
            preset_label = QLabel("Preset:")
            preset_combo = self.encoder_tab.preset_combo
            crf_label = QLabel("CRF:")
            crf_slider = self.encoder_tab.crf_slider
            crf_value = self.encoder_tab.crf_label
            start_btn = self.encoder_tab.start_btn
            self.quick_settings_layout.addWidget(codec_label)
            self.quick_settings_layout.addWidget(codec_combo)
            self.quick_settings_layout.addSpacing(8)
            self.quick_settings_layout.addWidget(preset_label)
            self.quick_settings_layout.addWidget(preset_combo)
            self.quick_settings_layout.addSpacing(8)
            self.quick_settings_layout.addWidget(crf_label)
            self.quick_settings_layout.addWidget(crf_slider)
            self.quick_settings_layout.addWidget(crf_value)
            self.quick_settings_layout.addSpacing(16)
            self.quick_settings_layout.addWidget(start_btn)
            self.quick_settings_layout.addStretch()
        elif mode == "subtitles":
            # Subtitles quick settings: language, mode (download/whisper), start button
            lang_label = QLabel("Language:")
            lang_combo = self.subtitle_tab.language_combo
            mode_label = QLabel("Mode:")
            download_check = self.subtitle_tab.download_radio
            whisper_check = self.subtitle_tab.whisper_radio
            start_btn = self.subtitle_tab.start_btn
            self.quick_settings_layout.addWidget(lang_label)
            self.quick_settings_layout.addWidget(lang_combo)
            self.quick_settings_layout.addSpacing(8)
            self.quick_settings_layout.addWidget(mode_label)
            self.quick_settings_layout.addWidget(download_check)
            self.quick_settings_layout.addWidget(whisper_check)
            self.quick_settings_layout.addSpacing(16)
            self.quick_settings_layout.addWidget(start_btn)
            self.quick_settings_layout.addStretch()
        elif mode == "renamer":
            # Renamer quick settings: pattern, preview, rename button
            pattern_label = QLabel("Pattern:")
            pattern_input = self.renamer_tab.pattern_input
            preview_btn = self.renamer_tab.preview_btn
            rename_btn = self.renamer_tab.rename_btn
            self.quick_settings_layout.addWidget(pattern_label)
            self.quick_settings_layout.addWidget(pattern_input)
            self.quick_settings_layout.addSpacing(8)
            self.quick_settings_layout.addWidget(preview_btn)
            self.quick_settings_layout.addWidget(rename_btn)
            self.quick_settings_layout.addStretch()
        elif mode == "logs":
            # Logs quick settings: filter, search
            filter_label = QLabel("Filter:")
            filter_combo = self.logs_tab.filter_combo
            search_label = QLabel("Search:")
            search_box = self.logs_tab.search_box
            self.quick_settings_layout.addWidget(filter_label)
            self.quick_settings_layout.addWidget(filter_combo)
            self.quick_settings_layout.addSpacing(8)
            self.quick_settings_layout.addWidget(search_label)
            self.quick_settings_layout.addWidget(search_box)
            self.quick_settings_layout.addStretch()
        else:
            # Fallback: show mode name
            label = QLabel(f"Quick Settings: {mode.capitalize()}")
            self.quick_settings_layout.addWidget(label)
            self.quick_settings_layout.addStretch()

    # For menu actions that previously used tab_widget, update to use stacked_layout
    def _current_mode_widget(self):
        idx = self.stacked_layout.currentIndex()
        if idx == 0:
            return self.encoder_tab
        elif idx == 1:
            return self.subtitle_tab
        elif idx == 2:
            return self.renamer_tab
        elif idx == 3:
            return self.logs_tab
        else:
            return None
    
    def _apply_macos_styling(self):
        """Apply beautiful macOS-inspired dark theme"""
        self.setStyleSheet("""
            /* Main Window - macOS inspired */
            QMainWindow {
                background-color: #1e1e1e;
            }
            
            /* Tab Widget - Modern macOS style */
            QTabWidget::pane {
                border: none;
                background-color: #2d2d2d;
                border-radius: 0px;
            }
            
            QTabBar {
                background-color: #1e1e1e;
            }
            
            QTabBar::tab {
                background-color: transparent;
                color: #8e8e93;
                padding: 12px 24px;
                margin-right: 2px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 13px;
                font-weight: 500;
            }
            
            QTabBar::tab:selected {
                color: #ffffff;
                border-bottom: 2px solid #0a84ff;
            }
            
            QTabBar::tab:hover:!selected {
                color: #c7c7cc;
                background-color: rgba(255, 255, 255, 0.05);
            }
            
            /* Menu Bar - macOS style */
            QMenuBar {
                background-color: #1e1e1e;
                color: #ffffff;
                border-bottom: 1px solid #2a2a2a;
                padding: 4px;
            }
            
            QMenuBar::item {
                background-color: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }
            
            QMenuBar::item:selected {
                background-color: #0a84ff;
            }
            
            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 4px;
            }
            
            QMenu::item {
                padding: 8px 32px 8px 12px;
                border-radius: 4px;
            }
            
            QMenu::item:selected {
                background-color: #0a84ff;
            }
            
            QMenu::separator {
                height: 1px;
                background-color: #3a3a3a;
                margin: 4px 8px;
            }
            
            /* Toolbar - macOS style */
            QToolBar {
                background-color: #1e1e1e;
                border: none;
                border-bottom: 1px solid #2a2a2a;
                spacing: 8px;
                padding: 8px;
            }
            
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 8px;
                color: #ffffff;
            }
            
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
            
            /* Status Bar - macOS style */
            QStatusBar {
                background-color: #1e1e1e;
                color: #8e8e93;
                border-top: 1px solid #2a2a2a;
                font-size: 12px;
            }
            
            /* Scrollbars - macOS style */
            QScrollBar:vertical {
                background-color: transparent;
                width: 12px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 0.3);
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            /* Horizontal scrollbar */
            QScrollBar:horizontal {
                background-color: transparent;
                height: 12px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                min-width: 20px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: rgba(255, 255, 255, 0.3);
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
    
    def _create_menus(self):
        """Create application menus matching Java app structure"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        
        add_files_action = QAction("Add &Files...", self)
        add_files_action.setShortcut("Ctrl+O")
        add_files_action.triggered.connect(self._handle_add_files)
        file_menu.addAction(add_files_action)
        
        add_folder_action = QAction("Add F&older...", self)
        add_folder_action.setShortcut("Ctrl+Shift+O")
        add_folder_action.triggered.connect(self._handle_add_folder)
        file_menu.addAction(add_folder_action)
        
        file_menu.addSeparator()
        
        clear_queue_action = QAction("&Clear Queue", self)
        clear_queue_action.triggered.connect(self._handle_clear_queue)
        file_menu.addAction(clear_queue_action)
        
        remove_selected_action = QAction("&Remove Selected", self)
        remove_selected_action.setShortcut("Delete")
        remove_selected_action.triggered.connect(self._handle_remove_selected)
        file_menu.addAction(remove_selected_action)
        
        file_menu.addSeparator()
        
        open_output_action = QAction("Open &Output Folder", self)
        open_output_action.triggered.connect(self._handle_open_output_folder)
        file_menu.addAction(open_output_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        
        select_all_action = QAction("Select &All", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self._handle_select_all)
        edit_menu.addAction(select_all_action)
        
        deselect_all_action = QAction("&Deselect All", self)
        deselect_all_action.triggered.connect(self._handle_deselect_all)
        edit_menu.addAction(deselect_all_action)
        
        edit_menu.addSeparator()
        
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._handle_settings)
        edit_menu.addAction(settings_action)
        
        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        
        batch_rename_action = QAction("&Batch Rename...", self)
        batch_rename_action.triggered.connect(self._handle_batch_rename)
        tools_menu.addAction(batch_rename_action)
        
        extract_subs_action = QAction("&Extract Subtitles...", self)
        extract_subs_action.triggered.connect(self._handle_extract_subtitles)
        tools_menu.addAction(extract_subs_action)
        
        tools_menu.addSeparator()
        
        setup_whisper_action = QAction("Setup &AI Subtitles...", self)
        setup_whisper_action.triggered.connect(self._handle_setup_whisper)
        tools_menu.addAction(setup_whisper_action)
        
        tools_menu.addSeparator()
        
        check_ffmpeg_action = QAction("Check &FFmpeg Status", self)
        check_ffmpeg_action.triggered.connect(self._handle_check_ffmpeg)
        tools_menu.addAction(check_ffmpeg_action)
        
        download_ffmpeg_action = QAction("&Download FFmpeg", self)
        download_ffmpeg_action.triggered.connect(self._handle_download_ffmpeg)
        tools_menu.addAction(download_ffmpeg_action)
        
        tools_menu.addSeparator()
        
        open_logs_action = QAction("Open &Logs Folder", self)
        open_logs_action.triggered.connect(self._handle_open_logs_folder)
        tools_menu.addAction(open_logs_action)
        
        open_settings_folder_action = QAction("Open &Settings Folder", self)
        open_settings_folder_action.triggered.connect(self._handle_open_settings_folder)
        tools_menu.addAction(open_settings_folder_action)
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        docs_action = QAction("&Documentation", self)
        docs_action.setShortcut("F1")
        docs_action.triggered.connect(self._handle_documentation)
        help_menu.addAction(docs_action)
        
        view_logs_action = QAction("&View Logs", self)
        view_logs_action.triggered.connect(self._handle_view_logs)
        help_menu.addAction(view_logs_action)
        
        help_menu.addSeparator()
        
        check_updates_action = QAction("Check for &Updates...", self)
        check_updates_action.triggered.connect(self._handle_check_updates)
        help_menu.addAction(check_updates_action)
        
        report_issue_action = QAction("&Report Issue...", self)
        report_issue_action.triggered.connect(self._handle_report_issue)
        help_menu.addAction(report_issue_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("&About EncodeForge", self)
        about_action.triggered.connect(self._handle_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Create modern toolbar with common actions"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Add File action
        add_files_action = QAction("Add Files", self)
        toolbar.addAction(add_files_action)
        
        add_folder_action = QAction("Add Folder", self)
        toolbar.addAction(add_folder_action)
        
        toolbar.addSeparator()
        
        # Process actions
        start_action = QAction("Start", self)
        toolbar.addAction(start_action)
        
        pause_action = QAction("Pause", self)
        toolbar.addAction(pause_action)
        
        stop_action = QAction("Stop", self)
        toolbar.addAction(stop_action)
        
        toolbar.addSeparator()
        
        # Settings action
        settings_action = QAction("Settings", self)
        toolbar.addAction(settings_action)
    
    def _create_statusbar(self):
        """Create status bar with progress indicator"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label)
        
        # Progress info
        self.progress_label = QLabel("")
        self.statusbar.addPermanentWidget(self.progress_label)
    
    def _update_status(self, message: str):
        """Update status bar message"""
        self.status_label.setText(message)
    
    def _on_encode_started(self, file_path: str):
        """Handle encoding started event"""
        file_name = Path(file_path).name
        self.status_label.setText(f"Encoding: {file_name}")
        logger.info(f"Encoding started: {file_name}")
    
    def _on_encode_progress(self, file_path: str, current: int, total: int, message: str):
        """Handle encoding progress update"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_label.setText(f"{percentage}% - {message}")
    
    def _on_encode_completed(self, file_path: str):
        """Handle encoding completed event"""
        file_name = Path(file_path).name
        self.status_label.setText(f"Completed: {file_name}")
        self.progress_label.setText("")
        logger.info(f"Encoding completed: {file_name}")
    
    def _on_encode_error(self, file_path: str, error_message: str):
        """Handle encoding error event"""
        file_name = Path(file_path).name
        self.status_label.setText(f"Error: {file_name}")
        self.progress_label.setText(error_message)
        logger.error(f"Encoding error for {file_name}: {error_message}")
    
    def _on_subtitle_started(self, file_path: str):
        """Handle subtitle processing started event"""
        file_name = Path(file_path).name
        self.status_label.setText(f"Processing subtitles: {file_name}")
        logger.info(f"Subtitle processing started: {file_name}")
    
    def _on_subtitle_progress(self, file_path: str, current: int, total: int, message: str):
        """Handle subtitle processing progress update"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_label.setText(f"{percentage}% - {message}")
    
    def _on_subtitle_completed(self, file_path: str):
        """Handle subtitle processing completed event"""
        file_name = Path(file_path).name
        self.status_label.setText(f"Subtitles ready: {file_name}")
        self.progress_label.setText("")
        logger.info(f"Subtitle processing completed: {file_name}")
    
    def _on_subtitle_error(self, file_path: str, error_message: str):
        """Handle subtitle processing error event"""
        file_name = Path(file_path).name
        self.status_label.setText(f"Subtitle error: {file_name}")
        self.progress_label.setText(error_message)
        logger.error(f"Subtitle error for {file_name}: {error_message}")
    
    def _on_rename_started(self, file_path: str):
        """Handle rename processing started event"""
        file_name = Path(file_path).name if "/" in file_path or "\\" in file_path else file_path
        self.status_label.setText(f"Renaming: {file_name}")
        logger.info(f"Rename processing started: {file_name}")
    
    def _on_rename_progress(self, file_path: str, current: int, total: int, message: str):
        """Handle rename processing progress update"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_label.setText(f"{percentage}% - {message}")
    
    def _on_rename_completed(self, file_path: str):
        """Handle rename processing completed event"""
        file_name = Path(file_path).name if "/" in file_path or "\\" in file_path else file_path
        self.status_label.setText(f"Rename complete: {file_name}")
        self.progress_label.setText("")
        logger.info(f"Rename processing completed: {file_name}")
    
    def _on_rename_error(self, file_path: str, error_message: str):
        """Handle rename processing error event"""
        file_name = Path(file_path).name if "/" in file_path or "\\" in file_path else file_path
        self.status_label.setText(f"Rename error: {file_name}")
        self.progress_label.setText(error_message)
        logger.error(f"Rename error for {file_name}: {error_message}")
    
    async def show_notification(self, title: str, message: str, urgency: str = "normal"):
        """Show desktop notification"""
        try:
            await self.notifier.send(
                title=title,
                message=message,
                urgency=urgency
            )
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")
    
    # Menu Action Handlers
    
    def _handle_add_files(self):
        """Handle Add Files menu action"""
        current_widget = self._current_mode_widget()
        if hasattr(current_widget, '_add_files'):
            current_widget._add_files()
    
    def _handle_add_folder(self):
        """Handle Add Folder menu action"""
        current_widget = self._current_mode_widget()
        if hasattr(current_widget, '_add_folder'):
            current_widget._add_folder()
    
    def _handle_clear_queue(self):
        """Handle Clear Queue menu action"""
        current_widget = self._current_mode_widget()
        if hasattr(current_widget, '_clear_all'):
            current_widget._clear_all()
    
    def _handle_remove_selected(self):
        """Handle Remove Selected menu action"""
        current_widget = self._current_mode_widget()
        if hasattr(current_widget, '_remove_selected'):
            current_widget._remove_selected()
    
    def _handle_open_output_folder(self):
        """Handle Open Output Folder menu action"""
        import os
        import subprocess
        from core import path_manager
        output_dir = path_manager.get_cache_dir()
        if output_dir.exists():
            if os.name == 'nt':  # Windows
                os.startfile(output_dir)
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', str(output_dir)])
    
    def _handle_select_all(self):
        """Handle Select All menu action"""
        current_widget = self._current_mode_widget()
        if hasattr(current_widget, 'file_table'):
            current_widget.file_table.selectAll()
    
    def _handle_deselect_all(self):
        """Handle Deselect All menu action"""
        current_widget = self._current_mode_widget()
        if hasattr(current_widget, 'file_table'):
            current_widget.file_table.clearSelection()
    
    def _handle_settings(self):
        """Handle Settings menu action"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Settings", "Settings dialog will be implemented soon!")
        # TODO: Implement settings dialog
    
    def _handle_batch_rename(self):
        """Handle Batch Rename menu action"""
        self._switch_mode(2)
    
    def _handle_extract_subtitles(self):
        """Handle Extract Subtitles menu action"""
        self._switch_mode(1)
    
    def _handle_setup_whisper(self):
        """Handle Setup Whisper menu action"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Whisper Setup", "Whisper AI setup dialog will be implemented soon!")
        # TODO: Implement Whisper setup dialog
    
    def _handle_check_ffmpeg(self):
        """Handle Check FFmpeg Status menu action"""
        from PySide6.QtWidgets import QMessageBox
        from core import ffmpeg_manager
        
        try:
            ffmpeg_path = ffmpeg_manager.get_ffmpeg_path()
            version = ffmpeg_manager.get_ffmpeg_version()
            
            if ffmpeg_path and version:
                message = f"FFmpeg is installed\n\nPath: {ffmpeg_path}\nVersion: {version}"
                QMessageBox.information(self, "FFmpeg Status", message)
            else:
                message = "FFmpeg is not installed or not found in PATH"
                QMessageBox.warning(self, "FFmpeg Status", message)
        except Exception as e:
            QMessageBox.critical(self, "FFmpeg Status", f"Error checking FFmpeg: {str(e)}")
    
    def _handle_download_ffmpeg(self):
        """Handle Download FFmpeg menu action"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Download FFmpeg", "FFmpeg download dialog will be implemented soon!")
        # TODO: Implement FFmpeg download dialog
    
    def _handle_open_logs_folder(self):
        """Handle Open Logs Folder menu action"""
        import os
        import subprocess
        from core import path_manager
        logs_dir = path_manager.get_logs_dir()
        if logs_dir.exists():
            if os.name == 'nt':  # Windows
                os.startfile(logs_dir)
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', str(logs_dir)])
    
    def _handle_open_settings_folder(self):
        """Handle Open Settings Folder menu action"""
        import os
        import subprocess
        from core import path_manager
        settings_dir = path_manager.get_settings_dir()
        if settings_dir.exists():
            if os.name == 'nt':  # Windows
                os.startfile(settings_dir)
            elif os.name == 'posix':  # macOS/Linux
                subprocess.run(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', str(settings_dir)])
    
    def _handle_documentation(self):
        """Handle Documentation menu action"""
        import webbrowser
        webbrowser.open("https://github.com/SirStig/EncodeForge/wiki")
    
    def _handle_view_logs(self):
        """Handle View Logs menu action"""
        self._switch_mode(3)
    
    def _handle_check_updates(self):
        """Handle Check for Updates menu action"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Check for Updates", "Update checker will be implemented soon!")
        # TODO: Implement update checker
    
    def _handle_report_issue(self):
        """Handle Report Issue menu action"""
        import webbrowser
        webbrowser.open("https://github.com/SirStig/EncodeForge/issues/new")
    
    def _handle_about(self):
        """Handle About menu action"""
        from PySide6.QtWidgets import QMessageBox
        import sys
        from PySide6 import __version__ as pyside_version
        
        about_text = f"""
<h2>EncodeForge</h2>
<p><b>Version:</b> 0.5.0</p>
<p><b>Python Version:</b> {sys.version.split()[0]}</p>
<p><b>PySide6 Version:</b> {pyside_version}</p>
<br>
<p>A powerful media encoding, subtitle management, and file renaming tool.</p>
<p>Built with PySide6 and FFmpeg.</p>
<br>
<p><a href="https://github.com/SirStig/EncodeForge">GitHub Repository</a></p>
<p>License: MIT</p>
"""
        QMessageBox.about(self, "About EncodeForge", about_text)
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Application closing")
        
        # Clean up threads
        self.threadpool.waitForDone(2000)
        
        event.accept()
