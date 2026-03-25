# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EncodeForge is a PySide6 desktop application for video encoding, subtitle management, and media renaming. It supports both a GUI and a CLI interface that share the same core business logic. The project is currently in a `pyside-refactor` branch, actively migrating and rebuilding the UI with modern Fluent Design.

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
- `subtitle/`: 9+ providers (OpenSubtitles, Addic7ed, Jimaku, SubDL, etc.) plus `whisper_manager.py` for AI-based local subtitle generation. Aggregated in `core/subtitle_manager.py`.

**Utility Layer (`utils/`)** — Cross-cutting concerns: `ffmpeg_manager.py` (FFmpeg detection/path), `gpu_detector.py` (NVENC/AMF/QSV/VideoToolbox detection), `settings_manager.py` (JSON-backed dataclass config), `theme_manager.py` (glassmorphism CSS theming), `workers.py` (QThread worker pool), `download_manager.py` (resumable downloads with hash verification).

### Key Patterns

- **GUI ↔ Core**: GUI widgets call `EncodeForgeCore` methods; workers emit Qt signals for progress updates back to the GUI.
- **Lazy initialization**: Both `EncodeForgeCore._ensure_handlers_initialized()` and the `whisper_mgr` property defer expensive setup to first access.
- **Shared core**: `main.py` (GUI) and `cli.py` (CLI) both use the same `EncodeForgeCore` and handlers — no logic duplication.
- **Provider fallback**: Manager classes try providers in order and return the best result.
- **Settings**: `utils/settings_manager.py` uses nested dataclasses (`EncoderSettings`, `SubtitleSettings`, `RenamerSettings`, `UISettings`) serialized to JSON via `core/path_manager.py`.

## FFmpeg Dependency

FFmpeg is required at runtime and is not bundled. On first GUI launch, `main.py` calls `check_ffmpeg()` and shows `FFmpegSetupDialog` if not found. Hardware acceleration (NVENC, AMF, QSV, VideoToolbox) is auto-detected via `utils/gpu_detector.py` and cached.

## Entry Points (from `setup.py`)

- `encodeforge` / `encodeforge-gui` → `main:main`
- `encodeforge-cli` → `cli:main`
