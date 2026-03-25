"""
Whisper AI Setup Dialog
Provides installation and model management for Whisper AI
"""

import logging

from PySide6.QtCore import QRunnable, QThreadPool, Qt, Signal, QObject
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class _WorkerSignals(QObject):
    progress = Signal(dict)
    finished = Signal(bool, str)


class _WhisperWorker(QRunnable):
    """Background worker for Whisper install / model download."""

    def __init__(self, task: str, model_name: str = ""):
        super().__init__()
        self.task = task          # "install" or "download"
        self.model_name = model_name
        self.signals = _WorkerSignals()

    def run(self):
        try:
            from core.providers.subtitle.whisper_manager import WhisperManager
            mgr = WhisperManager()
            if self.task == "install":
                ok, msg = mgr.install_whisper(progress_callback=self._emit)
            else:
                ok, msg = mgr.download_model(self.model_name, progress_callback=self._emit)
            self.signals.finished.emit(ok, msg)
        except Exception as exc:
            logger.exception("Whisper worker error")
            self.signals.finished.emit(False, str(exc))

    def _emit(self, data: dict):
        self.signals.progress.emit(data)


class WhisperSetupDialog(QDialog):
    """Dialog for installing Whisper AI and downloading models."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Whisper AI Setup")
        self.setMinimumSize(520, 400)
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(1)
        self._setup_ui()
        self._refresh_status()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Status group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)

        self._status_label = QLabel("Checking…")
        status_layout.addWidget(self._status_label)

        self._device_label = QLabel("")
        status_layout.addWidget(self._device_label)

        layout.addWidget(status_group)

        # Install group
        install_group = QGroupBox("Install / Update Whisper")
        install_layout = QVBoxLayout(install_group)

        install_layout.addWidget(QLabel(
            "Installs openai-whisper and PyTorch with the best available\n"
            "backend (CUDA, ROCm, MPS, or CPU-only) for your hardware."
        ))

        self._install_btn = QPushButton("Install Whisper")
        self._install_btn.clicked.connect(self._run_install)
        install_layout.addWidget(self._install_btn)

        layout.addWidget(install_group)

        # Model download group
        model_group = QGroupBox("Download Model")
        model_layout = QHBoxLayout(model_group)

        model_layout.addWidget(QLabel("Model:"))
        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "tiny (75 MB)", "base (142 MB)", "small (466 MB)",
            "medium (1.5 GB)", "large (2.9 GB)", "large-v2 (2.9 GB)", "large-v3 (2.9 GB)"
        ])
        model_layout.addWidget(self._model_combo, 1)

        self._download_btn = QPushButton("Download")
        self._download_btn.clicked.connect(self._run_download)
        model_layout.addWidget(self._download_btn)

        layout.addWidget(model_group)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_label)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        layout.addWidget(self._log)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _refresh_status(self):
        try:
            from core.providers.subtitle.whisper_manager import WhisperManager
            mgr = WhisperManager()
            if mgr.whisper_available:
                installed = ", ".join(mgr.installed_models) if mgr.installed_models else "none downloaded"
                self._status_label.setText(f"Whisper: Installed  |  Models: {installed}")
            else:
                self._status_label.setText("Whisper: Not installed")
            self._device_label.setText(f"Detected device: {mgr.device}")
        except Exception as exc:
            self._status_label.setText(f"Status check failed: {exc}")

    def _set_busy(self, busy: bool):
        self._install_btn.setEnabled(not busy)
        self._download_btn.setEnabled(not busy)
        self._progress_bar.setVisible(busy)
        if not busy:
            self._progress_bar.setValue(0)

    def _run_install(self):
        self._set_busy(True)
        self._log_line("Starting Whisper installation…")
        worker = _WhisperWorker("install")
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        self._pool.start(worker)

    def _run_download(self):
        model_name = self._model_combo.currentText().split()[0]
        self._set_busy(True)
        self._log_line(f"Downloading model: {model_name}…")
        worker = _WhisperWorker("download", model_name)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        self._pool.start(worker)

    def _on_progress(self, data: dict):
        msg = data.get("message", "")
        pct = data.get("progress", 0)
        self._progress_bar.setValue(int(pct))
        self._progress_label.setText(msg)
        if msg:
            self._log_line(msg)

    def _on_finished(self, ok: bool, message: str):
        self._set_busy(False)
        self._progress_label.setText("")
        self._log_line(f"{'Done' if ok else 'Failed'}: {message}")
        self._refresh_status()
        if not ok:
            QMessageBox.warning(self, "Whisper Setup", f"Operation failed:\n{message}")

    def _log_line(self, text: str):
        self._log.append(text)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())
