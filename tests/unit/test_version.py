from pathlib import Path

from revolut_app.core import version


def test_resolve_git_sha_from_loose_ref(monkeypatch, tmp_path: Path):
    git_dir = tmp_path / '.git'
    ref = git_dir / 'refs' / 'heads' / 'main'
    ref.parent.mkdir(parents=True)
    (git_dir / 'HEAD').write_text('ref: refs/heads/main\n', encoding='ascii')
    ref.write_text('a' * 40 + '\n', encoding='ascii')

    monkeypatch.delenv('GIT_SHA', raising=False)
    monkeypatch.setattr(version, '_find_git_dir', lambda: git_dir)
    version.resolve_git_sha.cache_clear()

    assert version.resolve_git_sha() == 'a' * 40


def test_configured_git_sha_takes_precedence(monkeypatch):
    monkeypatch.setenv('GIT_SHA', 'build-revision')
    version.resolve_git_sha.cache_clear()

    assert version.resolve_git_sha() == 'build-revision'
