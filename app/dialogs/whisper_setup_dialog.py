"""
Whisper AI Setup Dialog
Provides installation and model management for faster-whisper.
"""

import logging

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

_STATUS_STYLE = {
    "ok":      "color: #3fc66d; font-weight: bold;",
    "warn":    "color: #e8a040; font-weight: bold;",
    "error":   "color: #e05050; font-weight: bold;",
}

_MODEL_ROWS = [
    # (model_name, label, badge)
    ("tiny",            "Tiny  — 75 MB",              "fastest"),
    ("base",            "Base  — 145 MB",             ""),
    ("small",           "Small  — 466 MB",            ""),
    ("medium",          "Medium  — 1.5 GB",           "balanced"),
    ("large-v2",        "Large v2  — 2.9 GB",         ""),
    ("large-v3",        "Large v3  — 2.9 GB",         "best accuracy"),
    ("large-v3-turbo",  "Large v3 Turbo  — 1.6 GB",  "recommended"),
]


class _WorkerSignals(QObject):
    progress = Signal(dict)
    finished = Signal(bool, str)


class _WhisperWorker(QRunnable):
    """Background worker for install / model download."""

    def __init__(self, task: str, model_name: str = ""):
        super().__init__()
        self.task = task
        self.model_name = model_name
        self.signals = _WorkerSignals()

    def run(self):
        try:
            from core.providers.subtitle.whisper_manager import WhisperManager
            mgr = WhisperManager()
            if self.task == "install":
                ok, msg = mgr.install_whisper(progress_callback=self.signals.progress.emit)
            else:
                ok, msg = mgr.download_model(
                    self.model_name,
                    progress_callback=self.signals.progress.emit,
                )
            self.signals.finished.emit(ok, msg)
        except Exception as exc:
            logger.exception("Whisper worker error")
            self.signals.finished.emit(False, str(exc))


