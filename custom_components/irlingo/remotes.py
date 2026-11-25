"""irlingo's remotes: finding and loading them.

The integration released for HACS carries the remotes in its remotes/
directory. Run from a checkout of the repository, it uses conf/remotes.
These functions do file I/O: call them in an executor.
"""

from __future__ import annotations

import json
from pathlib import Path

from .encoder import EncodeError, Remote


def remotes_dir() -> Path:
    """The directory with a subdirectory of remotes per manufacturer."""
    bundled = Path(__file__).parent / "remotes"
    if bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parents[2] / "conf" / "remotes"


def manufacturers() -> list[str]:
    """The manufacturers that have remotes, sorted."""
    return sorted(
        (path.name for path in remotes_dir().iterdir() if path.is_dir()),
        key=str.casefold,
    )


def remotes_of(manufacturer: str) -> list[str]:
    """A manufacturer's remotes, as "manufacturer/remote" names, sorted."""
    directory = remotes_dir() / manufacturer
    if not _is_safe_name(manufacturer) or not directory.is_dir():
        return []
    return sorted(
        (f"{manufacturer}/{path.stem}" for path in directory.glob("*.json")),
        key=str.casefold,
    )


def load_remote(name: str) -> Remote:
    """A remote by its "manufacturer/remote" name."""
    parts = name.split("/")
    if len(parts) != 2 or not all(_is_safe_name(part) for part in parts):
        raise EncodeError(f"Invalid remote name {name}")
    path = remotes_dir() / parts[0] / f"{parts[1]}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise EncodeError(f"Cannot read remote {name}: {err}") from err
    data.pop("tests", None)
    return Remote(data, name)


def _is_safe_name(part: str) -> bool:
    return bool(part) and part not in (".", "..") and "/" not in part and "\\" not in part
