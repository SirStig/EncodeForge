#!/usr/bin/env python3
"""
Rename Executor - the single place that touches the filesystem for renames.

RenamingHandler (CLI / backend), MetadataTab (GUI), and any future entry
point all build a list of (source, destination) pairs their own way, then
hand them to execute_renames(). Collision detection, the overwrite guard,
the backup log, and dry-run all live here exactly once, so a fix here
reaches every caller instead of needing to be re-applied per implementation.
"""

import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"rename", "move", "copy", "hardlink", "symlink"}

SIDECAR_EXTENSIONS = {
    ".srt", ".ass", ".ssa", ".sub", ".vtt", ".idx", ".nfo",
}


@dataclass
class RenamePair:
    """One planned filesystem operation."""
    source: Path
    dest: Path
    label: str = ""  # e.g. "sidecar (eng.srt)" — shown in results/backup only


def _key(p: Path) -> Path:
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def plan_renames(pairs: List[RenamePair]):
    """
    Walk `pairs` once and split it into indices safe to execute and a
    results list (same length as `pairs`, index-aligned, with a hole at
    every index still pending execution) for the ones rejected before
    anything touches disk: missing source, already-correct name, or a
    destination that collides with another pair in this same batch.
    Collisions are detected up front so a batch never discovers a conflict
    only after the first half already renamed a file into it.
    """
    n = len(pairs)
    results: List[Optional[Dict]] = [None] * n

    by_target: Dict[Path, List[int]] = {}
    for i, p in enumerate(pairs):
        by_target.setdefault(_key(p.dest), []).append(i)
    colliding = {i for idxs in by_target.values() if len(idxs) > 1 for i in idxs}

    accepted_idx: List[int] = []
    for i, p in enumerate(pairs):
        original = str(p.source)
        new_path = str(p.dest)

        if not p.source.exists():
            results[i] = {
                "original": original, "new_path": new_path, "success": False,
                "message": f"File not found: {p.source}",
            }
            continue

        if i in colliding:
            others = ", ".join(
                pairs[j].source.name for j in by_target[_key(p.dest)] if j != i
            )
            results[i] = {
                "original": original, "new_path": new_path, "success": False,
                "message": f"Target name collides with {others} in this batch — skipped",
            }
            continue

        if _key(p.source) == _key(p.dest):
            results[i] = {
                "original": original, "new_path": new_path, "success": True,
                "message": f"Already correctly named: {p.source.name}",
            }
            continue

        accepted_idx.append(i)

    return accepted_idx, results


def execute_renames(
    pairs: List[RenamePair],
    *,
    action: str = "rename",
    dry_run: bool = False,
    create_backup: bool = False,
) -> Dict:
    """
    Execute a planned batch of renames/moves/copies/links.

    Returns {"status", "renamed", "total", "results", "backup_file"} —
    `results` is index-aligned with `pairs`, entries are
    {"original", "new_path", "success", "message"}.
    """
    if action not in VALID_ACTIONS:
        logger.warning(f"Unknown rename action '{action}', defaulting to 'rename'")
        action = "rename"

    accepted_idx, results = plan_renames(pairs)
    backup_entries: List[Dict] = []

    for i in accepted_idx:
        p = pairs[i]
        original = str(p.source)
        new_path = str(p.dest)

        if p.dest.exists():
            # Not one of this batch's own collisions (plan_renames already
            # caught those) — a file already sitting at the target outside
            # this run. Refuse rather than clobber it.
            results[i] = {
                "original": original, "new_path": new_path, "success": False,
                "message": f"Refusing to overwrite existing file: {p.dest.name}",
            }
            continue

        if dry_run:
            verb = {"rename": "rename", "move": "move", "copy": "copy",
                     "hardlink": "hardlink", "symlink": "symlink"}[action]
            results[i] = {
                "original": original, "new_path": new_path, "success": True,
                "message": f"Would {verb} to: {p.dest}",
            }
            continue

        try:
            p.dest.parent.mkdir(parents=True, exist_ok=True)

            if action == "copy":
                shutil.copy2(p.source, p.dest)
            elif action == "hardlink":
                os.link(p.source, p.dest)
            elif action == "symlink":
                p.dest.symlink_to(p.source)
            else:
                # "rename"/"move" both use shutil.move: a plain Path.rename
                # raises across filesystems (e.g. destination on another
                # drive), which a configured library root makes routine.
                shutil.move(str(p.source), str(p.dest))

            if create_backup and action in ("rename", "move"):
                backup_entries.append({
                    "original_path": original,
                    "original_name": p.source.name,
                    "new_path": new_path,
                    "new_name": p.dest.name,
                    "timestamp": datetime.now().isoformat(),
                })

            verb_past = {"rename": "Renamed", "move": "Moved", "copy": "Copied",
                         "hardlink": "Hardlinked", "symlink": "Symlinked"}[action]
            results[i] = {
                "original": original, "new_path": new_path, "success": True,
                "message": f"{verb_past} to: {p.dest.name}",
            }
        except Exception as e:
            logger.error(f"{action} failed for {p.source}: {e}")
            results[i] = {
                "original": original, "new_path": new_path, "success": False,
                "message": f"{action.capitalize()} failed: {e}",
            }

    backup_file: Optional[Path] = None
    if create_backup and not dry_run and backup_entries:
        backup_file = _write_backup(backup_entries)

    success_count = sum(1 for r in results if r and r["success"])
    return {
        "status": "success",
        "renamed": success_count,
        "total": len(pairs),
        "results": results,
        "backup_file": str(backup_file) if backup_file else None,
    }


def _write_backup(entries: List[Dict]) -> Optional[Path]:
    from core import path_manager
    try:
        backup_dir = path_manager.get_backups_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_file = backup_dir / f"rename_backup_{ts}.json"
        payload = {
            "timestamp": datetime.now().isoformat(),
            "total_files": len(entries),
            "successful_renames": len(entries),
            "files": entries,
        }
        backup_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Backup created: {backup_file}")
        return backup_file
    except Exception as e:
        logger.error(f"Failed to create backup file: {e}")
        return None


def list_backups() -> List[Path]:
    """Backup files newest first."""
    from core import path_manager
    try:
        backup_dir = path_manager.get_backups_dir()
        return sorted(
            backup_dir.glob("rename_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        return []


def restore_from_backup(backup_file: Path) -> Dict:
    """Reverse a batch recorded by _write_backup, newest entry first."""
    try:
        data = json.loads(Path(backup_file).read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "status": "error", "message": f"Could not read backup file: {e}",
            "renamed": 0, "total": 0, "results": [],
        }

    files = list(data.get("files", []))
    pairs = [
        RenamePair(source=Path(f["new_path"]), dest=Path(f["original_path"]))
        for f in reversed(files)
        if f.get("new_path") and f.get("original_path")
    ]
    result = execute_renames(pairs, action="rename", dry_run=False, create_backup=False)
    result["status"] = "success"
    return result


def find_sidecar_files(video_path: Path) -> List[Path]:
    """
    Sibling files sharing `video_path`'s stem — subtitles and an .nfo the
    video rename should carry along. Matches on exact stem, not substring,
    so "Show.S01E01.mkv" doesn't also sweep up "Show.S01E010.srt".
    """
    try:
        folder = video_path.parent
        stem = video_path.stem
        out = []
        for f in folder.iterdir():
            if f == video_path or not f.is_file():
                continue
            if f.suffix.lower() in SIDECAR_EXTENSIONS and f.stem == stem:
                out.append(f)
        return sorted(out)
    except Exception as e:
        logger.warning(f"Could not scan for sidecar files of {video_path}: {e}")
        return []
