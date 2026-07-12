from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def read_script(name):
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_code_package_builder_excludes_database_and_media():
    """FR-OPS-01: routine release packages contain source code only."""
    script = read_script("build-migration-package.ps1")

    assert 'packageName = "ddmp-code-$timestamp"' in script
    assert 'package_type = "code_only"' in script
    assert "includes_database = $false" in script
    assert "includes_media = $false" in script
    assert "dumpdata" not in script
    assert "sourceMediaDir" not in script
    assert '"pytest-of-*"' in script
    assert '".tmp"' in script


def test_server_apply_script_has_no_destructive_data_import_commands():
    """FR-OPS-02: code deployment preserves production records and media."""
    script = read_script("apply-migration-package.ps1")

    assert 'package_type -ne "code_only"' in script
    assert 'Join-Path $packageRoot "data"' in script
    assert 'Join-Path $packageRoot "media"' in script
    assert '"flush"' not in script
    assert '"loaddata"' not in script
    assert '"dumpdata"' not in script
    assert "$ReplaceDatabase" not in script
    assert "Mirroring development media" not in script
    assert "& curl.exe --fail-with-body" not in script
    assert "& curl.exe -f -i" in script


def test_latest_package_batches_only_select_code_packages():
    """FR-OPS-02: old full-data migration zips cannot be selected accidentally."""
    build_batch = read_script("build-latest-migration-package.bat")
    apply_batch = read_script("apply-latest-migration-package.bat")

    assert "ddmp-code-*.zip" in build_batch
    assert "ddmp-code-*.zip" in apply_batch
    assert "ddmp-migration-*.zip" not in apply_batch
    assert "preserve production data/media" in apply_batch
