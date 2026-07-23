# Changelog

All notable changes to EncodeForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] — 2026-07-22

First stable release of the PySide6 rewrite. This promotes the 0.5.0 alpha line to a full release

### Fixed

- **Automatic FFmpeg download on Windows and Linux** — The downloaded archive was saved under a generic temporary name, and extraction was chosen from the file extension, so it always failed with “Unsupported archive format.” The first-run setup flow now identifies archives by content and supports `.tar.xz` (used by the Linux builds).
- **Update notifications** — The version check discarded the pre-release suffix from both sides before comparing, so every `-alpha` release compared equal and no update was ever detected. Version comparison is now full PEP 440, and a manual check no longer reports “You are up to date” when it isn’t.
- **AI subtitle generation through the subtitle handler** — An import still pointed at a package layout from before the PySide6 refactor, so Whisper reported “not available” even when it was fully installed.
- **Crash recovery of an interrupted batch** — The same class of stale import meant conversion state was never written to disk, so resuming after an interruption never worked.
- **“Convert to SRT” subtitle mode** — Called an internal method with the wrong number of arguments, failing every file that had a subtitle track. Subtitles are now transcoded in the same FFmpeg pass.
- **Hardware acceleration in the encode queue** — Encoder detection was gated on the wrong field, so encodes silently fell back to CPU even with a supported GPU. Selecting AMF, QSV, or VideoToolbox also always produced NVENC arguments; each backend is now honoured.
- **API key “Test” buttons** — Always reported `✗ Error`, including for valid keys, because the worker passed an argument the check did not accept.
- **Desktop notifications** — Five call sites used a method that did not exist, raising an error mid-operation — including on the subtitle failure path.
- **“Open Output Folder”** — Used a Windows-only API and crashed on Linux and macOS.
- **Sidebar “Add Files” / “Add Folder”** — Did nothing on the Subtitles and Metadata tabs due to a signature mismatch that was silently swallowed.
- **The Providers list on the Subtitles tab** — Was built by the UI and then discarded; every provider was queried regardless of what you selected.
- **Preview then Apply Rename** — Preview discarded the fetched metadata, so Apply silently renamed nothing.

### Fixed — data loss and safety

- **Batch rename could destroy files** — Renaming used an operation that overwrites silently on macOS and Linux, so two files resolving to the same episode left only one. Collisions and empty names are now refused.
- **Settings loss on upgrade** — All settings sections shared one error handler, and the section holding every API key was loaded last, so a single unrecognised key wiped the lot. Sections now load independently and unknown keys are ignored.
- **Corrupt settings after an unclean exit** — `settings.json` was written in place; it is now written atomically and stored with owner-only permissions.
- **Exported settings leaked API keys** — Export now redacts them by default.
- **Archive extraction** — FFmpeg archives are validated against path traversal (zip-slip / tar-slip) before any file is written.
- **Profile names** — Were used unsanitised as file paths, so a name containing `../` could read or delete files outside the profiles directory.

### Fixed — wrong results

- **Subtitles for the wrong episode** — Addic7ed results were taken from the season page without filtering by episode, then labelled with the episode you asked for.
- **Spanish, German, Chinese, Dutch, Czech, and Greek subtitles** — Several providers mangled language codes (`ger` became `GE`, not `DE`), so those languages returned no results at all. Language handling is now shared and normalised.
- **Subtitles in the wrong language** — A substring match meant a request for English could match Slovenian or French.
- **Corrupt subtitle files reported as successful** — When an archive failed to unpack or a site returned an error page, the raw bytes were written as `.srt` and reported as a success, which also stopped other providers from being tried. Downloads are now validated as subtitle text.
- **Mojibake in Spanish subtitles** — SubDivX content was re-encoded unconditionally, turning UTF-8 into `AquÃ­ estÃ¡`.
- **Resolutions parsed as season/episode** — `Show.1920x1080.mkv` parsed as season 1920, episode 1080.
- **Release year detection** — `Blade.Runner.2049.2017.mkv` used 2049 as the year.
- **Release-group anime filenames** — `[SubsPlease] Show - [12].mkv` classified as a TV episode but had no matching parse rule, so it never renamed.
- **English title preference** — Matched two-letter Japanese particles anywhere in a title, so “The Night Of”, “Doctor Who”, and “Snowfall” were all treated as Japanese.
- **Bitmap subtitles aborted the encode** — PGS/VobSub tracks were force-converted to a text format, failing the job after it had been running. They are now copied where the container allows it and dropped with a warning where it does not.
- **Video-only files failed to encode** — The audio stream mapping was not optional.
- **Progress stuck at 0%** — Sources without a frame count (some `.ts` captures) produced no progress updates at all; elapsed time is now used as a fallback.
- **Profiles saved but never applied** — Loading a profile reported success without changing any setting.
- **`ffprobe` path corruption** — Deriving the `ffprobe` path rewrote every occurrence of “ffmpeg” in the path, including directory names, breaking all probing for the app’s own FFmpeg installer.
- **Language and subtitle mode settings reset on restart** — Saved in a format that could not be read back.

