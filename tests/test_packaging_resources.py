"""Regression: pip wheels/sdists must include resources/ styles and icons."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "resources/__init__.py",
    "resources/icons/app-icon.png",
    "resources/icons/app-icon.ico",
    "resources/icons/check.svg",
    "resources/styles/theme_base.css",
    "resources/styles/splash_screen.css",
}


def _normalize_member(name: str) -> str:
    # Wheel members are bare paths; sdist members are prefixed with encodeforge-*/.
    parts = Path(name).parts
    if parts and parts[0].startswith("encodeforge-"):
        parts = parts[1:]
    return "/".join(parts)


def _cleanup_build_side_effects() -> None:
    for path in (ROOT / "build", ROOT / "encodeforge.egg-info"):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_built_artifact_includes_resources(kind: str, tmp_path: Path):
    out = tmp_path / "dist"
    out.mkdir()
    _cleanup_build_side_effects()
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                f"--{kind}",
                "--outdir",
                str(out),
                "--no-isolation",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"python -m build --{kind} failed\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        artifacts = list(out.glob("*.whl" if kind == "wheel" else "*.tar.gz"))
        assert len(artifacts) == 1, f"expected one {kind} in {out}, got {artifacts}"
        artifact = artifacts[0]

        if kind == "wheel":
            with zipfile.ZipFile(artifact) as zf:
                names = {_normalize_member(n) for n in zf.namelist()}
        else:
            with tarfile.open(artifact, "r:gz") as tf:
                names = {
                    _normalize_member(m.name) for m in tf.getmembers() if m.isfile()
                }

        missing = sorted(EXPECTED - names)
        assert not missing, f"{kind} missing resource files: {missing}"
    finally:
        _cleanup_build_side_effects()


def test_packaging_config_files_exist():
    assert (ROOT / "MANIFEST.in").is_file()
    assert (ROOT / "pyproject.toml").is_file()
    assert (ROOT / "resources" / "__init__.py").is_file()
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "graft resources" in manifest
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.setuptools.package-data]" in pyproject
    assert 'resources = [' in pyproject or "resources = [" in pyproject
