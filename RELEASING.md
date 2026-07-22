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

- Tag format must keep its pre-release suffix (`v0.5.0-alpha-3`). The update
  checker compares full PEP 440 versions, so the suffix is significant.
- Bump `__version__` in `app/__init__.py` and the `version` in `setup.py`
  together — they are separate strings today.
- CI runs the unit suite on every branch; confirm it is green.