### Fixed — stability

- **The app hung on exit during an encode** — The window closed but the process stayed alive and busy until the batch finished.
- **Stop did not stop** — Queued files started encoding anyway, rows stayed at “Encoding…”, and cancelled files could be marked “Completed”.
- **Removing a queued row corrupted other rows** — Progress and completion were written to a row index captured when the encode started.
- **Closing the Whisper setup window mid-download froze the app** until the download finished.
- **Log files were destroyed after 5,000 lines** — A rotation bug left one line per file, so logs attached to bug reports contained nothing useful.
- **Batch subtitle failures opened one dialog per file** — 40 failures meant 40 dialogs; there is now a single summary.
- **Right-click menu opened twice** in the encoder queue.
- **GPU detection** re-ran external tools on every call and could freeze the UI for seconds; results are now cached.
- **Whisper on a GPU-less machine** — Now falls back to CPU instead of failing outright, and reports real transcription progress instead of sitting at 10%.
- **Partially downloaded Whisper models** no longer show as installed.

### Changed

- **Dependencies trimmed** — Removed packages that were declared but never imported, including `pandas` and `numpy` (~100 MB). Two were actively harmful: the obsolete `pathlib` backport, which shadows the standard library, and `PyQt-Fluent-Widgets`, which pulled a second Qt binding into the process. Build tooling moved to `requirements-dev.txt`.
- **Packaging** — `pip install .` now ships the entry-point modules; previously all three console scripts failed with `ModuleNotFoundError`.
- **CI** — Now runs the test suite on every branch across Linux, macOS, and Windows. The macOS workflow, which still built a JavaFX/Maven project that no longer exists, was replaced with one that builds the current app.
- **API keys** — The bundled OpenSubtitles and SubDL keys can be overridden via `ENCODEFORGE_OPENSUBTITLES_KEY` and `ENCODEFORGE_SUBDL_KEY`. A user-supplied OpenSubtitles key is now actually used; previously the bundled key always took precedence. Keys are no longer written to debug logs.
- **OMDb and AniDB** are now contacted over HTTPS.
- **Release process** — `prepare_release.sh`, which only printed instructions, is now `RELEASING.md`.

### Known limitations

- Several subtitle scrapers (Podnapisi, SubDivX, Jimaku) target site layouts that have since changed and may return no results. They fail quietly rather than erroring.
- The CLI still exposes only `gui`; encode, subtitle, and rename subcommands remain planned.
- Theme selection, two-pass encoding, and a few other settings are still displayed but not yet wired up.

### Release Links

