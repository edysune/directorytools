"""Unit tests for the shared language policy (languagePolicy.py).

Policy under test (user, 2026-10-28):
  - keep       : confirmed whitelist match                          -> kept
  - confirmed  : known specific non-whitelisted language            -> removable
  - ambiguous  : untagged/und, format tokens, fan-sub names,        -> NEVER auto-removed;
                 channel labels, suspected-English (English [CC])     EXCLUDE list
Covers RISK-1 (40 approved vs 2 ASS/SRT holds), RISK-2 (title/label leak),
BUG-5 ('und' must stay out of the removal set), and foreign-dir exclusion.
"""
import pytest

from tools.video_audio_scripts import languagePolicy as lp
from tools.video_audio_scripts import fixVideoMetadata as fvm


# ---------------- normalize_lang_code ----------------

@pytest.mark.parametrize("raw,expected", [
    ("en", "en"), ("ENG", "en"), ("English", "en"), ("eng", "en"),
    ("jpn", "ja"), ("ja", "ja"), ("Japanese", "ja"),
    ("fre", "fr"), ("fra", "fr"), ("French", "fr"),
    ("ice", "is"), ("isl", "is"), ("Icelandic", "is"),
    ("cze", "cs"), ("gre", "el"), ("hrv", "hr"), ("nob", "nb"),
    ("enm", "enm"), ("engb", None),            # enm=Middle English kept distinct; unknown var. -> None
    ("und", None), ("unkn", None),             # 'und'/'unknown' = ambiguous, not a code
    ("  ja ", "ja"),                            #
    (8, None), ("stereo", None), ("necomimi", None), ("english [cc]", None),
])
def test_normalize_lang_code(raw, expected):
    assert lp.normalize_lang_code(raw) == expected


# ---------------- is_ambiguous_lang ----------------

@pytest.mark.parametrize("raw", [
    "", None, "unknown", "UND", "und",
    "SRT", "ASS", "VTT",                     # subtitle format tokens (RISK-1 holds)
    "Stereo", "Surround", "MRSK", "morsk2",  # channel-mix labels (RISK-2 audio)
    "Nekomimi - No Honorifics", "Chihiro - German",  # fan-sub names (RISK-2)
    "English [CC]",                           # suspected-English (People of Earth)
])
def test_is_ambiguous_lang_true(raw):
    assert lp.is_ambiguous_lang(raw) is True


@pytest.mark.parametrize("raw", ["en", "ja", "fre", "ara", "jpn", "dan", "enm", "nob"])
def test_is_ambiguous_lang_false(raw):
    """Every confirmed language from the Phase-1 library must NOT be ambiguous."""
    assert lp.is_ambiguous_lang(raw) is False


# ---------------- matches_whitelist ----------------

def test_matches_whitelist_confirmed_codes():
    assert lp.matches_whitelist("jpn", "Japanese") is True
    assert lp.matches_whitelist("eng", "english") is True
    assert lp.matches_whitelist("eng", "English, Japanese, Korean") is True
    assert lp.matches_whitelist("fre", "French") is True


def test_matches_whitelist_nonmatch():
    assert lp.matches_whitelist("jpn", "English") is False
    assert lp.matches_whitelist("fre", "English, Japanese, Korean") is False


def test_matches_whitelist_never_ambiguous():
    """Ambiguous values NEVER match — they must be decided via lang_state (RISK-2/BUG-5)."""
    for raw in ["und", "", "unknown", "SRT", "Stereo", "English [CC]", "Nekomimi - x"]:
        assert lp.matches_whitelist(raw, "English") is False


def test_matches_whitelist_no_match_on_empty_whitelist():
    assert lp.matches_whitelist("en", "") is False
    assert lp.matches_whitelist("en", None) is False


# ---------------- lang_state (the tri-state classifier) ----------------

def test_lang_state_keep():
    assert lp.lang_state("en", "English") == "keep"
    assert lp.lang_state("English", "English") == "keep"


