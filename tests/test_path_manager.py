import core.path_manager as pm


def test_subdirs_under_isolated_base(isolated_app_data):
    base = isolated_app_data
    assert pm.get_base_dir() == base
    logs = pm.get_logs_dir()
    cache = pm.get_cache_dir()
    assert logs.parent == base
    assert cache.parent == base
    assert (base / "settings.json") == pm.get_settings_file()
