"""
Bottom-right toast for available updates.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QVBoxLayout

from app.widgets.custom_widgets import GlassmorphicButton, PrimaryButton, StyledLabel


class UpdateToast(QFrame):
    later_clicked = Signal()
    notes_clicked = Signal()
    download_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("update_toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = StyledLabel("Update available")
        title.setObjectName("update_toast_title")
        root.addWidget(title)

        self._subtitle = StyledLabel("")
        self._subtitle.setObjectName("update_toast_subtitle")
        self._subtitle.setWordWrap(True)
        root.addWidget(self._subtitle)

        row = QHBoxLayout()
        row.setSpacing(8)

        notes_btn = GlassmorphicButton("What's new")
        notes_btn.clicked.connect(self.notes_clicked.emit)
        row.addWidget(notes_btn)

        dl_btn = PrimaryButton("Get update")
        dl_btn.clicked.connect(self.download_clicked.emit)
        row.addWidget(dl_btn)

        later_btn = GlassmorphicButton("Later")
        later_btn.clicked.connect(self.later_clicked.emit)
        row.addWidget(later_btn)

        root.addLayout(row)

        self.setFixedWidth(340)

    def set_version_text(self, version: str, title: str = "") -> None:
        name = title.strip() if title else f"Version {version}"
        self._subtitle.setText(f"{name} is ready to install from GitHub Releases.")
