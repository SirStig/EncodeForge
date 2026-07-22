# Releasing EncodeForge

These are manual steps. They were previously in `prepare_release.sh`, which
looked like an executable release process but only printed this text — running
it did nothing and invited the assumption that a release had been prepared.

Check the current version with:

```bash
python3 -c "from app import __version__; print(__version__)"
```

## 1. Install build dependencies

```bash
pip install -r requirements-dev.txt   # includes Nuitka, ordered-set, zstandard
```

## 2. Compile

```bash
python3 build_nuitka.py
```

For a Windows single-file executable:

```bash
NUITKA_ONEFILE=1 python3 build_nuitka.py
```

## 3. Build platform installers

Outputs land under `dist-packages/`.

**macOS**

```bash
export CODESIGN_IDENTITY='Developer ID Application: … (TEAM_ID)'
./packaging/macos/build-release-macos.sh
```

Notarisation is optional and skipped unless configured. Set `NOTARY_PROFILE`
(default `AC_PASSWORD`) after running `xcrun notarytool store-credentials`.

**Linux**

```bash
./packaging/linux/build-deb-rpm.sh
./packaging/linux/build-appimage.sh
```

Requires `fpm` (`gem install fpm`) for deb/rpm, and `appimagetool` on `PATH`
for the AppImage.

**Windows**

```powershell
powershell -File packaging/windows/package-zip.ps1
```

## 4. Verify before tagging

- Bump `__version__` in `app/__init__.py`. It is the single source of truth —
  `setup.py` and the settings file stamp both read it, so nothing else needs
  editing.
- Tag the release to match, prefixed with `v` (`v0.5.0`). Pre-release tags keep
  their suffix (`v0.5.1-beta-1`): the update checker compares full PEP 440
  versions, so the suffix is significant and must not be dropped.
- Update `CHANGELOG.md` and the version strings in `docs/index.html`,
  `docs/guide.html`, and `README.md`. The download page reads GitHub Releases
  at runtime and needs no edit.
- CI runs the unit suite on every branch; confirm it is green.