- **GitHub Release** — [v0.5.0](https://github.com/SirStig/EncodeForge/releases/tag/v0.5.0)
- **Compare** — [v0.5.0-alpha-2...v0.5.0](https://github.com/SirStig/EncodeForge/compare/v0.5.0-alpha-2...v0.5.0)

---

## [0.5.0-alpha-2] — 2026-03-28

Renamer overhaul, smarter provider selection, a cleaner Settings experience, and stability/layout improvements on top of the first PySide6 alpha.

### Added

- **Auto & All Providers mode** — Two new options sit at the top of the provider picker. *Auto* tries providers in priority order and returns the first good match (fast). *All Providers* queries every source in parallel and picks the most complete result — best episode title, air date, and overview wins.
- **API key test buttons** — Each key field in Settings → Accounts now has a **Test** button. Click it and a live ✓ / ✗ status appears next to the field without leaving the dialog.
- **Direct links to API key sign-up pages** — Every provider field shows a small “Get free API key →” link that opens the registration page directly in your browser (TMDB, TVDB, OMDb, Trakt, Fanart.tv, AniDB, OpenSubtitles).

### Improved

- **Provider picker only shows what you have set up** — Providers that require an API key are hidden from the dropdown until you add that key in Settings. Free providers (TVmaze, AniDB, Kitsu, Jikan) are always available.
- **Episode titles from all providers** — OMDB and Trakt previously returned a placeholder like “Episode 3” instead of the real title. Both now fetch the actual episode name from their APIs.
- **Settings dialog is wider** — The window opens at a more comfortable size so input fields aren’t cramped, and form fields now stretch to fill the available space.
- **Smaller, less crowded input fields** — Text and placeholder font in dropdowns and text boxes is slightly smaller, reducing visual noise across the whole app.
- **No more inline API key field on the Renamer tab** — Keys are managed once in Settings → Accounts, not duplicated on each tab.
- **Multi-file rename order fixed** — When renaming several files at once, each file now always gets the metadata that belongs to it. A background-thread ordering bug could previously apply the wrong name to the wrong file.
- **Metadata / rename tab** — Dropped the extra preview area so the before/after columns get the room. After fetch, each suggested name stays on the correct row.
- **Naming patterns** — **Format / Templates** offers ready-made layouts, one-tap building blocks, saved custom templates, and a live sample so the final filenames match what you set.
- **Subtitles tab** — Searching and applying subtitles now keeps you informed: you see status text while providers are checked, and you get clear messages when nothing turns up or when a step fails (instead of only finding out in the log).
- **Download and apply errors** — If a subtitle cannot be downloaded or applied (for example access denied or daily limits), the app shows a dialog, a notification, and updates the main status bar so failures are obvious.
- **OpenSubtitles sign-in** — When OpenSubtitles is in play but you have not added your account in Settings, the app shows a short tip and disables **Apply** / **Batch apply** where an account is needed, so you are guided to add your username and password or choose other providers.
- **Preview** — Picking a search result now shows either a text preview (if the file is already local) or a plain explanation that you still need to use **Apply** to fetch it.

### Fixed

- **TMDB genre crash** — Fetching TV show metadata could silently fail due to an internal type error in the genre field. Fixed.
- **TVDB API calls updated** — The app was using outdated v3-style endpoints. All TVDB lookups now use the correct v4 API paths.
- **Year pattern mis-detecting resolutions as movie years** — A file named `Show.1920x1080.mkv` was classified as a movie because `1920` looked like a year. The detection now only matches valid year ranges (1900–2099) and ignores resolution strings.
- **Encoder: Add Files / Add Folder** — Those buttons could error right after clicking them. They work reliably again.
- **FFmpeg vs FFprobe** — If FFmpeg was installed in a custom folder (for example the one the app downloads for you), video info sometimes still looked for “ffprobe” on the system path and failed. The app now looks for FFprobe next to your FFmpeg executable and remembers both paths when you save setup.
- **FFmpeg setup window** — Opening FFmpeg setup from the main window no longer runs auto-setup in the background and closes the window on its own. You stay in the dialog until you finish or cancel.
- **Starting an encode** — Starting encoding could crash because the conversion engine wasn’t fully initialized yet. That path is initialized before encoding runs.
- **Subtitles tab layout** — The Whisper status line no longer stretches the top section and shoves the file list, results, and preview to the bottom. The main subtitle workspace uses the window height as expected.

### Release Links

- **Compare** — [v0.5.0-alpha-1...v0.5.0-alpha-2](https://github.com/SirStig/EncodeForge/compare/v0.5.0-alpha-1...v0.5.0-alpha-2)

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

> **Note:** Final **JavaFX** release (deprecated). Current binaries are the **PySide6** line; see **[v0.5.0](https://github.com/SirStig/EncodeForge/releases/tag/v0.5.0)**.

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