def test_lang_state_confirmed():
    """Confirmed non-whitelisted languages are the only removable class (RISK-1)."""
    for raw in ["fre", "ara", "jpn", "chi", "dan", "fin", "nor", "swe", "rus", "ukr", "ger"]:
        assert lp.lang_state(raw, "English") == "confirmed"


def test_lang_state_ambiguous_never_removed():
    for raw in ["und", "", "unknown", "SRT", "ASS", "Stereo", "MRSK", "English [CC]", "Nekomimi - No Honorifics"]:
        assert lp.lang_state(raw, "English") == "ambiguous"


def test_lang_state_unrecognized_is_ambiguous_not_confirmed():
    """Conservatism (user rule: when in doubt, keep): unknown tokens must NEVER
    become 'confirmed' — that would make them removable (BUG-5 class of failure)."""
    assert lp.lang_state("cpe", "English") == "ambiguous"
    assert lp.lang_state("xyzzy", "English") == "ambiguous"


def test_lang_state_multi_entry_whitelist():
    w = "English, Japanese, Korean"
    assert lp.lang_state("eng", w) == "keep"
    assert lp.lang_state("jpn", w) == "keep"
    assert lp.lang_state("kor", w) == "keep"
    assert lp.lang_state("fre", w) == "confirmed"
    assert lp.lang_state("und", w) == "ambiguous"


# ---------------- back-compat shim in fixVideoMetadata ----------------

def test_fixer_language_matches_whitelist_delegates():
    """fixVideoMetadata keeps the old name for analyze/gui importers, but it
    must now be the STRICT policy matcher (no fuzzy prefix matching)."""
    assert fvm.language_matches_whitelist("eng", "english") is True
    assert fvm.language_matches_whitelist("jpn", "Japanese") is True
    assert fvm.language_matches_whitelist("jpn", "English") is False
    assert fvm.language_matches_whitelist("und", "English") is False
    assert fvm.language_matches_whitelist("English [CC]", "English") is False
    # the old fuzzy matcher matched any 2-letter prefix; strict must not:
    assert fvm.language_matches_whitelist("st", "sterling") is False


# ---------------- foreign-dir exclusion ----------------

@pytest.mark.parametrize("p", [
    "/mnt/A18000/plex/foreign_tv_shows/Show/1.mkv",
    "/mnt/A16000/plex/foreign_movies/Movie (2020) 1080p.mkv",
    "E:\\Media\\FOREIGN_MOVIES\\x.mkv",          # case-insensitive win-style
    "/data/foreign_tv_shows",                    # the category dir itself
])
def test_is_path_excluded(p):
    assert lp.is_path_excluded(p) is True


@pytest.mark.parametrize("p", [
    "/mnt/A18000/plex/anim_d/Bleach/1.mkv",
    "/media/tv_shows_d/Gen V/1.mkv",
    "/data/4k_anime/Series/1.mkv",               # 4k_anime is NOT a foreign category
    "/mnt/A18000/plex/my_foreign_backup_notes.mkv",  # substring must NOT trigger
])
def test_is_path_excluded_false(p):
    assert lp.is_path_excluded(p) is False


# =====================================================================
# fixVideoMetadata: track-level decision (no external tools; monkeypatched)
# =====================================================================

def _item(subs=None, audio=None):
    item = {"path": "/media/anime_d/Test/ep.mkv", "format": "matroska"}
    if subs is not None:
        item["subtitle_streams"] = [{"language": s} for s in subs]
    if audio is not None:
        item["audio_streams"] = [{"language": a} for a in audio]
    return item


@pytest.fixture
def no_external(monkeypatch):
    """No ffmpeg / no backup in tests — capture ffmpeg cmds to verify decisions."""
    cmds = []
    monkeypatch.setattr(fvm, "backup_file_before_fix", lambda *a, **k: None)
    monkeypatch.setattr("shutil.move", lambda *a, **k: None)
    def fake_run(cmd, check=True, **k):
        cmds.append(cmd)
        class Res:
            pass
        return Res()
    monkeypatch.setattr("subprocess.run", fake_run)
    return cmds


