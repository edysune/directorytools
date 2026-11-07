import pytest
from cryptography.fernet import Fernet

from dedup_cleaner import logs


def test_enabled_without_key_fails_fast():
    with pytest.raises(logs.ConfigKeyError):
        logs.Redactor(True, "")
    with pytest.raises(logs.ConfigKeyError):
        logs.Redactor(True, "not-a-fernet-key")


def test_token_roundtrip_and_display():
    key = Fernet.generate_key().decode()
    rd = logs.Redactor(True, key)
    tok = rd.token("/secret/clip.mkv")
    assert "/secret/clip.mkv" not in tok
    assert rd.try_decrypt(tok) == "/secret/clip.mkv"
    disp = rd.display("/secret/clip.mkv")
    assert disp != "/secret/clip.mkv" and disp.endswith("\u2026")


def test_disabled_passthrough():
    rd = logs.Redactor(False, "")
    assert rd.enabled is False
    assert rd.token("x") == "x" and rd.display("x") == "x"
    assert rd.try_decrypt("y") == "y"
