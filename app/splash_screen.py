"""
EncodeForge Splash Screen
Beautiful loading screen with progress updates
"""

import logging

from app import __version__ as APP_VERSION
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QPalette, QColor, QFont
from pathlib import Path

logger = logging.getLogger(__name__)


class SplashScreen(QWidget):
    """
    Beautiful splash screen with progress indication.
    
    Signals:
        finished: Emitted when splash screen should close
    """
    
    finished = Signal()
    
    def __init__(self, parent=None):
        """Initialize splash screen."""
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._setup_ui()
        
        # Center on screen
        self.center_on_screen()
        
        self._load_styles()
        
        logger.debug("Splash screen initialized")
    
    def _setup_ui(self):
        """Set up the splash screen UI."""
        # Set size
        self.setFixedSize(600, 400)
        
        # Apply styling
        # self.setStyleSheet("""...""")  # Moved to external CSS file
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # Add spacing at top
        layout.addStretch(1)
        
        # Logo/App name
        title_label = QLabel("EncodeForge")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont("Segoe UI", 36, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setObjectName("title_label")
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_font = QFont("Segoe UI", 12)
        version_label.setFont(version_font)
        version_label.setObjectName("version_label")
        layout.addWidget(version_label)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_font = QFont("Segoe UI", 11)
        self.status_label.setFont(status_font)
        self.status_label.setObjectName("status_label")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Tagline
        tagline_label = QLabel("Video Encoding • Subtitles • Smart Renaming")
        tagline_label.setAlignment(Qt.AlignCenter)
        tagline_font = QFont("Segoe UI", 10)
        tagline_label.setFont(tagline_font)
        tagline_label.setObjectName("tagline_label")
        layout.addWidget(tagline_label)
        
        # Add spacing at bottom
        layout.addStretch(1)
    
    def _load_styles(self):
        """Load CSS styles for the splash screen."""
        try:
            from PySide6.QtCore import QFile, QTextStream
            
            css_file = Path(__file__).parent.parent / "resources" / "styles" / "splash_screen.css"
            if css_file.exists():
                file = QFile(str(css_file))
                if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
                    stream = QTextStream(file)
                    css_content = stream.readAll()
                    file.close()
                    
                    # Apply the CSS
                    self.setStyleSheet(css_content)
                    logger.debug("Splash screen styles loaded successfully")
                else:
                    logger.warning("Failed to open splash_screen.css file")
            else:
                logger.warning("splash_screen.css file not found")
        except Exception as e:
            logger.error(f"Failed to load splash screen styles: {e}")
    
    def center_on_screen(self):
        """Center the splash screen on the primary screen."""
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)
    
    def set_progress(self, value: int, status: str = ""):
        """
        Update progress bar and status message.
        
        Args:
            value: Progress value (0-100)
            status: Status message to display
        """
        self.progress_bar.setValue(value)
        if status:
            self.status_label.setText(status)
        logger.debug(f"Splash progress: {value}% - {status}")
    
    def show_message(self, message: str):
        """
        Show a status message.
        
        Args:
            message: Message to display
        """
        self.status_label.setText(message)
        logger.debug(f"Splash message: {message}")
    
    def finish(self):
        """Close the splash screen with fade out effect."""
        self.finished.emit()
        self.close()
        logger.debug("Splash screen closed")


class SplashScreenManager:
    """
    Manages splash screen lifecycle and initialization tasks.
    
    Usage:
        splash_manager = SplashScreenManager()
        splash_manager.run_initialization()
    """
    
    def __init__(self):
        """Initialize splash screen manager."""
        self.splash = SplashScreen()
        self.current_progress = 0
    
    def show(self):
        """Show the splash screen."""
        self.splash.show()
    
    def hide(self):
        """Hide the splash screen."""
        self.splash.finish()
    
    def update_progress(self, progress: int, message: str):
        """
        Update splash screen progress.
        
        Args:
            progress: Progress value (0-100)
            message: Status message
        """
        self.current_progress = progress
        self.splash.set_progress(progress, message)
    
    def run_initialization(self):
        """
        Run initialization tasks with progress updates.
        
        This should be called after showing the splash screen.
        Returns when initialization is complete.
        """
        from PySide6.QtCore import QCoreApplication
        
        # Task 1: Initialize paths (10%)
        self.update_progress(10, "Initializing directories...")
        QCoreApplication.processEvents()
        self._init_paths()
        
        # Task 2: Initialize logging (20%)
        self.update_progress(20, "Setting up logging...")
        QCoreApplication.processEvents()
        self._init_logging()
        
        # Task 3: Load settings (40%)
        self.update_progress(40, "Loading settings...")
        QCoreApplication.processEvents()
        self._init_settings()
        
        # Task 4: Check dependencies (60%)
        self.update_progress(60, "Checking dependencies...")
        QCoreApplication.processEvents()
        self._check_dependencies()
        
        # Task 5: Initialize managers (80%)
        self.update_progress(80, "Initializing managers...")
        QCoreApplication.processEvents()
        self._init_managers()
        
        # Task 6: Complete (100%)
        self.update_progress(100, "Ready!")
        QCoreApplication.processEvents()
        
        # Small delay to show completion
        QTimer.singleShot(500, self.hide)
    
    def _init_paths(self):
        """Initialize application paths."""
        from core import path_manager
        # Paths are auto-created by path_manager
        logger.debug("Paths initialized")
    
    def _init_logging(self):
        """Initialize logging system."""
        from utils.logging_config import setup_logging
        # Logging should already be set up, but ensure it's configured
        logger.debug("Logging verified")
    
    def _init_settings(self):
        """Load application settings."""
        from utils.settings_manager import get_settings_manager
        settings = get_settings_manager()
        settings.load()
        logger.debug("Settings loaded")
    
    def _check_dependencies(self):
        """Check for required dependencies."""
        # Check FFmpeg
        try:
            from core.ffmpeg_manager import FFmpegManager
            ffmpeg_mgr = FFmpegManager()
            success, info = ffmpeg_mgr.detect_ffmpeg()
            if success:
                logger.info("FFmpeg detected")
            else:
                logger.warning("FFmpeg not detected")
        except Exception as e:
            logger.warning(f"FFmpeg check failed: {e}")
    
    def _init_managers(self):
        """Initialize application managers."""
        # Managers are initialized as singletons when needed
        logger.debug("Managers ready")