def _sub_maps(cmds):
    """The '-0:s:N' exclusions encoded in the last ffmpeg command."""
    c = cmds[-1]
    out, skip = [], False
    for i, x in enumerate(c):
        if skip:
            skip = False
            continue
        if x == "-map" and i + 1 < len(c) and c[i + 1].startswith("-0:s:"):
            out.append(int(c[i + 1].split(":")[-1]))
            skip = True
    return out


def test_sub_remove_confirmed_only(no_external):
    # [en, fre] -> remove fre index 1, keep en
    r = fvm.attempt_remove_non_whitelisted_subs(_item(subs=["en", "fre"]), "English")
    assert r["success"] is True
    assert r["removed"] == ["fre"] and r["remaining"] == ["en"]
    assert _sub_maps(no_external) == [1]


def test_sub_risk1_approved_all_confirmed(no_external):
    # RISK-1 approved case: only confirmed non-English subs -> ALL may be removed
    r = fvm.attempt_remove_non_whitelisted_subs(_item(subs=["fre", "ara"]), "English")
    assert r["success"] is True
    assert r["removed"] == ["fre", "ara"] and r["remaining"] == []
    assert _sub_maps(no_external) == [0, 1]


def test_sub_risk1_hold_ass_srt_never_removed(no_external):
    # Bleach S17E14 / Draw This Then Die: format tokens, not languages -> HOLD
    r = fvm.attempt_remove_non_whitelisted_subs(_item(subs=["ASS", "SRT"]), "English")
    assert r["success"] is False
    assert no_external == []


def test_sub_risk2_suspected_english_never_removed(no_external):
    # People of Earth: 'English [CC]' is suspected-English -> EXCLUDE, not strip
    r = fvm.attempt_remove_non_whitelisted_subs(_item(subs=["en", "English [CC]"]), "English")
    assert r["success"] is False
    assert no_external == []


def test_sub_bug5_und_kept(no_external):
    # BUG-5: 'und' must never be auto-removed; nothing confirmed -> no-op
    r = fvm.attempt_remove_non_whitelisted_subs(_item(subs=["en", "und"]), "English")
    assert r["success"] is False
    assert no_external == []


def test_sub_fan_sub_name_never_removed(no_external):
    # RISK-2: fan-sub group name (could be a good English sub) -> EXCLUDE
    r = fvm.attempt_remove_non_whitelisted_subs(_item(subs=["en", "Nekomimi - No Honorifics"]), "English")
    assert r["success"] is False
    assert no_external == []


def test_audio_remove_confirmed_only(no_external):
    r = fvm.attempt_remove_non_whitelisted_audio(_item(audio=["eng", "fre"]), "English, Japanese, Korean")
    assert r["success"] is True
    assert r["removed"] == ["fre"] and r["remaining"] == ["eng"]


def test_audio_never_removes_all(no_external):
    # Miscategorized foreign file with only one non-English track -> keep it
    r = fvm.attempt_remove_non_whitelisted_audio(_item(audio=["fre"]), "English, Japanese, Korean")
    assert r["success"] is False
    assert no_external == []


def test_audio_risk2_labels_kept(no_external):
    # RISK-2 audio: 'Stereo' is a channel label (possibly English alt-audio) -> KEEP
    r = fvm.attempt_remove_non_whitelisted_audio(_item(audio=["eng", "Stereo"]), "English")
    assert r["success"] is False
    assert no_external == []


def test_foreign_path_all_changes_skipped(no_external):
    item = _item(subs=["fre"], audio=["fre"])
    item["path"] = "/mnt/A16000/plex/foreign_tv_shows/Show/ep.mkv"
    assert fvm.attempt_remove_non_whitelisted_subs(item, "English")["success"] is False
    assert fvm.attempt_remove_non_whitelisted_audio(item, "English")["success"] is False
    assert no_external == []

