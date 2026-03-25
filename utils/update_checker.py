"""
GitHub Releases update check for EncodeForge.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_REPO = "SirStig/EncodeForge"
GITHUB_API_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
USER_AGENT = "EncodeForge-UpdateCheck/1.0"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    name: str
    body: str
    html_url: str
    published_at: str


@dataclass
class UpdateCheckOutcome:
    release: Optional[ReleaseInfo] = None
    error: Optional[str] = None
    is_newer: bool = False


def _repo_slug() -> str:
    return os.environ.get("ENCODEFORGE_UPDATE_REPO", DEFAULT_REPO).strip().strip("/")


def normalize_version(tag: str) -> str:
    tag = (tag or "").strip()
    if tag.lower().startswith("v"):
        tag = tag[1:]
    tag = tag.split("-")[0].strip()
    return tag


def _parse_version_tuple(v: str) -> tuple:
    parts = re.findall(r"\d+", v)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def is_newer(remote_version: str, current_version: str) -> bool:
    try:
        from packaging.version import Version

        return Version(normalize_version(remote_version)) > Version(
            normalize_version(current_version)
        )
    except Exception:
        return _parse_version_tuple(remote_version) > _parse_version_tuple(current_version)


def fetch_latest_release(timeout: float = 15.0) -> Optional[ReleaseInfo]:
    repo = _repo_slug()
    url = GITHUB_API_LATEST.format(repo=repo)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 404:
            logger.warning("No GitHub releases found for %s", repo)
            return None
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("Update check failed: %s", e)
        raise

    tag = data.get("tag_name") or ""
    ver = normalize_version(tag)
    if not ver:
        logger.warning("Release missing tag_name")
        return None

    return ReleaseInfo(
        version=ver,
        tag_name=tag,
        name=(data.get("name") or "").strip() or tag,
        body=(data.get("body") or "").strip(),
        html_url=(data.get("html_url") or "").strip(),
        published_at=(data.get("published_at") or "").strip(),
    )
