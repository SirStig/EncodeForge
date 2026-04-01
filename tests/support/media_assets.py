"""
Test media: optional download (network) or local FFmpeg synthesis.

Cache directory: $ENCODEFORGE_TEST_MEDIA_CACHE or ~/.cache/encodeforge_tests
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

SAMPLE_MP4_URL = "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"
SAMPLE_MP4_CACHE_NAME = "sample_640x360.mp4"
SAMPLE_MIN_BYTES = 50_000


def get_media_cache_dir() -> Path:
    env = os.environ.get("ENCODEFORGE_TEST_MEDIA_CACHE", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "encodeforge_tests"


def ensure_downloaded_sample_mp4() -> Path:
    cache = get_media_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / SAMPLE_MP4_CACHE_NAME
    if dest.exists() and dest.stat().st_size >= SAMPLE_MIN_BYTES:
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(
        SAMPLE_MP4_URL,
        headers={"User-Agent": "EncodeForge-Tests/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp, open(part, "wb") as out:
            shutil.copyfileobj(resp, out)
    except Exception:
        if part.exists():
            part.unlink(missing_ok=True)
        raise
    part.replace(dest)
    return dest


def synthesize_test_mp4(
    output_path: Path,
    duration: float = 4.0,
    size: str = "640x360",
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration}:size={size}:rate=24",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        timeout=120,
        text=True,
    )
    return output_path


def trim_video(
    input_path: Path,
    output_path: Path,
    duration_sec: float,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-t",
        str(duration_sec),
        "-c",
        "copy",
        str(output_path),
    ]
    subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        timeout=120,
        text=True,
    )
    return output_path
