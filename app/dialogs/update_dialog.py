"""
Release notes and update actions.
"""

import qtawesome as qta
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout

from app.widgets.custom_widgets import GlassmorphicButton, PrimaryButton, StyledLabel
from utils.update_checker import ReleaseInfo


class UpdateAvailableDialog(QDialog):
    def __init__(self, release: ReleaseInfo, current_version: str, parent=None):
        super().__init__(parent)
        self._release = release
        self.setWindowTitle("Update available")
        self.setMinimumSize(480, 420)
        self.resize(520, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        head = StyledLabel(f"EncodeForge {release.version}")
        head.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: rgba(255,255,255,0.95);"
        )
        layout.addWidget(head)

        sub = StyledLabel(f"You are on {current_version}. Latest release: {release.tag_name}.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 12px;")
        layout.addWidget(sub)

        notes_label = QLabel("Release notes")
        notes_label.setStyleSheet(
            "color: rgba(255,255,255,0.45); font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.8px; text-transform: uppercase;"
        )
        layout.addWidget(notes_label)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(release.body or "No release notes were provided.")
        body.setStyleSheet(
            "QTextEdit { background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.10); "
            "border-radius: 8px; padding: 10px; color: rgba(255,255,255,0.88); }"
        )
        layout.addWidget(body, 1)

        row = QHBoxLayout()
        row.addStretch()
        close_btn = GlassmorphicButton("Close")
        close_btn.clicked.connect(self.reject)
        row.addWidget(close_btn)

        open_btn = PrimaryButton("Open release page", qta.icon("fa5s.external-link-alt"))
        open_btn.clicked.connect(self._open_release)
        row.addWidget(open_btn)
        layout.addLayout(row)

    def _open_release(self) -> None:
        url = self._release.html_url
        if url:
            QDesktopServices.openUrl(QUrl(url))
        self.accept()
