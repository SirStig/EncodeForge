import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """
    Shared QApplication for widget-level tests. GUI tests run headless via
    QT_QPA_PLATFORM=offscreen, set above before PySide6 touches a display.
    """
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _no_real_desktop_notifications(monkeypatch):
    """
    NotificationManager spins up a background thread that drives desktop-notifier's
    async backend (dbus_fast on Linux, UNUserNotificationCenter on macOS, WinRT toast
    on Windows). Headless CI runners have no notification service to talk to, and the
    native backend calls racing against that background thread have been observed to
    segfault the interpreter rather than raise a catchable exception.

    Stub DesktopNotifier.send and keep NotificationManager._ensure_loop from
    starting the asyncio thread, so widget tests cannot leave a dangling notifier
    thread racing Qt/shiboken GC. Instance-level monkeypatches in dedicated
    notification unit tests still win over this class-level stub.
    """
    from desktop_notifier import DesktopNotifier
    from utils.notifications import NotificationManager

    async def _noop_send(self, *args, **kwargs):
        return None

    monkeypatch.setattr(DesktopNotifier, "send", _noop_send)
    monkeypatch.setattr(NotificationManager, "_ensure_loop", lambda self: None)


@pytest.fixture
def isolated_app_data(tmp_path, monkeypatch):
    """
    Point EncodeForge app data at tmp_path and reset the settings singleton
    so tests do not read or write the real user config directory.
    """
    import core.path_manager as pm
    from utils.settings_manager import SettingsManager

    previous = pm._base_dir
    pm._base_dir = tmp_path
    SettingsManager._instance = None
    yield tmp_path
    SettingsManager._instance = None
    pm._base_dir = previous


@pytest.fixture
def qt_widget(qapp):
    """
    Yield a factory that tracks QWidget instances and tears them down with
    deleteLater + processEvents so shiboken does not GC half-alive wrappers
    between tests (observed as native aborts under PySide6 6.12+).
    """
    widgets = []

    def _track(widget):
        widgets.append(widget)
        return widget

    yield _track

    for widget in reversed(widgets):
        try:
            widget.close()
            widget.deleteLater()
        except RuntimeError:
            # Already deleted by Qt.
            pass
    qapp.processEvents()
    widgets.clear()
