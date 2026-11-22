#!/usr/bin/env python3
"""
EncodeForge CLI

``encode``, ``subtitle``, ``rename``, and ``gui`` share EncodeForgeCore with
the desktop app.
"""

import sys
import click
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app import __version__ as APP_VERSION

VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
    '.webm', '.m4v', '.mpg', '.mpeg', '.3gp',
}

CODEC_FALLBACK = {
    'h264': 'libx264',
    'h265': 'libx265',
    'hevc': 'libx265',
    'av1': 'libaom-av1',
}

# Setup logging
try:
    from utils.logging_config import setup_logging
    setup_logging()
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


def _collect_video_files(input_path: str, recursive: bool = True):
    """Return sorted video paths from a file or directory."""
    src = Path(input_path)
    if src.is_dir():
        it = src.rglob('*') if recursive else src.iterdir()
        return sorted(str(f) for f in it if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS)
    return [str(src)]


def _resolve_encode_output(input_file: Path, output: str | None, output_format: str) -> str | None:
    """Map CLI --output to a concrete file path, or None for handler auto-naming."""
    if not output:
        return None
    out = Path(output)
    # Existing directory, or a path without a media suffix → treat as output folder.
    if out.is_dir() or (not out.suffix or out.suffix.lower() not in VIDEO_EXTENSIONS):
        out.mkdir(parents=True, exist_ok=True)
        return str(out / f"{input_file.stem}.{output_format}")
    out.parent.mkdir(parents=True, exist_ok=True)
    return str(out)


@click.group()
@click.version_option(version=APP_VERSION)
def cli():
    """EncodeForge — desktop app plus scriptable `encode`/`subtitle`/`rename`."""
    pass


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file or directory')
@click.option('--codec', '-c', type=click.Choice(['h264', 'h265', 'hevc', 'av1'], case_sensitive=False),
              default='h264', show_default=True, help='Video codec family')
@click.option('--preset', '-p', default='medium', show_default=True, help='Encoding preset')
@click.option('--use-nvenc', is_flag=True, help='Prefer NVIDIA NVENC hardware acceleration')
@click.option('--use-qsv', is_flag=True, help='Prefer Intel Quick Sync hardware acceleration')
@click.option('--use-amf', is_flag=True, help='Prefer AMD AMF hardware acceleration')
@click.option('--crf', type=int, default=23, show_default=True,
              help='Quality (CRF / CQ) value (0-51, lower is better)')
@click.option('--format', 'output_format', type=click.Choice(['mp4', 'mkv', 'webm', 'avi', 'mov'], case_sensitive=False),
              default='mp4', show_default=True, help='Output container format')
@click.option('--overwrite/--no-overwrite', default=False, show_default=True,
              help='Overwrite an existing output file')
@click.option('--recursive/--no-recursive', default=True,
              help='When INPUT_PATH is a folder, scan it recursively (default: on).')
@click.option('--dry-run', '--preview', 'dry_run', is_flag=True,
              help='Show what would be encoded without running FFmpeg.')
@click.option('-y', '--yes', is_flag=True, help='Skip the confirmation prompt.')
def encode(input_path, output, codec, preset, use_nvenc, use_qsv, use_amf, crf,
           output_format, overwrite, recursive, dry_run, yes):
    """
    Encode video files with FFmpeg via EncodeForgeCore / ConversionHandler.

    INPUT_PATH is a single video file, or a folder to scan for video files.
    Without --use-nvenc/--use-qsv/--use-amf, encoding uses software (libx264/…).
    """
    files = _collect_video_files(input_path, recursive=recursive)
    if not files:
        click.echo(click.style("No video files found.", fg="yellow"))
        raise SystemExit(1)

    if output and len(files) > 1:
        out = Path(output)
        if out.suffix.lower() in VIDEO_EXTENSIONS and not out.is_dir():
            click.echo(click.style(
                "--output must be a directory when encoding more than one file.",
                fg="red", bold=True,
            ))
            raise SystemExit(1)

    from utils.settings_manager import get_settings_manager
    from core.encodeforge_core import EncodeForgeCore

    sm = get_settings_manager()
    settings = sm.get_merged_conversion_settings()
    settings.video_codec_fallback = CODEC_FALLBACK[codec.lower()]
    settings.video_preset = preset
    settings.video_crf = crf
    settings.nvenc_cq = crf
    settings.amf_qp = crf
    settings.qsv_quality = crf
    settings.output_format = output_format.lower()
    settings.overwrite_existing = overwrite
    settings.dry_run = dry_run

    # CLI HW flags are opt-in; default is software so headless/CI machines work.
    settings.use_nvenc = bool(use_nvenc)
    settings.use_qsv = bool(use_qsv)
    settings.use_amf = bool(use_amf)
    settings.use_videotoolbox = False
    if use_nvenc and codec.lower() in ('h265', 'hevc'):
        settings.nvenc_codec = 'hevc_nvenc'
    elif use_nvenc:
        settings.nvenc_codec = 'h264_nvenc'

    core = EncodeForgeCore(settings=settings)

    click.echo(f"Encoding {len(files)} file(s)…")
    if not dry_run and not yes:
        if not click.confirm(f"Encode {len(files)} file(s) with {settings.video_codec_fallback}?", default=False):
            click.echo("Cancelled.")
            raise SystemExit(1)

    def _progress(info):
        name = info.get('file', '')
        status = info.get('status', '')
        progress = info.get('progress')
        if progress is not None and status in ('encoding', 'converting', 'progress'):
            click.echo(f"\r  {name}: {progress}%", nl=False)
        elif status in ('completed', 'dry_run', 'error'):
            click.echo("")

    failures = 0
    converted = 0
    for path in files:
        src = Path(path)
        out_path = _resolve_encode_output(src, output, settings.output_format)
        result = core.convert_file(path, output_path=out_path, progress_callback=_progress)
        name = src.name
        if result.get("status") == "success":
            converted += 1
            dest = result.get("output_path") or out_path or "(auto)"
            encoder = result.get("encoder", settings.video_codec_fallback)
            prefix = "would" if result.get("dry_run") else "ok"
            color = "cyan" if result.get("dry_run") else "green"
            click.echo(click.style(f"  {prefix:5} ", fg=color) + f"{name}  →  {dest}  [{encoder}]")
        else:
            failures += 1
            click.echo(click.style(" fail  ", fg="red") + f"{name}  —  {result.get('message', 'unknown error')}")

    verb = "would encode" if dry_run else "encoded"
    click.echo(f"\n{converted}/{len(files)} {verb}" + (f", {failures} failed" if failures else ""))
    raise SystemExit(1 if failures else 0)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--language', '-l', default=None,
              help='Subtitle language code or name (default: saved settings, usually English).')
