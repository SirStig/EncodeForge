# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EncodeForge is a PySide6 desktop application for video encoding, subtitle management, and media renaming. GUI and CLI share the same core business logic. The UI is a custom flat dark theme (not Fluent Design / PyQt-Fluent-Widgets). Active development targets the `0.5.0` line.

CLI reality: `encode`, `rename`, and `gui` are implemented; `subtitle` is a stub that exits with status 2.

## Commands

### Running

```bash
python main.py          # Launch GUI
python cli.py --help    # CLI usage
python cli.py gui       # Launch GUI via CLI
```

### Development Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Code Quality

```bash
black .       # Format
flake8 .      # Lint
mypy .        # Type checking
isort .       # Sort imports
```

### Testing

```bash
pytest
pytest --cov=core --cov=app --cov=utils
```

### Building Standalone Executables

```bash
python build_nuitka.py   # Cross-platform via Nuitka
./build.sh               # macOS/Linux wrapper
```

## Architecture

The application is organized into four layers:

**GUI Layer (`app/`)** — PySide6 widgets. `main_window.py` is the tabbed root. Widgets in `app/widgets/` correspond to tabs (encoder, subtitle, metadata, logs). Dialogs in `app/dialogs/` handle FFmpeg setup and settings.

**Core Orchestrator (`core/encodeforge_core.py`)** — `EncodeForgeCore` is the single entry point for both GUI and CLI. It lazily initializes handlers on first use with a thread lock, avoiding expensive startup costs (especially Whisper AI imports).

**Handler Layer (`core/handlers/`)** — `ConversionHandler`, `FileHandler`, `SubtitleHandler`, `RenamingHandler`. These contain the actual business logic. `models.py` defines the dataclasses (`ConversionSettings`, `FileInfo`) used across the app.

**Provider Layer (`core/providers/`)** — Two sub-systems, each with an abstract base and concrete implementations:
- `metadata/`: 8+ providers (TMDB, TVDB, OMDB, Trakt, Kitsu, Jikan, AniDB, TVmaze). The `MetadataGrabber` in `core/metadata_grabber.py` aggregates them.
- `subtitle/`: 8+ providers (OpenSubtitles, Addic7ed, Jimaku, SubDL, etc.) plus `whisper_manager.py` for AI-based local subtitle generation. Aggregated in `core/subtitle_manager.py`.

**Utility Layer (`utils/`)** — Cross-cutting concerns: `ffmpeg_manager.py` (FFmpeg detection/path), `gpu_detector.py` (NVENC/AMF/VAAPI/QSV/VideoToolbox detection + OS backend matrix), `settings_manager.py` (JSON-backed dataclass config), `theme_manager.py` (flat dark CSS theming; Light/Auto not exposed until tokens exist), `workers.py` (QThread worker pool), `download_manager.py` (resumable downloads with hash verification).

### Key Patterns

- **GUI ↔ Core**: GUI widgets call `EncodeForgeCore` methods; workers emit Qt signals for progress updates back to the GUI.
- **Lazy initialization**: Both `EncodeForgeCore._ensure_handlers_initialized()` and the `whisper_mgr` property defer expensive setup to first access.
- **Shared core**: `main.py` (GUI) and `cli.py` (CLI) both use the same `EncodeForgeCore` and handlers — no logic duplication.
- **Provider fallback**: Manager classes try providers in order and return the best result.
- **Settings**: `utils/settings_manager.py` uses nested dataclasses (`EncoderSettings`, `SubtitleSettings`, `RenamerSettings`, `UISettings`) serialized to JSON via `core/path_manager.py`.

## FFmpeg Dependency

FFmpeg is required at runtime and is not bundled. On first GUI launch, `main.py` calls `check_ffmpeg()` and shows `FFmpegSetupDialog` if not found. Hardware acceleration is OS-aware: NVENC (all), AMF (Windows), VAAPI (Linux), QSV (Windows/Linux), VideoToolbox (macOS). GPU presence comes from `utils/gpu_detector.py`; FFmpeg detection/probing lives in `utils/ffmpeg_manager.py` (`core/ffmpeg_manager.py` is a thin re-export façade).

## Entry Points (from `setup.py`)

- `encodeforge` / `encodeforge-gui` → `main:main`
- `encodeforge-cli` → `cli:main`
