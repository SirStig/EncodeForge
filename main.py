#!/usr/bin/env python3
"""
EncodeForge - PySide6 Application
Main entry point for the desktop application
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Initialize logging FIRST
from utils.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

from app.dialogs import FFmpegSetupDialog
from app.main_window import MainWindow
from utils.ffmpeg_manager import get_ffmpeg_manager


def check_ffmpeg() -> bool:
    """
    Check if FFmpeg is available and configured using centralized manager.
    
    Returns:
        True if FFmpeg is ready, False otherwise
    """
    ffmpeg_manager = get_ffmpeg_manager()
    
    # Try to detect FFmpeg
    if ffmpeg_manager.detect_ffmpeg():
        logger.info(f"FFmpeg found at: {ffmpeg_manager.get_ffmpeg_path()}")
        return True
    
    logger.warning("FFmpeg not configured or not found")
    return False


def run_ffmpeg_setup() -> bool:
    """
    Show FFmpeg setup dialog and configure FFmpeg.
    
    Returns:
        True if setup completed successfully, False if cancelled
    """
    logger.info("Starting FFmpeg setup...")
    
    dialog = FFmpegSetupDialog(required=True)
    result = dialog.exec()
    
    if result:
        logger.info("FFmpeg setup completed successfully")
        return True
    else:
        logger.warning("FFmpeg setup was cancelled")
        return False


def main():
    """Main application entry point"""
    logger.info("Starting EncodeForge v0.5.0")

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("EncodeForge")
    app.setApplicationVersion("0.5.0")
    app.setOrganizationName("EncodeForge")
    
    # Load glassmorphism theme
    try:
        from utils.theme_manager import load_theme
        if load_theme():
            logger.info("Glassmorphism theme loaded successfully")
        else:
            logger.warning("Failed to load theme, using default styling")
    except Exception as e:
        logger.warning(f"Theme loading error: {e}")
    
    # Set application icon
    icon_path = Path(__file__).parent / "resources" / "icons" / "app-icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Check for FFmpeg before showing main window
    if not check_ffmpeg():
        logger.info("FFmpeg not found, showing setup dialog...")
        
        if not run_ffmpeg_setup():
            # User cancelled setup
            QMessageBox.critical(
                None,
                "FFmpeg Required",
                "FFmpeg is required for EncodeForge to function.\n\n"
                "The application will now exit.\n\n"
                "Please run the application again to complete FFmpeg setup.",
                QMessageBox.Ok
            )
            logger.error("Application startup cancelled - FFmpeg setup incomplete")
            return 1
    
    # Create and show main window
    try:
        window = MainWindow()
        window.show()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Failed to create main window: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Failed to start EncodeForge:\n\n{str(e)}\n\n"
            "Please check the logs for details.",
            QMessageBox.Ok
        )
        return 1
    
    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
