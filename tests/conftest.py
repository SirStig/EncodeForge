import pytest


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
