import os
from cryptography.fernet import Fernet

from dedup_cleaner import state, logs
from dedup_cleaner.models import FileInfo


def F(name, path, size=10):
    return FileInfo(name=name, path=path, size=size)


def test_plain_roundtrip_and_unchanged_skip(tmp_path):
    rd = logs.Redactor(False, "")
    st = state.State(rd)
    f = F("v.mp4", "/d/v.mp4", 10)
    assert st.process(f, None) is True        # new
    assert st.process(f, None) is False       # same size -> no rework
    p = str(tmp_path / "s.csv")
    st.save(p)
    st2 = state.State.load(p, logs.Redactor(False, ""))
    assert len(st2) == 1
    # plaintext store when encryption off
    assert "/d/v.mp4" in open(p).read()


def test_encrypted_csv_is_opaque(tmp_path):
    key = Fernet.generate_key().decode()
    rd = logs.Redactor(True, key)
    st = state.State(rd)
    st.add_or_update(F("v.mp4", "/d/v.mp4", 10), sha="h")
    p = str(tmp_path / "s.csv")
    st.save(p)
    raw = open(p).read()
    assert "/d/v.mp4" not in raw and "v.mp4" not in raw     # not recoverable by eye
    st2 = state.State.load(p, logs.Redactor(True, key))
    assert st2.verify_decryption() is True


def test_wrong_key_flags_decrypt_failure():
    k1 = Fernet.generate_key().decode()
    k2 = Fernet.generate_key().decode()
    st = state.State(logs.Redactor(True, k1))
    st.add_or_update(F("v.mp4", "/d/v.mp4", 10), "h")
    assert st.verify_decryption() is True
    st2 = state.State(logs.Redactor(True, k2))
    st2.rows = st.rows
    assert st2.verify_decryption() is False
    assert any("decrypt" in w.lower() for w in st2.warnings)


def test_prune_stale_dirs():
    rd = logs.Redactor(False, "")
    st = state.State(rd)
    st.add_or_update(F("a", "/d1/a", 5), "")
    st.add_or_update(F("b", "/d2/b", 5), "")
    known = {state._digest("/d1")}
    removed = st.prune_stale(known)
    assert removed == 1 and len(st) == 1
