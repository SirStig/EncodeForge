# EncodeForge PySide6 Migration - Project Structure

## Overview
This document describes the new Python/PySide6 project structure after migrating from Java/JavaFX.

## Directory Structure

```
EncodeForge/
├── main.py                    # Main GUI entry point
├── cli.py                     # Command-line interface
├── setup.py                   # Package configuration
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── build_nuitka.py           # Nuitka build script
├── build.bat / build.sh      # Platform-specific build scripts
├── .gitignore                # Git ignore patterns (Python-focused)
├── README.md                 # Modern professional README
├── LICENSE                   # MIT License
├── CHANGELOG.md              # Version history
│
├── app/                      # PySide6 GUI application
│   ├── __init__.py
│   ├── main_window.py        # Main application window
│   └── widgets/              # Custom Qt widgets
│       └── __init__.py
│
├── core/                     # Business logic (from Java project)
│   ├── __init__.py
│   ├── ffmpeg_core.py        # FFmpeg operations
│   ├── ffmpeg_manager.py     # FFmpeg installation/management
│   ├── metadata_grabber.py   # Metadata retrieval
│   ├── subtitle_manager.py   # Subtitle handling
│   ├── profile_manager.py    # Encoding profiles
│   ├── path_manager.py       # Path utilities
│   ├── resource_manager.py   # Resource management
│   ├── dependency_checker.py # Dependency validation
│   ├── encodeforge_core.py   # Core business logic
│   │
│   ├── providers/            # External service providers
│   │   ├── __init__.py
│   │   ├── metadata/         # Metadata providers
│   │   │   ├── __init__.py
│   │   │   ├── base_provider.py
│   │   │   ├── tmdb_provider.py
│   │   │   ├── tvdb_provider.py
│   │   │   ├── omdb_provider.py
│   │   │   ├── anidb_provider.py
│   │   │   ├── kitsu_provider.py
│   │   │   ├── jikan_provider.py
│   │   │   ├── tvmaze_provider.py
│   │   │   └── trakt_provider.py
│   │   │
│   │   └── subtitle/         # Subtitle providers
│   │       ├── __init__.py
│   │       ├── base_provider.py
│   │       ├── opensubtitles_manager.py
│   │       ├── whisper_manager.py
│   │       ├── addic7ed_provider.py
│   │       ├── subdl_provider.py
│   │       ├── subf2m_provider.py
│   │       ├── yify_provider.py
│   │       ├── podnapisi_provider.py
│   │       ├── subdivx_provider.py
│   │       ├── kitsunekko_provider.py
│   │       └── jimaku_provider.py
│   │
│   └── handlers/             # Operation handlers
│       ├── __init__.py
│       ├── conversion_handler.py
│       ├── file_handler.py
│       ├── renaming_handler.py
│       ├── subtitle_handler.py
│       └── models.py
│
├── resources/                # Application resources
│   ├── icons/                # Application icons
│   │   └── app-icon.png
│   └── styles/               # Qt stylesheets (if needed)
│
├── utils/                    # Utility functions
│   └── __init__.py
│
├── config/                   # Configuration files (preserved)
│
├── docs/                     # Documentation (to be updated)
│   ├── index.html
│   ├── sitemap.xml
│   └── screenshots/
│
├── venv/                     # Virtual environment
├── .vscode/                  # VS Code settings
├── .github/                  # GitHub workflows (to be updated)
│
└── EncodeForge/              # PRESERVED: Original Java project
    ├── pom.xml
    ├── src/
    └── target/
```

## Key Changes

### ✅ Completed

1. **New Structure Created**
   - `app/` - PySide6 GUI components
   - `core/` - Business logic copied from Java project
   - `core/providers/metadata/` - Metadata provider modules
   - `core/providers/subtitle/` - Subtitle provider modules
   - `core/handlers/` - Operation handlers
   - `resources/` - Icons and styles
   - `utils/` - Utility functions

2. **Entry Points**
   - `main.py` - PySide6 GUI application with QThreadPool
   - `cli.py` - Click-based CLI interface
   - `setup.py` - Package configuration

3. **Build System**
   - `build_nuitka.py` - Cross-platform Nuitka compilation
   - `build.bat` / `build.sh` - Platform-specific build scripts
   - Configured for Windows, macOS, and Linux

4. **Dependencies**
   - `requirements.txt` - Production dependencies (PySide6, Nuitka, etc.)
   - `requirements-dev.txt` - Development tools (pytest, black, mypy)

5. **Documentation**
   - Modern professional README inspired by Ghost-Downloader-3
   - Clear feature sections, installation guides, quick start
   - Removed all Java/JavaFX references

6. **Git Configuration**
   - Updated `.gitignore` for Python/Qt project
   - Marked obsolete directories (dist-deb, dist-rpm, dist-macos, docker)

### ⏳ Remaining Tasks

1. **Delete Obsolete Directories**
   - Remove `dist-deb/`, `dist-macos/`, `dist-rpm/`, `docker/`
   - Keep `EncodeForge/` (Java project) as requested

2. **Update GitHub Files**
   - Modify `.github/workflows/` for Python/PySide6
   - Update issue templates
   - Update PR templates

3. **Update Documentation Website**
   - Modify `docs/` folder content
   - Update for Python/PySide6 stack

4. **Backend Refactoring**
   - Break large Python files into smaller modules (<500 lines)
   - Improve modularization

5. **UI Development**
   - Build out encoder, subtitle, and renamer tabs
   - Integrate pyqt-fluent-widgets components
   - Add file browser, progress tracking, etc.

6. **Threading Implementation**
   - Implement QRunnable workers for video processing
   - Add progress signals/slots
   - Handle cancellation and errors

## Technology Stack

### UI Layer
- **PySide6** - Qt6 for Python
- **PyQt-Fluent-Widgets** - Modern UI components (free version)

### Business Logic
- **FFmpeg** - Video/audio processing
- **OpenAI Whisper** - AI subtitle generation
- **Metadata Providers** - TMDB, TVDB, OMDB, AniDB, Kitsu, etc.
- **Subtitle Providers** - OpenSubtitles, Whisper, web scrapers

### Build & Distribution
- **Nuitka** - Python compiler for standalone executables
- **setuptools** - Package management

### Development
- **pytest** - Testing framework
- **black** - Code formatter
- **mypy** - Type checking
- **flake8** - Linting

## Next Steps

1. Delete obsolete distribution directories
2. Update GitHub workflows and templates
3. Refactor large Python files into smaller modules
4. Build out PySide6 UI tabs (encoder, subtitle, renamer)
5. Implement concurrent task processing with QThreadPool
6. Test Nuitka builds on all platforms
7. Update documentation website

## Notes

- Java project (`EncodeForge/`) preserved as requested
- WebUI support completely dropped
- CLI support maintained and enhanced
- All Python files copied, not moved
- Structure designed for modularity and maintainability
