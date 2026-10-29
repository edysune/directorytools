"""Tests for tools/video_audio_scripts/applyVideoMetadata.py (Phase-2 applier).

The applier wraps three subprocess tools (mkvmerge/mkvpropedit, ffprobe).
These tests monkeypatch those at the module boundary and use real temp files
for the file-movement logic (backup, atomic swap, restore-on-failure).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "video_audio_scripts"))

import applyVideoMetadata as avm
import languagePolicy as lp
import runVideoMetadata as rv


def make_item(path, aud, subs, fmt="matroska,webm", dur="100.0"):
    """Build a scan-schema item with sequential global stream indices.

    Indices start at 1 to mirror real files (stream 0 is the video track,
    which the apply engine never touches).
    """
    item = {
        "path": str(path),
        "filename": Path(path).name,
        "format": fmt,
        "duration": dur,
        "size": 1234,
        "audio_streams": [],
        "subtitle_streams": [],
    }
    idx = 1  # 0 = (implicit) video track
    for lang, default in aud:
        item["audio_streams"].append(
            {"index": idx, "codec": "aac", "language": lang, "default": default,
             "forced": False, "channels": 2}
        )
        idx += 1
    for lang in subs:
        if isinstance(lang, tuple):
            lang = lang[0]
        item["subtitle_streams"].append(
            {"index": idx, "codec": "ass", "language": lang, "default": False,
             "forced": False, "duration": dur}
        )
        idx += 1
    return item


# --------------------------------------------------------------------------- #
# plan_file (pure)
# --------------------------------------------------------------------------- #
def test_plan_audio_removal_numbering(tmp_path):
    p = tmp_path / "x.mkv"
    p.write_bytes(b"0" * 100)
    item = make_item(p, [("jpn", True), ("eng", False)], [])
    pl = avm.plan_file(item, "English", "English", "English")
    assert pl["skip"] is None
    assert pl["actions"] and pl["actions"][0].startswith("AUD")
    assert pl["aud_to_remove_a"] == [1]            # jpn is a1
    assert pl["default_target_a"] == 1             # eng (was a2) becomes a1 after removal


def test_plan_audio_removal_keeps_english_default_global_pos(tmp_path):
    p = tmp_path / "y.mkv"
    p.write_bytes(b"0" * 100)
    # a1=fre, a2=jpn, a3=eng
    item = make_item(p, [("fre", True), ("jpn", False), ("eng", False)], [])
    pl = avm.plan_file(item, "English", "English", "English")
    # fre+jpn confirmed -> both removed, eng survives as a1
    assert pl["aud_to_remove_a"] == [1, 2]
    assert pl["default_target_a"] == 1


def test_plan_und_audio_never_removed(tmp_path):
    p = tmp_path / "z.mkv"
    p.write_bytes(b"0" * 100)
    item = make_item(p, [("eng", True), ("und", False)], [])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    assert not any(a.startswith("AUD") for a in pl["actions"])
    assert pl["aud_to_remove_a"] == []
    assert pl["sub_state"] in ("none", "clean")


def test_plan_single_audio_never_removed(tmp_path):
    p = tmp_path / "s.mkv"
    p.write_bytes(b"0" * 100)
    item = make_item(p, [("jpn", True)], [("jpn",)])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    assert not any(a.startswith(("AUD",)) for a in pl["actions"])
    # no English sub, all confirmed (jpn) -> ALL approved
    assert any(a.startswith("ALL") for a in pl["actions"])


def test_plan_ambiguous_sub_holds_all_subs(tmp_path):
    p = tmp_path / "h.mkv"
    p.write_bytes(b"0" * 100)
    item = make_item(p, [("eng", True)], [("fre",), ("und",)])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    assert not any(a.startswith(("SUB", "ALL")) for a in pl["actions"])
    assert pl["sub_state"] == "held_ambiguous"


def test_plan_keep_english_removes_confirmed_only(tmp_path):
    p = tmp_path / "k.mkv"
    p.write_bytes(b"0" * 100)
    item = make_item(p, [("eng", True)], [("eng",), ("jpn",), ("fre",)])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    assert pl["sub_state"] == "remove_confirmed"
    assert pl["sub_to_remove_s"] == [2, 3]         # eng=a? subs: eng=1, jpn=2, fre=3


def test_plan_foreign_category_skipped(tmp_path):
    p = tmp_path / "f.mkv"
    p.write_bytes(b"0" * 100)
    item = make_item("/mnt/A16000/foreign_tv_shows/Show/S.mkv", [("eng", True)], [("fre",)])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    assert pl["skip"] == "foreign_category"
    assert pl["actions"] == []


def test_plan_non_matroska_skipped(tmp_path):
    p = tmp_path / "x.mp4"
    p.write_bytes(b"0" * 100)
    item = make_item(p, [("eng", True), ("fre", True)], [("fre",)], fmt="mp4")
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    assert pl["skip"] and "unsupported_format" in pl["skip"]


def test_plan_default_only_global_position(tmp_path):
    p = tmp_path / "d.mkv"
    p.write_bytes(b"0" * 100)
    # a1=fre(default), a2=jpn, a3=eng -> DEF target must be GLOBAL a3, not 1
    item = make_item(p, [("fre", True), ("jpn", False), ("eng", False)], [])
    # force classify: default_audio_fixable = True (fre default + eng preferred)
    # but fre/jpn are not in audio_whitelist -> audio removal also planned.
    # To isolate DEF-only use an audio whitelist that keeps fre+jpn:
    pl = avm.plan_file(item, "English", "English, Japanese, Korean, French", "English")
    # fre/jpn now whitelisted -> no AUD; DEF should pick global a3
    defacts = [a for a in pl["actions"] if a.startswith("DEF")]
    assert defacts and "track 3" in defacts[0] or defacts and pl["default_target_a"] == 3


# --------------------------------------------------------------------------- #
# free-space gate
# --------------------------------------------------------------------------- #
def test_free_space_gate(monkeypatch, tmp_path):
    d = tmp_path / "media"
    d.mkdir()
    f1 = d / "a.mkv"; f1.write_bytes(b"0" * 1024)
    f2 = d / "b.mkv"; f2.write_bytes(b"0" * 1024)

    monkeypatch.setattr(avm.shutil, "disk_usage", lambda p: type("U", (), {"free": 0})())
    problems = avm.free_space_ok([str(f1), str(f2)], margin_gib=0)
    assert problems and "free" in problems[0]

    monkeypatch.setattr(avm.shutil, "disk_usage",
                        lambda p: type("U", (), {"free": 10 * 1024 * 1024})())
    assert avm.free_space_ok([str(f1), str(f2)], margin_gib=0) == []


# --------------------------------------------------------------------------- #
# apply_file (real fs, mocked muxers + probes)
# --------------------------------------------------------------------------- #
def _mock_tools(monkeypatch, after_item, raw_after, fail_cmd=None):
    """after_item: the probe result verify_file must see (or None for probe fail)."""
    cmds = []

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        if fail_cmd and cmd[0] == fail_cmd:
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="boom")
        # simulate mkvmerge: create the -o target so os.replace works
        if cmd and cmd[0] == "mkvmerge":
            out = cmd[cmd.index("-o") + 1]
            Path(out).write_bytes(b"MUXED")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(avm.rv, "analyze_file", lambda path, timeout: after_item)
    monkeypatch.setattr(avm.rv, "run_ffprobe", lambda path, timeout: raw_after)
    return cmds


def test_apply_happy_path_with_backup_atomic_swap(tmp_path, monkeypatch):
    p = tmp_path / "x.mkv"
    p.write_bytes(b"ORIGINALBYTES")
    item = make_item(p, [("jpn", True), ("eng", False)], ["jpn"])
    pl = avm.plan_file(item, "English", "English", "English")
    # aud: jpn removed (a1) -> eng default a1 ; subs: only jpn, confirmed non-English -> ALL
    assert pl["aud_to_remove_a"] == [1]
    assert pl["default_target_a"] == 1
    assert pl["sub_to_remove_s"] == [1]
    after_item = make_item(p, [("eng", True)], [])
    raw_after = {"streams": [{"codec_type": "video", "codec_name": "h264"},
                             {"codec_type": "audio", "codec_name": "aac"}]}
    _mock_tools(monkeypatch, after_item, raw_after)

    res = avm.apply_file(pl, item, probe_timeout=5)
    assert res["status"] == "ok", res
    # backup kept, original replaced with muxed content
    assert (tmp_path / "x.mkv.orig").read_bytes() == b"ORIGINALBYTES"
    assert p.read_bytes() == b"MUXED"
    assert not (tmp_path / "x.mkv.tmp-fix").exists()


def test_apply_mkmerge_fails_restores_backup(tmp_path, monkeypatch):
    p = tmp_path / "x.mkv"
    p.write_bytes(b"ORIGINALBYTES")
    item = make_item(p, [("jpn", True), ("eng", False)], [])
    pl = avm.plan_file(item, "English", "English", "English")
    assert pl["aud_to_remove_a"] == [1]          # forces a mux -> mkvmerge path
    _mock_tools(monkeypatch, make_item(p, [("eng", True)], []),
                {"streams": [{"codec_type": "video"}]}, fail_cmd="mkvmerge")

    res = avm.apply_file(pl, item, probe_timeout=5)
    assert res["status"] == "failed_cmd"
    # original must be byte-identical and NO backup left behind (restored)
    assert p.read_bytes() == b"ORIGINALBYTES"
    assert not (tmp_path / "x.mkv.orig").exists()


def test_apply_verify_mismatch_restores_and_flags(tmp_path, monkeypatch):
    p = tmp_path / "x.mkv"
    p.write_bytes(b"ORIGINALBYTES")
    item = make_item(p, [("eng", True), ("fre", True)], [])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    # probe AFTER returns an extra fre track (simulates muxer bug)
    bad_after = make_item(p, [("eng", True), ("fre", True)], [])
    raw_after = {"streams": [{"codec_type": "video"}]}
    _mock_tools(monkeypatch, bad_after, raw_after)

    res = avm.apply_file(pl, item, probe_timeout=5)
    assert res["status"] == "failed_verify"
    assert p.read_bytes() == b"ORIGINALBYTES"
    assert not (tmp_path / "x.mkv.orig").exists()


def test_apply_backup_conflict_skips(tmp_path, monkeypatch):
    p = tmp_path / "x.mkv"
    p.write_bytes(b"ORIGINALBYTES")
    (tmp_path / "x.mkv.orig").write_bytes(b"TRUE ORIGINAL")
    item = make_item(p, [("eng", True), ("fre", True)], [])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean", "English")
    after_item = make_item(p, [("eng", True)], [])
    raw_after = {"streams": [{"codec_type": "video"}]}
    _mock_tools(monkeypatch, after_item, raw_after)

    res = avm.apply_file(pl, item, probe_timeout=5)
    assert res["status"] == "skipped_backup_conflict"
    assert p.read_bytes() == b"ORIGINALBYTES"
    assert (tmp_path / "x.mkv.orig").read_bytes() == b"TRUE ORIGINAL"


def test_apply_default_only_full_copy_mux(tmp_path, monkeypatch):
    p = tmp_path / "d.mkv"
    p.write_bytes(b"ORIGINALBYTES")
    item = make_item(p, [("fre", True), ("eng", False)], [])
    pl = avm.plan_file(item, "English", "English, Japanese, Korean, French", "English")
    assert pl["default_target_a"] == 2 and not pl["aud_to_remove_a"]
    # globals: eng audio is global index 2; fre (survives) gets an explicit false flag
    assert pl["default_target_global"] == 2
    assert pl["default_others_global"] == [1]
    after_item = make_item(p, [("fre", False), ("eng", True)], [])
    raw_after = {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}, {"codec_type": "audio"}]}
    cmds_list = _mock_tools(monkeypatch, after_item, raw_after)
    res = avm.apply_file(pl, item, probe_timeout=5)
    assert res["status"] == "ok", res
    # DEF now requires a full stream-copy re-mux; the flag comes from mkvmerge
    mg = [c for c in cmds_list if c[0] == "mkvmerge"]
    assert len(mg) == 1
    cmd = mg[0]
    assert "-y" not in cmd
    assert not any(a.startswith("--no-") for a in cmd)
    assert "--default-track-flag" in cmd
    i = cmd.index("--default-track-flag")
    assert cmd[i + 1] == "2:true"
    j = cmd.index("--default-track-flag", i + 2)
    assert cmd[j + 1] == "1:false"
    assert cmd[-1] == str(p)
    assert not any(c[0] == "mkvpropedit" for c in cmds_list)
    # fully replaced (re-muxed copy), pristine backup kept
    assert p.read_bytes() == b"MUXED"
    assert (tmp_path / "d.mkv.orig").read_bytes() == b"ORIGINALBYTES"


# --------------------------------------------------------------------------- #
# build_mkvmerge_cmd — exact command shape (mkvmerge 84.0, verified 2026-10-29)
# --------------------------------------------------------------------------- #
def _pinfo(**kw):
    base = {
        "aud_rm_global": [], "aud_keep_global": None,
        "sub_rm_global": [], "sub_keep_global": None,
        "default_target_a": None, "default_target_global": None, "default_others_global": [],
    }
    base.update(kw)
    return base


def test_build_cmd_def_only_exact():
    cmd = avm.build_mkvmerge_cmd(
        _pinfo(default_target_global=3, default_others_global=[1, 2]),
        out="/t.mkv", inpath="/s.mkv")
    assert cmd == [
        "mkvmerge", "-o", "/t.mkv",
        "--default-track-flag", "3:true",
        "--default-track-flag", "1:false",
        "--default-track-flag", "2:false",
        "/s.mkv",
    ]


def test_build_cmd_all_subs_drop():
    cmd = avm.build_mkvmerge_cmd(_pinfo(sub_keep_global=[]), out="/t.mkv", inpath="/s.mkv")
    assert cmd == ["mkvmerge", "-o", "/t.mkv", "-S", "/s.mkv"]


def test_build_cmd_keep_lists_plus_def():
    cmd = avm.build_mkvmerge_cmd(
        _pinfo(aud_keep_global=[2, 4], sub_keep_global=[6],
               default_target_global=2, default_others_global=[4]),
        out="/t.mkv", inpath="/s.mkv")
    assert "-a" in cmd and cmd[cmd.index("-a") + 1] == "2,4"
    assert "-s" in cmd and cmd[cmd.index("-s") + 1] == "6"
    assert "2:true" in cmd and "4:false" in cmd
    # nothing that mkvmerge 84.0 rejects:
    assert "-y" not in cmd
    assert not any(x.startswith("--no-") for x in cmd)


def test_bin_check_missing(monkeypatch):
    monkeypatch.setattr(avm.shutil, "which", lambda n: None)
    assert avm.bin_check() == ["ffprobe", "mkvmerge"]


# --------------------------------------------------------------------------- #
# main() end-to-end (regression: main loop must call apply_file with the right
# keyword args and finish the full apply cycle)
# --------------------------------------------------------------------------- #
def _main_argv(root, outdir, extra=()):
    return [
        "applyVideoMetadata.py", str(root),
        "--subtitle-whitelist", "English",
        "--audio-whitelist", "English, Japanese, Korean",
        "--default-audio-language", "English",
        "--output-dir", str(outdir),
        *extra, "--apply",
    ]


def _fake_tools(monkeypatch, fail_mkvmerge: bool):
    """Fake subprocess.run: ffprobe returns BEFORE/AFTER stream state based on
    path suffix; mkvmerge copies input to -o (and optionally fails)."""
    cmds = []

    def before_json(path: Path) -> str:
        return json.dumps({
            "format": {"format_name": "matroska,webm",
                       "duration": "100.0", "size": str(path.stat().st_size)},
            "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "h264",
                 "tags": {}, "disposition": {}},
                {"index": 1, "codec_type": "audio", "codec_name": "aac",
                 "tags": {"language": "eng"}, "disposition": {"default": 1}},
                {"index": 2, "codec_type": "audio", "codec_name": "aac",
                 "tags": {"language": "fre"}, "disposition": {"default": 0}},
                {"index": 3, "codec_type": "subtitle", "codec_name": "subrip",
                 "tags": {"language": "eng"}, "disposition": {}},
                {"index": 4, "codec_type": "subtitle", "codec_name": "subrip",
                 "tags": {"language": "fre"}, "disposition": {}},
            ],
        })

    def after_json(path: Path) -> str:
        return json.dumps({
            "format": {"format_name": "matroska,webm",
                       "duration": "100.0", "size": str(path.stat().st_size)},
            "streams": [
                {"index": 0, "codec_type": "video", "codec_name": "h264",
                 "tags": {}, "disposition": {}},
                {"index": 1, "codec_type": "audio", "codec_name": "aac",
                 "tags": {"language": "eng"}, "disposition": {"default": 1}},
                {"index": 2, "codec_type": "subtitle", "codec_name": "subrip",
                 "tags": {"language": "eng"}, "disposition": {}},
            ],
        })

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        name = cmd[0]
        if name == "ffprobe":
            p = Path(cmd[-1])
            payload = after_json(p) if p.name.endswith(avm.TMP_SUFFIX) else before_json(p)
            return subprocess.CompletedProcess(cmd, 0, stdout=payload)
        if name == "mkvmerge":
            if fail_mkvmerge:
                raise subprocess.CalledProcessError(1, cmd, output="", stderr="mux boom")
            out = Path(cmd[cmd.index("-o") + 1])
            src = Path(cmd[-1])
            out.write_bytes(src.read_bytes() + b"MUXED")
            return subprocess.CompletedProcess(cmd, 0)
        # mkvpropedit / anything else
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr(avm.shutil, "which", lambda b: "/bin/fake-" + b)
    monkeypatch.setattr(avm.shutil, "disk_usage",
                        lambda p: type("U", (), {"free": 100 * 1024 ** 3})())
    return cmds


def test_main_apply_end_to_end_ok(tmp_path, monkeypatch, capsys):
    media = tmp_path / "media" / "Show"
    media.mkdir(parents=True)
    vid = media / "Show - S01E01.mkv"
    vid.write_bytes(b"ORIGINALBYTES")
    outdir = tmp_path / "out"

    cmds = _fake_tools(monkeypatch, fail_mkvmerge=False)
    monkeypatch.setattr("sys.argv", _main_argv(tmp_path / "media", outdir))

    rc = avm.main()
    assert rc == 0
    # original replaced with muxed content, pristine backup kept, no temp left
    assert vid.read_bytes() == b"ORIGINALBYTESMUXED"
    assert (media / "Show - S01E01.mkv.orig").read_bytes() == b"ORIGINALBYTES"
    assert not (media / "Show - S01E01.mkv.tmp-fix").exists()
    # muxer got the right per-type removals as GLOBAL keep-lists:
    # fre audio (global 2) + fre sub (global 4) dropped; eng audio 1 + eng sub 3 kept
    mg = [c for c in cmds if c[0] == "mkvmerge"]
    assert len(mg) == 1
    cmd = mg[0]
    assert "-a" in cmd and cmd[cmd.index("-a") + 1] == "1"
    assert "-s" in cmd and cmd[cmd.index("-s") + 1] == "3"
    # sole default flag set on the surviving eng audio (global 1) — via mkvmerge
    assert "--default-track-flag" in cmd and "1:true" in cmd
    assert "-y" not in cmd and not any(x.startswith("--no-") for x in cmd)
    assert not any(c[0] == "mkvpropedit" for c in cmds)
    # report written
    reports = list(outdir.glob("apply_*.json"))
    assert reports and json.loads(reports[0].read_text())["rc"] == 0


def test_main_apply_end_to_end_failure_restores(tmp_path, monkeypatch):
    media = tmp_path / "media" / "Show"
    media.mkdir(parents=True)
    vid = media / "Show - S01E01.mkv"
    vid.write_bytes(b"ORIGINALBYTES")
    outdir = tmp_path / "out"

    _fake_tools(monkeypatch, fail_mkvmerge=True)
    monkeypatch.setattr("sys.argv", _main_argv(tmp_path / "media", outdir))

    rc = avm.main()
    assert rc == 1
    # original byte-identical, backup cleaned up, no temp left
    assert vid.read_bytes() == b"ORIGINALBYTES"
    assert not (media / "Show - S01E01.mkv.orig").exists()
    assert not (media / "Show - S01E01.mkv.tmp-fix").exists()
    reports = list(outdir.glob("apply_*.json"))
    assert reports and json.loads(reports[0].read_text())["rc"] == 1