@click.option('--generate', is_flag=True,
              help='Generate subtitles with Whisper AI instead of downloading.')
@click.option('--model', default=None,
              help='Whisper model (tiny, base, small, medium, large-v2, …). '
                   'Default: saved settings (Subtitles tab / Settings).')
@click.option('--provider', default=None,
              help='Restrict download to one provider (opensubtitles, addic7ed, subdl, …). '
                   'Default: providers saved in settings.')
@click.option('--recursive/--no-recursive', default=True,
              help='When INPUT_PATH is a folder, scan it recursively (default: on).')
def subtitle(input_path, language, generate, model, provider, recursive):
    """
    Download or generate subtitles for video files.

    Uses the same settings merge as the Subtitles tab: saved language / Whisper
    model / providers, with CLI flags as overrides. INPUT_PATH is a video file
    or a folder of videos.
    """
    from utils.settings_manager import (
        build_subtitle_settings_dict,
        subtitle_core_from_settings,
    )

    files = _collect_video_files(input_path, recursive=recursive)
    if not files:
        click.echo(click.style("No video files found.", fg="yellow"))
        raise SystemExit(1)

    providers = [provider] if provider else None
    subs = build_subtitle_settings_dict(
        language=language,
        whisper_model=model,
        providers=providers,
    )
    core = subtitle_core_from_settings(subs)
    languages = subs.get("languages") or ["eng"]
    lang = languages[0]

    mode_label = "Whisper generate" if generate else "download"
    click.echo(f"Processing {len(files)} file(s) ({mode_label}, language={lang})…")

    failures = 0
    for path in files:
        name = Path(path).name
        if generate:
            result = core.generate_subtitles(path, language=lang)
            if result.get("status") == "success":
                info = result.get("subtitle") or {}
                out = info.get("path") or info.get("subtitle_path") or result.get("subtitle_path") or ""
                detail = f"  →  {out}" if out else ""
                click.echo(click.style("  ok  ", fg="green") + f"{name}{detail}")
                if result.get("message"):
                    click.echo(f"       {result['message'].splitlines()[0]}")
            else:
                failures += 1
                click.echo(
                    click.style(" fail ", fg="red")
                    + f"{name}  —  {result.get('message', 'unknown error')}"
                )
            continue

        result = core.download_subtitles(path, languages=languages)
        if result.get("status") == "success":
            downloaded = result.get("subtitles_downloaded") or []
            paths = []
            for item in downloaded:
                p = item.get("subtitle_path") or item.get("path")
                if p:
                    paths.append(p)
            detail = f"  →  {paths[0]}" if paths else ""
            click.echo(click.style("  ok  ", fg="green") + f"{name}{detail}")
            if result.get("message"):
                click.echo(f"       {result['message']}")
        else:
            failures += 1
            click.echo(
                click.style(" fail ", fg="red")
                + f"{name}  —  {result.get('message', 'unknown error')}"
            )

    total = len(files)
    ok = total - failures
    click.echo(f"\n{ok}/{total} succeeded" + (f", {failures} failed" if failures else ""))
    raise SystemExit(1 if failures else 0)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--tmdb-key', help='TMDB API key (overrides saved settings)')
