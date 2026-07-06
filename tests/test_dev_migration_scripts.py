from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fresh_machine_bootstrap_preserves_environment_isolation():
    """SYS-CONFIG-001: a new checkout creates local config without importing data."""
    script = (REPO_ROOT / "scripts" / "bootstrap-dev-machine.ps1").read_text(encoding="utf-8")

    assert 'Join-Path $root ".venv\\Scripts\\python.exe"' in script
    assert 'Join-Path $root ".env"' in script
    assert "RandomNumberGenerator" in script
    assert '"manage.py", "migrate", "--noinput"' in script
    assert '"manage.py", "check"' in script
    assert "Copy-Item" in script
    assert ".local\\db.sqlite3" not in script
    assert ".local\\media" not in script


def test_local_secrets_data_and_archives_are_ignored():
    """SYS-CONFIG-001: machine-local config and data cannot enter the code baseline."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (".env", ".venv/", ".local/", "*.sqlite3", "*.rar", "*.zip", "*.7z"):
        assert pattern in gitignore
