import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """
    Shared QApplication for widget-level tests. GUI tests run headless via
    QT_QPA_PLATFORM=offscreen, set above before PySide6 touches a display.
    """
    pyside6 = pytest.importorskip("PySide6")
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
    segfault the interpreter rather than raise a catchable exception. Stub the one
    shared async entrypoint so no test — even ones that never touch notifications.py
    directly, e.g. via _apply_rename's success/error paths — reaches real OS APIs.
    """
    from desktop_notifier import DesktopNotifier

    async def _noop_send(self, *args, **kwargs):
        return None

    monkeypatch.setattr(DesktopNotifier, "send", _noop_send)


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