class WhisperSetupDialog(QDialog):
    """Dialog for installing faster-whisper and downloading models."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Whisper AI Setup")
        self.setMinimumSize(540, 480)
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(1)
        self._model_btns: dict[str, QPushButton] = {}
        self._setup_ui()
        self._refresh_status()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Status banner ──────────────────────────────────────────────
        banner = QFrame()
        banner.setObjectName("whisper_banner")
        banner.setFrameShape(QFrame.Shape.StyledPanel)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)

        col = QVBoxLayout()
        col.setSpacing(2)
        self._status_label = QLabel("Checking…")
        self._status_label.setFont(QFont(self.font().family(), -1, QFont.Weight.Bold))
        col.addWidget(self._status_label)
        self._device_label = QLabel("")
        self._device_label.setStyleSheet("color: #888; font-size: 11px;")
        col.addWidget(self._device_label)
        self._models_label = QLabel("")
        self._models_label.setStyleSheet("color: #888; font-size: 11px;")
        col.addWidget(self._models_label)
        banner_layout.addLayout(col, 1)

        self._install_btn = QPushButton("Install faster-whisper")
        self._install_btn.setMinimumWidth(180)
        self._install_btn.clicked.connect(self._run_install)
        banner_layout.addWidget(self._install_btn)

        root.addWidget(banner)

        # ── Info blurb ────────────────────────────────────────────────
        info = QLabel(
            "faster-whisper uses CTranslate2 — no manual GPU driver selection needed. "
            "CUDA is detected automatically if NVIDIA drivers are installed."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(info)

        # ── Model grid ────────────────────────────────────────────────
        model_group = QGroupBox("Models")
        model_layout = QVBoxLayout(model_group)
        model_layout.setSpacing(6)

        for model_name, label_text, badge in _MODEL_ROWS:
            row = QHBoxLayout()
            row.setSpacing(8)

            self._model_btns[model_name] = QPushButton("Download")
            self._model_btns[model_name].setFixedWidth(96)
            self._model_btns[model_name].clicked.connect(
                lambda checked=False, m=model_name: self._run_download(m)
            )
            row.addWidget(self._model_btns[model_name])

            lbl = QLabel(label_text)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            row.addWidget(lbl)

            if badge:
                badge_lbl = QLabel(badge)
                badge_lbl.setStyleSheet(
                    "color: #fff; background: #3a7bd5; border-radius: 4px; "
                    "padding: 1px 6px; font-size: 10px;"
                )
                row.addWidget(badge_lbl)

            model_layout.addLayout(row)

        root.addWidget(model_group)

        # ── Progress ──────────────────────────────────────────────────
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setVisible(False)
        root.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet("font-size: 11px; color: #aaa;")
        root.addWidget(self._progress_label)

        # ── Log ───────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(90)
        self._log.setStyleSheet("font-size: 10px;")
        root.addWidget(self._log)

        # ── Close ─────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Status refresh
    # ------------------------------------------------------------------

    def _refresh_status(self):
        try:
            from core.providers.subtitle.whisper_manager import WhisperManager
            mgr = WhisperManager()

            if mgr.whisper_available:
                self._status_label.setText("faster-whisper is installed")
                self._status_label.setStyleSheet(_STATUS_STYLE["ok"])
                self._install_btn.setText("Re-install / Update")

                device_display = {
                    "cuda": "NVIDIA GPU (CUDA)",
                    "auto": "Apple Silicon (Metal)",
                    "cpu": "CPU",
                }.get(mgr.device, mgr.device)
                self._device_label.setText(f"Compute device: {device_display}")

                if mgr.installed_models:
                    self._models_label.setText(
                        f"Downloaded models: {', '.join(mgr.installed_models)}"
                    )
                    self._models_label.setStyleSheet(_STATUS_STYLE["ok"] + " font-size: 11px;")
                else:
                    self._models_label.setText("No models downloaded yet — pick one below")
                    self._models_label.setStyleSheet(_STATUS_STYLE["warn"] + " font-size: 11px;")
            else:
                self._status_label.setText("faster-whisper is not installed")
                self._status_label.setStyleSheet(_STATUS_STYLE["error"])
                self._device_label.setText("")
                self._models_label.setText("")
                self._install_btn.setText("Install faster-whisper")

            # Update per-model button labels
            installed = set(mgr.installed_models)
            for model_name, btn in self._model_btns.items():
                if model_name in installed:
                    btn.setText("Re-download")
                    btn.setEnabled(mgr.whisper_available)
                else:
                    btn.setText("Download")
                    btn.setEnabled(mgr.whisper_available)

        except Exception as exc:
            self._status_label.setText(f"Status check failed: {exc}")
            self._status_label.setStyleSheet(_STATUS_STYLE["error"])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool):
        self._install_btn.setEnabled(not busy)
        for btn in self._model_btns.values():
            btn.setEnabled(not busy)
        self._progress_bar.setVisible(busy)
        if not busy:
            self._progress_bar.setValue(0)

    def _run_install(self):
        self._set_busy(True)
        self._log_line("Starting faster-whisper installation…")
        worker = _WhisperWorker("install")
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        self._pool.start(worker)

    def _run_download(self, model_name: str):
        self._set_busy(True)
        self._log_line(f"Downloading model: {model_name}…")
        worker = _WhisperWorker("download", model_name)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        self._pool.start(worker)

    def _on_progress(self, data: dict):
        msg = data.get("message", "")
        pct = int(data.get("progress", 0))
        self._progress_bar.setValue(pct)
        self._progress_label.setText(msg)
        if msg:
            self._log_line(msg)

    def _on_finished(self, ok: bool, message: str):
        self._set_busy(False)
        self._progress_label.setText("")
        self._log_line(f"{'Done' if ok else 'Failed'}: {message}")
        self._refresh_status()
        if not ok:
            QMessageBox.warning(self, "Whisper Setup", f"Operation failed:\n\n{message}")

    def _log_line(self, text: str):
        self._log.append(text)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())
