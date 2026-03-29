"""
FFmpeg Setup Dialog
Standalone dialog for detecting, downloading, or configuring FFmpeg
"""

import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)

from core.path_manager import get_bin_dir
from utils.download_manager import DownloadError, DownloadManager
from utils.ffmpeg_manager import get_ffmpeg_manager
from utils.settings_manager import SettingsManager
from utils.theme_manager import get_theme_manager
from utils.workers import Worker

logger = logging.getLogger(__name__)


class FFmpegSetupDialog(QDialog):
    """
    Dialog for FFmpeg setup and configuration.
    
    Provides three options:
    1. Auto-detect system FFmpeg
    2. Download FFmpeg automatically
    3. Select FFmpeg path manually
    """
    
    # Custom signals
    setup_complete = Signal(str)  # Emits FFmpeg path when setup is complete
    _log_to_ui = Signal(str)
    
    def __init__(self, parent=None, required: bool = True):
        """
        Initialize FFmpeg setup dialog.
        
        Args:
            parent: Parent widget
            required: If True, dialog cannot be closed without completing setup
        """
        super().__init__(parent)
        self.required = required
        self.settings = SettingsManager()
        self.download_manager = DownloadManager()
        self.thread_pool = QThreadPool.globalInstance()
        
        self.ffmpeg_path: Optional[Path] = None
        self.ffprobe_path: Optional[Path] = None
        
        self._setup_ui()
        self._apply_theme()
        self._connect_signals()
        self._check_existing_ffmpeg()
        if required:
            self._auto_detect()
    
    def _apply_theme(self):
        """Apply glassmorphism theme to dialog."""
        try:
            theme_manager = get_theme_manager()
            theme_manager.apply_dialog_theme(self)
            logger.debug("Applied theme to FFmpeg setup dialog")
        except Exception as e:
            logger.warning(f"Failed to apply theme to dialog: {e}")
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("FFmpeg Setup - EncodeForge")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        # Make modal if required
        if self.required:
            self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>FFmpeg Setup</h2>")
        layout.addWidget(header)
        
        info = QLabel(
            "FFmpeg is required for video encoding. Please choose a setup method:"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addSpacing(20)
        
        # Setup method selection
        method_group = QGroupBox("Setup Method")
        method_layout = QVBoxLayout(method_group)
        
        self.method_group = QButtonGroup(self)
        
        # Option 1: Auto-detect
        self.auto_detect_radio = QRadioButton("Auto-detect system FFmpeg")
        self.auto_detect_radio.setChecked(True)
        self.method_group.addButton(self.auto_detect_radio, 1)
        method_layout.addWidget(self.auto_detect_radio)
        
        auto_detect_hint = QLabel("  → Search for FFmpeg in system PATH")
        auto_detect_hint.setStyleSheet("color: #888;")
        method_layout.addWidget(auto_detect_hint)
        
        method_layout.addSpacing(10)
        
        # Option 2: Download
        self.download_radio = QRadioButton("Download FFmpeg automatically")
        self.method_group.addButton(self.download_radio, 2)
        method_layout.addWidget(self.download_radio)
        
        system = platform.system()
        download_hint = QLabel(f"  → Download official FFmpeg build for {system}")
        download_hint.setStyleSheet("color: #888;")
        method_layout.addWidget(download_hint)
        
        method_layout.addSpacing(10)
        
        # Option 3: Manual path
        self.manual_path_radio = QRadioButton("Select FFmpeg path manually")
        self.method_group.addButton(self.manual_path_radio, 3)
        method_layout.addWidget(self.manual_path_radio)
        
        manual_hint = QLabel("  → Browse to existing FFmpeg installation")
        manual_hint.setStyleSheet("color: #888;")
        method_layout.addWidget(manual_hint)
        
        # Manual path input (hidden by default)
        self.manual_path_widget = QGroupBox("FFmpeg Path")
        manual_path_layout = QVBoxLayout(self.manual_path_widget)
        
        path_input_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to ffmpeg executable...")
        path_input_layout.addWidget(self.path_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_ffmpeg)
        path_input_layout.addWidget(browse_btn)
        
        manual_path_layout.addLayout(path_input_layout)
        self.manual_path_widget.setVisible(False)
        method_layout.addWidget(self.manual_path_widget)
        
        layout.addWidget(method_group)
        
        layout.addSpacing(20)
        
        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.status_label = QLabel("Ready to begin setup")
        progress_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        # Log output — visible by default for transparency
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(120)
        progress_layout.addWidget(self.log_output)
        
        layout.addWidget(progress_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_btn)
        
        self.setup_btn = QPushButton("Begin Setup")
        self.setup_btn.setDefault(True)
        self.setup_btn.clicked.connect(self._begin_setup)
        button_layout.addWidget(self.setup_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.method_group.buttonClicked.connect(self._on_method_changed)
        self._log_to_ui.connect(self._log)
    
    def _on_method_changed(self, button):
        """Handle setup method change."""
        method_id = self.method_group.id(button)
        self.manual_path_widget.setVisible(method_id == 3)
    
    def _check_existing_ffmpeg(self):
        """Check if FFmpeg is already configured in settings."""
        existing_path = self.settings.application.ffmpeg_path
        if existing_path and Path(existing_path).exists():
            self._log(f"Found existing FFmpeg configuration: {existing_path}")
            self.path_input.setText(existing_path)
    
    def _browse_ffmpeg(self):
        """Open file dialog to browse for FFmpeg executable."""
        file_filter = "FFmpeg Executable (ffmpeg ffmpeg.exe);;All Files (*)"
        if platform.system() == "Windows":
            file_filter = "FFmpeg Executable (ffmpeg.exe);;All Files (*)"
        
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FFmpeg Executable",
            "",
            file_filter
        )
        
        if path:
            self.path_input.setText(path)
    
    def _log(self, message: str):
        """Add message to log output."""
        logger.info(message)
        self.log_output.append(message)
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )
    
    def _update_status(self, message: str):
        """Update status label."""
        self.status_label.setText(message)
        self._log(message)

    def _on_download_worker_progress(self, current: int, total: int, message: str):
        self.progress_bar.setValue(min(100, current))
        if message:
            self.status_label.setText(message)
    
    def _begin_setup(self):
        """Start the setup process based on selected method."""
        method_id = self.method_group.checkedId()
        
        # Disable controls during setup
        self.setup_btn.setEnabled(False)
        self.method_group.setExclusive(False)
        for button in self.method_group.buttons():
            button.setEnabled(False)
        self.method_group.setExclusive(True)
        
        if method_id == 1:
            self._auto_detect()
        elif method_id == 2:
            self._download_ffmpeg()
        elif method_id == 3:
            self._verify_manual_path()
    
    def _auto_detect(self):
        """Auto-detect FFmpeg using centralized manager."""
        self._update_status("Searching for FFmpeg on your system…")
        self.setup_btn.setEnabled(False)
        
        # Create worker for detection using centralized manager
        def detect_ffmpeg(progress_callback=None):
            ffmpeg_manager = get_ffmpeg_manager()
            
            if ffmpeg_manager.detect_ffmpeg(force_refresh=True):
                ffmpeg_path = ffmpeg_manager.get_ffmpeg_path()
                if not ffmpeg_path:
                    return None
                ffprobe_path = ffmpeg_manager.get_ffprobe_path()
                if not ffprobe_path:
                    ffprobe_exe = (
                        "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
                    )
                    cand = ffmpeg_path.parent / ffprobe_exe
                    if cand.exists():
                        ffprobe_path = cand
                return {
                    "ffmpeg": str(ffmpeg_path),
                    "ffprobe": str(ffprobe_path) if ffprobe_path else str(ffmpeg_path),
                }
            
            return None
        
        worker = Worker(detect_ffmpeg)
        worker.signals.result.connect(self._on_detection_complete)
        worker.signals.error.connect(self._on_error)
        self.thread_pool.start(worker)
    
    def _on_detection_complete(self, result):
        """Handle auto-detection completion."""
        if result:
            self.ffmpeg_path = Path(result["ffmpeg"])
            self.ffprobe_path = Path(result.get("ffprobe", result["ffmpeg"]))
            self._update_status(f"✓ Found FFmpeg: {self.ffmpeg_path}")
            self._save_and_complete()
        else:
            self._update_status(
                "✗ FFmpeg not found automatically. "
                "Choose 'Download' to fetch it, or 'Manual' to browse to an existing install."
            )
            self._reset_ui()
    
    def _download_ffmpeg(self):
        """Download FFmpeg automatically."""
        self._update_status("Preparing to download FFmpeg...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        system = platform.system().lower()
        machine = platform.machine().lower()
        is_arm = "arm" in machine or machine == "arm64" or machine == "aarch64"

        # eugeneware/ffmpeg-static: direct binary downloads, no archive extraction needed.
        # evermeet.cx is Intel-only and uses version-pinned URLs that go stale.
        # John Van Sickle provides archives for Linux static builds.
        _STATIC_BASE = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"

        if system == "windows":
            url = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"
            ffprobe_url = None
            direct_binary = False
        elif system == "linux":
            if is_arm:
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
            else:
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            ffprobe_url = None
            direct_binary = False
        elif system == "darwin":
            # eugeneware/ffmpeg-static: bare executables, no archive
            arch = "arm64" if is_arm else "x64"
            url = f"{_STATIC_BASE}/ffmpeg-darwin-{arch}"
            ffprobe_url = f"{_STATIC_BASE}/ffprobe-darwin-{arch}"
            direct_binary = True
        else:
            QMessageBox.critical(
                self,
                "Unsupported Platform",
                f"Automatic download is not supported for {system}.\n"
                "Please install FFmpeg manually and select the path."
            )
            self._reset_ui()
            return

        # Start download in worker (must not touch widgets here — QThreadPool worker thread)
        def download_and_extract(progress_callback=None):
            import stat as stat_mod

            bin_dir = get_bin_dir()
            ffmpeg_dir = bin_dir / "ffmpeg"
            ffmpeg_dir.mkdir(parents=True, exist_ok=True)

            def _dl_progress(downloaded, total, percentage):
                if not progress_callback:
                    return
                pct = min(99, int(percentage * 0.9))
                mb_dl = downloaded / (1024 * 1024)
                mb_tot = total / (1024 * 1024) if total else 0
                msg = f"Downloading: {mb_dl:.1f} / {mb_tot:.1f} MB ({percentage:.0f}%)"
                progress_callback({"progress": pct, "total": 100, "message": msg})

            try:
                if direct_binary:
                    # macOS: download bare executables directly
                    ffmpeg_dest = ffmpeg_dir / "ffmpeg"
                    self._log_to_ui.emit("Downloading ffmpeg binary…")
                    self.download_manager.download(
                        url=url,
                        destination=str(ffmpeg_dest),
                        progress_callback=_dl_progress,
                        resume=False,
                    )
                    ffmpeg_dest.chmod(ffmpeg_dest.stat().st_mode | stat_mod.S_IEXEC)

                    ffprobe_dest = ffmpeg_dir / "ffprobe"
                    if ffprobe_url:
                        self._log_to_ui.emit("Downloading ffprobe binary…")
                        if progress_callback:
                            progress_callback(
                                {
                                    "progress": 90,
                                    "total": 100,
                                    "message": "Downloading ffprobe…",
                                }
                            )
                        self.download_manager.download(
                            url=ffprobe_url,
                            destination=str(ffprobe_dest),
                            resume=False,
                        )
                        ffprobe_dest.chmod(ffprobe_dest.stat().st_mode | stat_mod.S_IEXEC)

                    return {
                        "ffmpeg": str(ffmpeg_dest),
                        "ffprobe": str(ffprobe_dest) if ffprobe_dest.exists() else str(ffmpeg_dest),
                    }

                else:
                    # Windows / Linux: download archive and extract
                    self._log_to_ui.emit(f"Downloading from: {url}")
                    archive_path = self.download_manager.download(
                        url=url,
                        destination=str(bin_dir / "ffmpeg_download.tmp"),
                        progress_callback=_dl_progress,
                        resume=True,
                    )

                    self._log_to_ui.emit("Extracting archive…")
                    if progress_callback:
                        progress_callback(
                            {
                                "progress": 95,
                                "total": 100,
                                "message": "Extracting FFmpeg…",
                            }
                        )
                    self.download_manager.extract_archive(archive_path, ffmpeg_dir)
                    archive_path.unlink(missing_ok=True)

                    ffmpeg_exe = "ffmpeg.exe" if system == "windows" else "ffmpeg"
                    ffprobe_exe = "ffprobe.exe" if system == "windows" else "ffprobe"

                    found_ffmpeg = next(
                        (p for p in ffmpeg_dir.rglob(ffmpeg_exe) if p.is_file()), None
                    )
                    found_ffprobe = next(
                        (p for p in ffmpeg_dir.rglob(ffprobe_exe) if p.is_file()), None
                    )

                    if not found_ffmpeg:
                        raise DownloadError("Could not find ffmpeg executable in downloaded archive")

                    if system == "linux":
                        found_ffmpeg.chmod(found_ffmpeg.stat().st_mode | stat_mod.S_IEXEC)
                        if found_ffprobe:
                            found_ffprobe.chmod(found_ffprobe.stat().st_mode | stat_mod.S_IEXEC)

                    return {
                        "ffmpeg": str(found_ffmpeg),
                        "ffprobe": str(found_ffprobe) if found_ffprobe else str(found_ffmpeg),
                    }

            except Exception as e:
                raise DownloadError(f"Download failed: {e}")
        
        worker = Worker(download_and_extract)
        worker.signals.progress.connect(self._on_download_worker_progress)
        worker.signals.result.connect(self._on_download_complete)
        worker.signals.error.connect(self._on_error)
        self.thread_pool.start(worker)
    
    def _on_download_complete(self, result):
        """Handle download completion."""
        self.ffmpeg_path = Path(result["ffmpeg"])
        self.ffprobe_path = Path(result.get("ffprobe", result["ffmpeg"]))
        self._update_status(f"✓ Downloaded and installed FFmpeg: {self.ffmpeg_path}")
        self.progress_bar.setValue(100)
        self._save_and_complete()
    
    def _verify_manual_path(self):
        """Verify manually selected FFmpeg path."""
        path_str = self.path_input.text().strip()
        
        if not path_str:
            QMessageBox.warning(
                self,
                "No Path Selected",
                "Please enter or browse to the FFmpeg executable path."
            )
            self._reset_ui()
            return
        
        path = Path(path_str)
        
        if not path.exists():
            QMessageBox.warning(
                self,
                "Path Not Found",
                f"The specified path does not exist:\n{path}"
            )
            self._reset_ui()
            return
        
        # Verify it's actually FFmpeg
        self._update_status("Verifying FFmpeg installation...")
        
        def verify_ffmpeg(progress_callback=None):
            try:
                result = subprocess.run(
                    [str(path), "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and "ffmpeg version" in result.stdout.lower():
                    # Try to find ffprobe in same directory
                    ffprobe = path.parent / ("ffprobe.exe" if platform.system() == "Windows" else "ffprobe")
                    return {
                        "ffmpeg": str(path),
                        "ffprobe": str(ffprobe) if ffprobe.exists() else str(path)
                    }
                else:
                    raise Exception("Not a valid FFmpeg executable")
            
            except Exception as e:
                raise Exception(f"Verification failed: {str(e)}")
        
        worker = Worker(verify_ffmpeg)
        worker.signals.result.connect(self._on_verification_complete)
        worker.signals.error.connect(self._on_error)
        self.thread_pool.start(worker)
    
    def _on_verification_complete(self, result):
        """Handle manual path verification completion."""
        self.ffmpeg_path = Path(result["ffmpeg"])
        self.ffprobe_path = Path(result.get("ffprobe", result["ffmpeg"]))
        self._update_status(f"✓ Verified FFmpeg: {self.ffmpeg_path}")
        self._save_and_complete()
    
    def _save_and_complete(self):
        """Save FFmpeg path to settings and complete setup."""
        if self.ffmpeg_path:
            # Update centralized manager
            ffmpeg_manager = get_ffmpeg_manager()
            ffmpeg_manager.set_ffmpeg_path(self.ffmpeg_path, self.ffprobe_path)
            
            self._log(f"Saved FFmpeg path: {self.ffmpeg_path}")
            self._update_status("✓ Setup complete!")
            
            # Emit completion signal
            self.setup_complete.emit(str(self.ffmpeg_path))
            
            # Close dialog after short delay
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, self.accept)
    
    def _on_error(self, error_info):
        """Handle worker errors."""
        exc_type, exc_value, exc_traceback = error_info
        error_msg = str(exc_value)
        
        self._update_status(f"✗ Error: {error_msg}")
        logger.error(f"Setup error: {exc_traceback}")
        
        QMessageBox.critical(
            self,
            "Setup Error",
            f"An error occurred during setup:\n\n{error_msg}\n\n"
            "Please try a different setup method or check the logs for details."
        )
        
        self._reset_ui()
    
    def _reset_ui(self):
        """Reset UI to allow retry."""
        self.setup_btn.setEnabled(True)
        self.method_group.setExclusive(False)
        for button in self.method_group.buttons():
            button.setEnabled(True)
        self.method_group.setExclusive(True)
        self.progress_bar.setVisible(False)
    
    def _on_cancel(self):
        """Handle cancel button."""
        if self.required:
            result = QMessageBox.question(
                self,
                "Cancel Setup",
                "FFmpeg is required for EncodeForge to function.\n\n"
                "Are you sure you want to cancel?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                self.reject()
        else:
            self.reject()
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.required and not self.ffmpeg_path:
            result = QMessageBox.question(
                self,
                "Close Setup",
                "FFmpeg setup is not complete.\n\n"
                "Are you sure you want to close this dialog?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if result == QMessageBox.No:
                event.ignore()
                return
        
        event.accept()


if __name__ == "__main__":
    # Test the dialog
    import sys

    from PySide6.QtWidgets import QApplication

    from utils.logging_config import setup_logging
    
    setup_logging()
    
    app = QApplication(sys.argv)
    
    dialog = FFmpegSetupDialog(required=False)
    dialog.setup_complete.connect(lambda path: print(f"Setup complete: {path}"))
    
    result = dialog.exec()
    print(f"Dialog result: {'Accepted' if result else 'Rejected'}")
    
    sys.exit()
