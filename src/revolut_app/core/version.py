from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


UNKNOWN_GIT_SHA = 'unknown'


def _read_ref(git_dir: Path, ref_name: str) -> str | None:
    loose_ref = git_dir / ref_name
    if loose_ref.is_file():
        return loose_ref.read_text(encoding='ascii').strip()

    packed_refs = git_dir / 'packed-refs'
    if not packed_refs.is_file():
        return None

    for line in packed_refs.read_text(encoding='ascii').splitlines():
        if not line or line.startswith(('#', '^')):
            continue
        sha, name = line.split(' ', maxsplit=1)
        if name == ref_name:
            return sha
    return None


def _find_git_dir() -> Path | None:
    candidates = (Path.cwd(), *Path(__file__).resolve().parents)
    for directory in candidates:
        git_dir = directory / '.git'
        if git_dir.is_dir():
            return git_dir
    return None


@lru_cache(maxsize=1)
def resolve_git_sha() -> str:
    configured_sha = os.getenv('GIT_SHA', '').strip()
    if configured_sha:
        return configured_sha

    git_dir = _find_git_dir()
    if git_dir is None:
        return UNKNOWN_GIT_SHA

    head = (git_dir / 'HEAD').read_text(encoding='ascii').strip()
    if not head.startswith('ref: '):
        return head or UNKNOWN_GIT_SHA

    return _read_ref(git_dir, head.removeprefix('ref: ')) or UNKNOWN_GIT_SHA
