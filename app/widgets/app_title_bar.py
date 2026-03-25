from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QSizePolicy, QToolButton, QWidget

from utils.design_tokens import default_tokens

_ICONS_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "icons"


class AppTitleBar(QFrame):
    def __init__(self, parent: QWidget | None = None, title: str = ""):
        super().__init__(parent)
        self.setObjectName("app_title_bar")
        self._drag_offset = None
        self._state_hooked = False

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 0, 4, 0)
        root.setSpacing(6)

        icon = QLabel()
        app_icon_path = _ICONS_DIR / "app-icon.png"
        if app_icon_path.exists():
            pix = QPixmap(str(app_icon_path)).scaled(
                14, 14,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon.setPixmap(pix)
        else:
            icon.setPixmap(qta.icon("fa5s.film").pixmap(12, 12))
        icon.setFixedSize(18, 18)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(icon)

        self._title = QLabel(title)
        self._title.setObjectName("titlebar_title")
        self._title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        root.addWidget(self._title)

        root.addStretch(1)

        self._menu_btn = QToolButton(self)
        self._menu_btn.setObjectName("titlebar_menu")
        self._menu_btn.setIcon(qta.icon("fa5s.ellipsis-v"))
        self._menu_btn.setAutoRaise(True)
        self._menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu_btn.setVisible(False)
        root.addWidget(self._menu_btn)

        self._btn_min = QToolButton(self)
        self._btn_min.setObjectName("titlebar_control")
        self._btn_min.setIcon(qta.icon("fa5s.window-minimize"))
        self._btn_min.setAutoRaise(True)
        self._btn_min.clicked.connect(self._on_minimize)
        root.addWidget(self._btn_min)

        self._btn_max = QToolButton(self)
        self._btn_max.setObjectName("titlebar_control")
        self._btn_max.setAutoRaise(True)
        self._btn_max.clicked.connect(self._on_maximize_toggle)
        root.addWidget(self._btn_max)

        self._btn_close = QToolButton(self)
        self._btn_close.setObjectName("titlebar_control")
        self._btn_close.setIcon(qta.icon("fa5s.times"))
        self._btn_close.setAutoRaise(True)
        self._btn_close.clicked.connect(self._on_close)
        root.addWidget(self._btn_close)

        _ib = QSize(12, 12)
        for _b in (self._menu_btn, self._btn_min, self._btn_max, self._btn_close):
            _b.setIconSize(_ib)
            _b.setFixedSize(22, 22)

        _th = int(default_tokens().title_bar_height.replace("px", "").strip())
        self.setFixedHeight(_th)
        self._sync_max_button()

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_menu(self, menu: QMenu) -> None:
        self._menu_btn.setMenu(menu)
        self._menu_btn.setVisible(True)

    def _ensure_window_state_hook(self) -> None:
        if self._state_hooked:
            return
        win = self.window()
        wh = win.windowHandle() if win else None
        if wh is None:
            return
        wh.windowStateChanged.connect(self._sync_max_button)
        self._state_hooked = True

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_window_state_hook()
        self._sync_max_button()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ParentChange:
            self._state_hooked = False
            self._ensure_window_state_hook()
            self._sync_max_button()

    def _hit_is_draggable(self, pos) -> bool:
        child = self.childAt(pos)
        w = child
        while w is not None and w is not self:
            if w.objectName() in ("titlebar_control", "titlebar_menu"):
                return False
            w = w.parentWidget()
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._hit_is_draggable(
            event.position().toPoint()
        ):
            super().mousePressEvent(event)
            return
        win = self.window()
        self._drag_offset = None
        wh = win.windowHandle() if win else None
        if wh is not None:
            sm = getattr(wh, "startSystemMove", None)
            if callable(sm):
                sm()
                super().mousePressEvent(event)
                return
        self._drag_offset = event.globalPosition().toPoint() - win.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            win = self.window()
            if win is not None and not win.isMaximized():
                win.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._hit_is_draggable(
            event.position().toPoint()
        ):
            super().mouseDoubleClickEvent(event)
            return
        win = self.window()
        if win is None:
            super().mouseDoubleClickEvent(event)
            return
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()
        self._sync_max_button()
        super().mouseDoubleClickEvent(event)

    def _sync_max_button(self) -> None:
        win = self.window()
        if win is None:
            return
        if win.isMaximized():
            self._btn_max.setIcon(qta.icon("fa5s.window-restore"))
        else:
            self._btn_max.setIcon(qta.icon("fa5s.window-maximize"))

    def _on_minimize(self) -> None:
        win = self.window()
        if win is not None:
            win.showMinimized()

    def _on_maximize_toggle(self) -> None:
        win = self.window()
        if win is None:
            return
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()
        self._sync_max_button()

    def _on_close(self) -> None:
        win = self.window()
        if win is not None:
            win.close()