@click.option('--tvdb-key', help='TVDB API key (overrides saved settings)')
@click.option('--omdb-key', help='OMDb API key (overrides saved settings)')
@click.option('--trakt-key', help='Trakt API key (overrides saved settings)')
@click.option('--provider', default='automatic',
              help='Metadata provider to use, or "automatic" to try all in priority order (default).')
@click.option('--pattern', help='Naming pattern, applied to both TV and movies (overrides saved settings).')
@click.option('-d', '--destination', 'destination', type=click.Path(file_okay=False),
              help='Move/copy into this root folder instead of renaming in place. '
                   'Enables "/" in the pattern to describe subfolders (e.g. "{title}/Season {season:02d}/...").')
@click.option('--action', type=click.Choice(['rename', 'move', 'copy', 'hardlink', 'symlink']), default=None,
              help='What to do with each file (default: rename in place, or move if --destination is set).')
@click.option('--sidecars/--no-sidecars', default=True,
              help='Carry along same-name .srt/.ass/.nfo files sitting next to each video (default: on).')
@click.option('--recursive/--no-recursive', default=True,
              help='When INPUT_PATH is a folder, scan it recursively (default: on).')
@click.option('--dry-run', '--preview', 'dry_run', is_flag=True,
              help="Show what would happen without touching the filesystem.")
@click.option('-y', '--yes', is_flag=True, help='Skip the confirmation prompt.')
@click.option('--type', 'media_type', type=click.Choice(['movie', 'tv', 'anime', 'auto']), default='auto',
              help='Media type hint (currently informational — detection is automatic per file).')
def rename(input_path, tmdb_key, tvdb_key, omdb_key, trakt_key, provider, pattern,
           destination, action, sidecars, recursive, dry_run, yes, media_type):
    """
    Rename media files using metadata (TMDB, TVDB, TVmaze, AniDB, Kitsu, Jikan, and more).

    INPUT_PATH is a single video file, or a folder to scan for video files.
    """
    from utils.settings_manager import get_settings_manager

    files = _collect_video_files(input_path, recursive=recursive)
    if not files:
        click.echo(click.style("No video files found.", fg="yellow"))
        raise SystemExit(1)

    sm = get_settings_manager()
    settings = sm.get_merged_conversion_settings()
    if pattern:
        settings.renaming_pattern_tv = pattern
        settings.renaming_pattern_movie = pattern
    if destination:
        settings.renaming_destination_root = destination
    settings.renaming_action = action or ('move' if destination else settings.renaming_action or 'rename')
    settings.renaming_include_sidecars = sidecars

    preview_settings = {"selected_provider": provider}
    key_overrides = {
        "tmdb_api_key": tmdb_key, "tvdb_api_key": tvdb_key,
        "omdb_api_key": omdb_key, "trakt_api_key": trakt_key,
    }
    for field, value in key_overrides.items():
        if value:
            setattr(settings, field, value)
            preview_settings[field] = value

    from core.encodeforge_core import EncodeForgeCore
    core = EncodeForgeCore(settings=settings)

    click.echo(f"Scanning {len(files)} file(s)…")
    if not dry_run and not yes:
        verb = settings.renaming_action
        if not click.confirm(f"{verb.capitalize()} {len(files)} file(s) using pattern from settings?", default=False):
            click.echo("Cancelled.")
            raise SystemExit(1)

    result = core.rename_files(
        files, dry_run=dry_run, create_backup=not dry_run, preview_settings=preview_settings
    )
    if result.get("status") != "success":
        click.echo(click.style(f"Rename failed: {result.get('message', 'unknown error')}", fg="red", bold=True))
        raise SystemExit(1)

    failures = 0
    for r in result.get("results", []):
        name = Path(r["original"]).name
        if r["success"]:
            click.echo(click.style("  ok  ", fg="green") + f"{name}  →  {r['message']}")
        else:
            failures += 1
            click.echo(click.style(" fail ", fg="red") + f"{name}  —  {r['message']}")

    for r in result.get("sidecar_results", []) or []:
        name = Path(r["original"]).name
        if r["success"]:
            click.echo(click.style("  ok  ", fg="green") + f"{name}  →  {r['message']}  (companion file)")
        else:
            click.echo(click.style(" skip ", fg="yellow") + f"{name}  —  {r['message']}  (companion file)")

    if result.get("backup_file"):
        click.echo(f"\nBackup written: {result['backup_file']}")

    total = result.get("total", len(files))
    click.echo(f"\n{result.get('renamed', 0)}/{total} renamed" + (f", {failures} failed" if failures else ""))
    raise SystemExit(1 if failures else 0)


@cli.command()
def gui():
    """Launch the PySide6 GUI application"""
    logger.info("Launching GUI")
    click.echo("Starting EncodeForge GUI...")
    
    # Import and run GUI
    from main import main
    main()


if __name__ == '__main__':
    cli()
