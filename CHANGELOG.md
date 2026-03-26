# Changelog

All notable changes to EncodeForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0-alpha-1] — 2026-03-25

> **First PySide6 pre-release on GitHub Releases.** Installers for **macOS (Apple Silicon)** and **Windows** are published; **Linux** packages (.deb, .rpm, AppImage) are not uploaded yet. The previous **[v0.4.1](https://github.com/SirStig/EncodeForge/releases/tag/v0.4.1)** line was JavaFX (deprecated).

### Highlights

**Complete rewrite from JavaFX to PySide6.** EncodeForge has been rebuilt from the ground up using Python and PySide6 with Fluent Design components. The legacy JavaFX/Java codebase has been retired entirely. The GUI and CLI now share a single core (`EncodeForgeCore`) with no logic duplication.

---

### Fixed

#### FFmpeg & Conversion Pipeline

- **FFmpeg path resolution** — All FFmpeg/FFprobe subprocess calls now route through `FFmpegManager` instead of falling back to bare `"ffmpeg"`/`"ffprobe"` strings. On systems where FFmpeg is installed outside of `PATH` (e.g. Homebrew-only macOS, custom Windows installs), conversions previously failed silently. They now raise a clear error if FFmpeg is not detected.
- **FFmpeg detection fallthrough** — If `shutil.which()` resolves FFmpeg to a broken binary (e.g. a dead Homebrew symlink), detection no longer stops there. It now logs a warning and continues searching common installation paths on all platforms.
- **FFprobe auto-detection** — `get_ffprobe_path()` now triggers the full FFmpeg detection routine when called before detection has run, instead of silently returning `None`.
- **Audio normalization with stream copy** — Enabling audio normalization (`loudnorm` filter) while the audio codec was set to `copy` caused a hard FFmpeg error, because filters cannot be applied to a copy stream. The codec is now automatically switched to `aac` in this case, with a log warning explaining the override.
- **10-bit video H.264 hardware fallback** — The fallback path that re-encodes 10-bit sources to 8-bit H.264 using hardware encoders (NVENC, AMF, QSV, VideoToolbox) was structurally unreachable — it shared the same conditions as the HEVC block above it, so if HEVC hardware was available it returned early, and if it wasn't, the H.264 block couldn't match either. The fallback now correctly activates only when no HEVC hardware encoder is found.
- **Unsafe FPS parsing** — Frame rate values from FFprobe were parsed using `eval()`, which could crash on malformed input (e.g. `0/0` raises `ZeroDivisionError`) and is generally unsafe. Replaced with `fractions.Fraction` for safe, stdlib-only parsing.
- **Partial output file cleanup** — When a conversion fails or produces an empty output file, the partial file is now deleted automatically. Previously it was left on disk, blocking re-runs unless `overwrite_existing` was enabled.
- **Output path deduplication loop** — The loop that generates unique output filenames (e.g. `video_1.mp4`, `video_2.mp4`) had no upper bound. Added a 9,999-attempt cap that returns a clear error instead of looping indefinitely.
- **`audio_track_selection` not persisted** — The audio track selection (`all` / `first audio only`) was read via `getattr` with a default because the field was missing from `ConversionSettings`. It is now a proper dataclass field and will round-trip correctly through settings serialization.

#### GPU Detection

- **AMD GPU detection via rocm-smi** — The rocm-smi output parser checked for `'Card series'` (lowercase `s`) but the actual output uses `'Card Series'` (capital `S`), causing AMD GPUs to never be detected on ROCm Linux systems. Fixed with a case-insensitive match and corrected column extraction.
- **GPU detection on Windows 11** — `wmic`, used to detect AMD and Intel GPUs, has been removed from some Windows 11 builds. Both `_detect_amd` and `_detect_intel` now fall back to `Get-CimInstance Win32_VideoController` via PowerShell when `wmic` is unavailable.

#### Subtitle Providers

- **OpenSubtitles.com** — Fixed a circular import crash (`from subtitle_manager import SubtitleProviders`) that caused a `ModuleNotFoundError` at runtime whenever a search was attempted. `OpenSubtitlesManager` now properly extends `BaseSubtitleProvider` and calls `self.extract_media_metadata()` directly.
- **Addic7ed** — Fixed the episode subtitle search navigating to the show overview page (`/show/{id}`) instead of the season page (`/show/{id}/{season}`), which caused the provider to never return episode-specific results. Download method now uses the stored `download_url` directly instead of re-searching with a garbled file ID.
- **SubDL** — Expanded language code conversion from 5 languages to the full set of 30+ supported ISO 639-2 codes. Previously, uncommon languages silently fell back to wrong 2-letter prefixes.
- **`subtitle_manager.py`** — Removed stale `self.providers` list referencing non-existent internal names. Replaced 4-language hardcoded language normalization with a complete 2-letter → 3-letter mapping (30+ languages). Removed phantom provider names (`Subscene`, `AnimeSubtitles`) from the scoring table.

---

### Added

#### Architecture

- **`EncodeForgeCore`** — New single entry point for all GUI and CLI operations. Lazily initializes handlers on first use via a thread lock, keeping startup fast even with heavy dependencies like Whisper.
- **Handler layer** — `ConversionHandler`, `FileHandler`, `SubtitleHandler`, `RenamingHandler` contain all business logic; no UI code in core.
- **Provider layer** — Abstract-base + concrete-implementation pattern for both metadata (8+ providers) and subtitle (8+ providers) subsystems.
- **`SettingsManager`** — JSON-backed nested dataclass settings (`EncoderSettings`, `SubtitleSettings`, `RenamerSettings`, `UISettings`).
- **`DownloadManager`** — Resumable downloads with SHA256 hash verification and progress callbacks.
- **`ThemeManager`** — Glassmorphism CSS theming with dark/light mode support.
- **`WorkerPool`** — QThread-based worker pool with signal/slot progress integration.

#### GUI (PySide6 + PyQt-Fluent-Widgets)

- Tabbed `MainWindow` — Encoder, Subtitles, Renamer, Processes, and Settings tabs.
- Real-time per-file and overall progress bars.
- Drag-and-drop file addition across all tabs.
- Comprehensive log viewer with export support.
- `FFmpegSetupDialog` — Detects, downloads, and configures FFmpeg on first launch.
- `SettingsDialog` — Full settings UI with API key management and hardware acceleration toggle.

#### CLI

- Full CLI built with Click, sharing `EncodeForgeCore` with the GUI.
- Commands: `encode`, `subtitle`, `rename`, `gui`.
- `encodeforge`, `encodeforge-cli`, `encodeforge-gui` entry points via `setup.py`.

#### Metadata Providers

- TMDB, TVDB, OMDB, Trakt, Fanart.tv, AniDB, Kitsu, Jikan/MAL, TVmaze
- `MetadataGrabber` aggregates providers and returns best match with fallback chain.

#### Subtitle Providers

- OpenSubtitles.com (API), Addic7ed, SubDL (API), Subf2m, YIFY, Podnapisi, SubDivX, Jimaku (Kitsunekko was removed — see **Removed**)
- `WhisperManager` — Local AI subtitle generation via **faster-whisper** (CTranslate2) with GPU device selection (CUDA, ROCm, MPS, CPU).
- `SubtitleManager` tries providers in configured order; returns first successful result.

#### Build

- Nuitka build system (`build_nuitka.py`) produces self-contained executables for Windows and Linux.
- GitHub Actions CI for automated cross-platform builds.

---

### Removed

#### Subtitle Providers

- **Kitsunekko** — Removed. The provider was a non-functional placeholder: `search()` never made any network requests and instead fabricated fake result objects, logging "prepared N placeholder result(s)". Downloads would fail for every result it produced. The file `core/providers/subtitle/kitsunekko_provider.py` has been deleted.

#### Platform / distribution

- **JavaFX / Java codebase** — Fully retired. The previous JavaFX implementation is no longer maintained or distributed.
- Maven build system — replaced by Python packaging (`setup.py`) and Nuitka.
- JAR packaging — replaced by Nuitka-compiled native executables.

---

### Changed

- **Whisper stack** — Replaced OpenAI Whisper with PyTorch by **faster-whisper**, which uses CTranslate2 for inference: faster transcription, lower memory use, and a lighter dependency footprint than the previous PyTorch-based pipeline.
- Application rebranded from a Java desktop app to a Python/PySide6 desktop app.
- All version references updated to `0.5.0-alpha-1` for the PySide6 line.
- `setup.py` classifiers updated to reflect PySide6/Qt6 environment.

---

### Release Links

- **GitHub Release** — [v0.5.0-alpha-1](https://github.com/SirStig/EncodeForge/releases/tag/v0.5.0-alpha-1)
- **Direct downloads** — [macOS Apple Silicon (.zip)](https://github.com/SirStig/EncodeForge/releases/download/v0.5.0-alpha-1/encodeforge-macos-arm.zip) · [Windows (.exe)](https://github.com/SirStig/EncodeForge/releases/download/v0.5.0-alpha-1/EncodeForge.exe)
- **Compare** — [v0.4.1...v0.5.0-alpha-1](https://github.com/SirStig/EncodeForge/compare/v0.4.1...v0.5.0-alpha-1)

---

## [0.4.1] — 2025-10-24

> **Note:** Final **JavaFX** release (deprecated). Current binaries are the **PySide6** line; see **[v0.5.0-alpha-1](https://github.com/SirStig/EncodeForge/releases/tag/v0.5.0-alpha-1)**.

### Highlights

- Major UI refresh: reorganized logs, settings views, and modernized tables.
- Swing-based splash screen to surface startup progress and initialization errors before the main window loads.

### Fixes

- Resolved macOS launch hang affecting JavaFX initialization.

### CI/CD

- Updated macOS artifact workflow so the packaged JAR carried the 0.4.1 version label.

### Release Links

- **Full Changelog**: [0.4.0...0.4.1](https://github.com/SirStig/EncodeForge/compare/0.4.0...0.4.1)

---

## [0.4.0] — 2025-10-23

> **Note:** Final major JavaFX release. Consolidated from development branches v0.3.2 and v0.3.3.

### Added

#### Audio Normalization

- New FFmpeg flag to normalize audio levels during encoding.
- Configurable via settings; integrated into the encoding workflow.

#### GPU-Accelerated AI Subtitle Generation

- Intelligent PyTorch installation: auto-detects NVIDIA CUDA, AMD ROCm, or Apple Silicon and downloads the appropriate PyTorch build.
- Falls back to CPU if no GPU is detected.
- **10–20x speed improvement** for Whisper AI subtitle generation on supported hardware.

### Changed

- **Enhanced visual depth** — improved dark theme consistency and component minimum sizes.
- **Lazy initialization** — Whisper manager and core Python modules deferred to first use; faster startup, lower idle memory.

### Fixes

- Resolved Whisper AI setup dialog issues and improved error handling during installation.

### Release Links

- **Full Changelog**: [v0.3.1...v0.4.0](https://github.com/SirStig/EncodeForge/compare/v0.3.1...v0.4.0)

---

## [0.3.1] — 2024

### Initial Public Release

First stable public release of EncodeForge (formerly FFmpeg Batch Transcoder). Built on JavaFX.

#### Features

- Hardware-accelerated video encoding — NVENC, AMF, Quick Sync, VideoToolbox
- Batch processing with queue management and real-time progress
- AI subtitle generation via OpenAI Whisper
- 9 subtitle provider integrations
- Smart file renaming with 10 metadata providers (TMDB, TVDB, OMDB, Trakt, AniDB, Kitsu, Jikan/MAL, TVmaze, Fanart.tv)
- Custom naming patterns with preview mode
- Dark-themed JavaFX desktop application for Windows, macOS, and Linux

---

[GitHub Releases](https://github.com/SirStig/EncodeForge/releases) · [Report a Bug](https://github.com/SirStig/EncodeForge/issues) · [Request a Feature](https://github.com/SirStig/EncodeForge/discussions)
