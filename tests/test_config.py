from dedup_cleaner.config import Config, from_env, from_args


def test_deletion_gate():
    assert not Config(root="/x", dry_run=True,  allow_delete=True).deletion_enabled()
    assert not Config(root="/x", dry_run=False, allow_delete=False).deletion_enabled()
    assert Config(root="/x", dry_run=False, allow_delete=True).deletion_enabled()


def test_bad_types_normalized():
    c = Config(root="/x", bad_file_types=[".part", "TMP", "part"])
    assert ".part" in c.bad_file_types
    assert ".tmp" in c.bad_file_types
    assert "part" not in c.bad_file_types


def test_from_env(monkeypatch):
    monkeypatch.setenv("DEDUP_ROOT", "/r")
    monkeypatch.setenv("DEDUP_PREFERRED", "/a /b")
    monkeypatch.setenv("DEDUP_IGNORE", "/x, /y")
    monkeypatch.setenv("DEDUP_DRY_RUN", "true")
    monkeypatch.setenv("DEDUP_MAX_CHANGES", "7")
    c = from_env()
    assert c.root == "/r"
    assert c.preferred == ["/a", "/b"]
    assert c.excluded == ["/x", "/y"]
    assert c.dry_run is True
    assert c.max_changes == 7


def test_from_args_flags():
    c = from_args(["--root", "/r", "--preferred", "/a",
                   "--bad-file-types", ".part", "--max-changes", "3",
                   "--hash-check", "--dry-off", "--allow-delete"])
    assert c.root == "/r"
    assert c.preferred == ["/a"]
    assert ".part" in c.bad_file_types
    assert c.max_changes == 3
    assert c.hash_check is True
    assert c.dry_run is False        # --dry-off
    assert c.allow_delete is True
    assert c.deletion_enabled() is True


def test_dry_run_defaults_true(monkeypatch):
    monkeypatch.setenv("DEDUP_DRY_RUN", "true")
    c = from_args(["--root", "/r"])
    assert c.dry_run is True
    assert c.allow_delete is False


def test_load_env_file_sets_only_missing(monkeypatch, tmp_path):
    import os
    from dedup_cleaner.config import _load_env_file
    monkeypatch.setenv("DEDUP_ROOT", "/already")
    monkeypatch.delenv("DEDUP_MAX_CHANGES", raising=False)
    monkeypatch.delenv("DEDUP_SECRET_KEY", raising=False)
    p = tmp_path / "dedup.env"
    p.write_text('DEDUP_ROOT=/fromfile\nDEDUP_MAX_CHANGES=4\nDEDUP_SECRET_KEY=\'abc\'\n\n# comment\n')
    _load_env_file(str(p))
    assert os.environ["DEDUP_ROOT"] == "/already"          # pre-existing wins (defaultset)
    assert os.environ["DEDUP_MAX_CHANGES"] == "4"          # missing key set
    assert os.environ["DEDUP_SECRET_KEY"] == "abc"         # quotes stripped


def test_load_env_file_missing_path_is_noop(monkeypatch, tmp_path):
    from dedup_cleaner.config import _load_env_file
    monkeypatch.delenv("DEDUP_MAX_CHANGES", raising=False)
    _load_env_file(str(tmp_path / "does-not-exist.env"))
    import os
    assert "DEDUP_MAX_CHANGES" not in os.environ


def _clear_dedup_bool_environ(monkeypatch) -> None:
    for var in ("DEDUP_ENCRYPT_FILE_NAME", "DEDUP_HASH_CHECK",
                "DEDUP_CORRUPTION_CHECK", "DEDUP_ALLOW_DELETE"):
        monkeypatch.delenv(var, raising=False)


def test_bool_flags_off_by_default(monkeypatch):
    """No env, no CLI flag -> every opt-in boolean is False (safe default)."""
    _clear_dedup_bool_environ(monkeypatch)
    c = from_args(["--root", "/r"])
    assert c.encrypt_file_name is False
    assert c.hash_check is False
    assert c.corruption_check is False
    assert c.allow_delete is False
    assert c.deletion_enabled() is False


def test_encrypt_flag_reads_env(monkeypatch):
    """DEDUP_ENCRYPT_FILE_NAME=true in env must enable the redactor via from_args."""
    _clear_dedup_bool_environ(monkeypatch)
    monkeypatch.setenv("DEDUP_ENCRYPT_FILE_NAME", "true")
    c = from_args(["--root", "/r"])
    assert c.encrypt_file_name is True


def test_hash_corruption_and_delete_read_env(monkeypatch):
    _clear_dedup_bool_environ(monkeypatch)
    monkeypatch.setenv("DEDUP_HASH_CHECK", "true")
    monkeypatch.setenv("DEDUP_CORRUPTION_CHECK", "true")
    c = from_args(["--root", "/r"])
    assert c.hash_check is True
    assert c.corruption_check is True
    # allow-delete stays off even when the other opt-ins are on
    assert c.allow_delete is False
    assert c.deletion_enabled() is False


def test_cli_flag_still_overrides_env(monkeypatch):
    """Explicit --encrypt-file-name works even if env is false (flag = opt-in)."""
    _clear_dedup_bool_environ(monkeypatch)
    monkeypatch.setenv("DEDUP_ENCRYPT_FILE_NAME", "false")
    c = from_args(["--root", "/r", "--encrypt-file-name"])
    assert c.encrypt_file_name is True
