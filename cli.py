#!/usr/bin/env python3
"""
EncodeForge CLI

``rename`` and ``gui`` are fully implemented and share EncodeForgeCore with
the desktop app. ``encode``/``subtitle`` are placeholders and exit with a
notice; they may land in a later release.
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


@click.group()
@click.version_option(version=APP_VERSION)
def cli():
    """EncodeForge — desktop app, plus a scriptable `rename` command. `encode`/`subtitle` are not yet implemented."""
    pass


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--codec', '-c', default='h264', help='Video codec (h264, h265, av1)')
@click.option('--preset', '-p', default='medium', help='Encoding preset')
@click.option('--use-nvenc', is_flag=True, help='Use NVIDIA NVENC hardware acceleration')
@click.option('--use-qsv', is_flag=True, help='Use Intel Quick Sync hardware acceleration')
@click.option('--crf', type=int, default=23, help='Quality (CRF) value (0-51, lower is better)')
def encode(input_path, output, codec, preset, use_nvenc, use_qsv, crf):
    """Encode video files with FFmpeg (not available in this release — use the GUI)."""
    click.echo(
        click.style(f"The encode command is not implemented in v{APP_VERSION}.", fg="yellow", bold=True)
    )
    click.echo("Use the desktop application: python main.py   or   python cli.py gui")
    raise SystemExit(2)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--language', '-l', default='en', help='Subtitle language code')
@click.option('--generate', is_flag=True, help='Generate subtitles using Whisper AI')
@click.option('--model', default='base', help='Whisper model (tiny, base, small, medium, large)')
@click.option('--provider', help='Subtitle provider (opensubtitles, addic7ed, etc.)')
def subtitle(input_path, language, generate, model, provider):
    """Download or generate subtitles (not available in this release — use the GUI)."""
    click.echo(
        click.style(f"The subtitle command is not implemented in v{APP_VERSION}.", fg="yellow", bold=True)
    )
    click.echo("Use the desktop application: python main.py   or   python cli.py gui")
    raise SystemExit(2)


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

    src = Path(input_path)
    if src.is_dir():
        it = src.rglob('*') if recursive else src.iterdir()
        files = sorted(str(f) for f in it if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS)
    else:
        files = [str(src)]

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
