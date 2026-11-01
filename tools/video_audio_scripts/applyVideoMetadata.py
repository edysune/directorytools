#!/usr/bin/env python3
"""applyVideoMetadata.py — Phase-2 non-interactive apply-mode engine.

Applies the SAME tri-state policy the dry-run runner reports
(languagePolicy.py: keep / confirmed / ambiguous), for Matroska files only:

  DEF  set the preferred (English) audio track as the SOLE default
       (mkvmerge --default-track-flag, stream copy — a full re-mux is required;
       mkvpropedit 84.0 is NOT used: it silently fails or corrupts in that build)
  AUD  remove non-whitelisted audio tracks          (mkvmerge -a keep-list, stream copy)
  SUB  remove non-English subtitles, English kept   (mkvmerge -s keep-list, stream copy)
  ALL  remove ALL subtitles — only when 100% confirmed non-English (RISK-1, user-approved)
       (mkvmerge -S)

mkvmerge syntax note (empirically verified on mkvtoolnix 84.0, 2026-10-29):
  * there is NO `-y` overwrite flag — `-y` means `--sync TID:d` and BREAKS the run.
    Overwrite is automatic; we also unlink any stale .tmp-fix before muxing.
  * there is NO `--no-a:<n>` / `--no-s:<n>` per-track exclusion. Track selection is a
    POSITIVE keep-list over GLOBAL 0-based track IDs (== ffprobe stream index):
    `-a 1,2` keeps only those audios, `-A` drops all audios; `-s 3,4` / `-S` for subs.
  * default flags are set in the SAME mux pass: `--default-track-flag <TID>:true|false`.
    Convention in the container build: default = flag byte omitted, non-default = explicit 0.
  * Language restatement: mkvmerge 84.0 has been observed DROPPING the language tag of
    some subtitle tracks on re-mux (2026-10-30, Back Arrow S01E17: the 'Signs@EMBER'
    signs sub lost its 'eng' label; verifier caught it -> restored). Every kept track's
    known language is therefore re-asserted with `--language <TID>:<code>` in the same
    pass so the post-mux state matches the scan state. Tracks whose recorded language
    is not a clean code (labels, title fallbacks like 'Signs@EMBER') are NOT asserted —
    an invalid code would abort the mux (and re-asserting a wrong label would be wrong).
  * Verification of the default still uses ffprobe `disposition.default`, which this
    ffprobe (6.1.1) fills correctly for Matroska (checked on muxed outputs).

Safety contract (user rules, 2026-10-28):
  * NEVER modify a file under an excluded foreign-nature category (languagePolicy.is_path_excluded)
  * NEVER remove a track whose language is "ambiguous" (und/untagged/label/fan-sub/suspected-English)
  * NEVER delete the last audio track of a file
  * Backup BEFORE any change: <file> -> <file>.orig (an existing .orig is NEVER overwritten;
    the file is skipped instead so the original is never clobbered)
  * Free-space gate: per target dir, free >= 2 * sum(file sizes) + margin
    (backup copy + mkvmerge temp live beside the original)
  * All edits via stream copy (mkvmerge) — never re-encode. DEF (default flag)
    now requires a full stream-copy re-mux (157-class DEF files are rewritten
    once, ~file size of extra disk, a few minutes per 4 GB file) because the
    mkvpropedit 84.0 build in the container cannot set flags reliably.
  * Write to <file>.tmp-fix, verify with ffprobe (video count, audio/subtitle set, default flag),
    then atomic os.replace onto the original
  * Any verification failure -> auto-restore from .orig; the failure is counted
    and the batch CONTINUES until a failure threshold trips (see below)

Modes:
  default        DRY-RUN: prints the per-file plan + commands, no changes (exit 0)
  --apply        performs the work (requires the dry-run plan to look right)

Exit codes: 0 = done (dry-run or all applied); 1 = run finished but some files
failed/skipped (each failed file's original was restored before continuing);
2 = batch STOPPED EARLY because a failure threshold was reached, or a
verification failure occurred — investigate before re-running;
3 = environment/config error (missing binaries, unreadable root, scan error).

Failure thresholds (--max-consecutive-failures default 5, --max-total-failures
default 20; 0 = unlimited): a per-file failure is LOGGED AND CONTINUED (the
original is always restored / the temp cleaned before moving on), so a single
corrupt file cannot stall a whole drive. But back-to-back or numerous failures
usually mean a systemic problem (wedged CIFS mount, out of space, wrong
policy), so when a threshold trips the remaining files are left untouched and
the run exits 2.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import languagePolicy as lp
import runVideoMetadata as rv  # classify() + analyze_file() — single probe/classify source

BACKUP_SUFFIX = ".orig"
TMP_SUFFIX = ".tmp-fix"
MARGIN_GIB_DEFAULT = 2.0

# A restat-able track language: ISO 639-1/2 (2-3 letters) with an optional
# BCP-47 subtag (region/script), e.g. 'eng', 'en-us', 'zh-hans'. Deliberately
# strict: anything else ('Signs@EMBER', 'und', labels) is NOT asserted back.
_LANG_CODE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


# --------------------------------------------------------------------------- #
# planning
# --------------------------------------------------------------------------- #
def matroska_index_maps(item: dict):
    """Map ffprobe-global stream index -> 1-based per-type track number (probe order)."""
    aud = {}
    sub = {}
    for i, a in enumerate(item.get("audio_streams") or [], 1):
        aud[a.get("index")] = i
    for i, s in enumerate(item.get("subtitle_streams") or [], 1):
        sub[s.get("index")] = i
    return aud, sub


def video_track_count(raw_probe: dict | None) -> int:
    if not raw_probe:
        return -1  # unknown -> treated as "can't verify", not "changed"
    return sum(1 for s in raw_probe.get("streams", []) if s.get("codec_type") == "video")


def plan_file(item: dict, sub_wl: str, audio_wl: str, default_lang: str) -> dict:
    """Derive the concrete action for one scanned file from the shared classifier."""
    p = item["path"]
    c = rv.classify(item, sub_wl, audio_wl, default_lang)
    aud, sub = matroska_index_maps(item)

    sz = item.get("size")
    if isinstance(sz, str):
        try:
            sz = int(sz)
        except ValueError:
            sz = 0
    pinfo = {
        "path": p,
        "size": sz if sz else os.path.getsize(p),
        "video_tracks": None,          # filled from raw probe when available
        "actions": [],                 # subset of DEF / AUD / SUB / ALL
        "aud_to_remove_a": sorted({aud[a["index"]] for a in c["aud_to_remove"] if a.get("index") in aud}),
        "sub_to_remove_s": sorted({sub[s["index"]] for s in c.get("sub_to_remove", []) if (s.get("index") is not None and s.get("index") in sub)}),
        # global 0-based stream indices (ffprobe index / mkvmerge track IDs):
        "aud_rm_global": sorted({a["index"] for a in c["aud_to_remove"] if a.get("index") is not None}),
        "sub_rm_global": sorted({s["index"] for s in c.get("sub_to_remove", []) if s.get("index") is not None}),
        "default_target_a": None,
        "default_target_global": None,
        "sub_state": c["sub_state"],
        "aud_state": c["aud_state"],
        "skip": None,
    }

    if lp.is_path_excluded(p):
        pinfo["skip"] = "foreign_category"
        return pinfo

    fmt = (item.get("format") or "").lower()
    if "matroska" not in fmt:
        pinfo["skip"] = "unsupported_format (%s)" % item.get("format")
        return pinfo

    if not (item.get("audio_streams") or item.get("subtitle_streams")):
        pinfo["skip"] = "no audio or subtitle streams"
        return pinfo

    # --- audio removal (classifier already enforces: no ambiguous, >=1 kept, never last) ---
    aud_remove = pinfo["aud_to_remove_a"]
    audio_streams = item.get("audio_streams") or []
    if aud_remove:
        pinfo["actions"].append("AUD: remove audio " + ",".join(str(i) for i in aud_remove))
        # the default must land on a surviving track; express in POST-removal numbering
        survivors = [i for i in range(1, len(audio_streams) + 1) if i not in set(aud_remove)]
        g_target = None
        for g in range(1, len(audio_streams) + 1):
            if g not in set(aud_remove) and lp.matches_whitelist(
                audio_streams[g - 1].get("language"), default_lang
            ):
                g_target = g
                break
        if g_target is None:
            pinfo["skip"] = "no default audio target remains after removal"
            pinfo["actions"] = []
            pinfo["aud_to_remove_a"] = []
            return pinfo
        pinfo["default_target_a"] = survivors.index(g_target) + 1
    # subtitle removal
    if c["sub_state"] == "remove_confirmed":
        assert pinfo["sub_to_remove_s"], "no subtitle indices to remove"
        pinfo["actions"].append("SUB: remove subtitles " + ",".join(str(i) for i in pinfo["sub_to_remove_s"]) + " (keep English)")
    elif c["sub_state"] == "remove_all_approved":
        all_s = sorted(sub.values())
        if not all_s:
            pinfo["skip"] = "no subtitle tracks found to remove (stale scan?)"
            return pinfo
        pinfo["sub_to_remove_s"] = all_s
        pinfo["actions"].append("ALL: remove ALL subtitles (100% confirmed non-English, RISK-1 approved)")

    # --- global track IDs (0-based, == ffprobe stream index == mkvmerge track ID) ---
    aud_rm = set(aud_remove)
    pinfo["aud_rm_global"] = sorted(audio_streams[i - 1]["index"] for i in aud_rm if audio_streams[i - 1].get("index") is not None)
    pinfo["aud_keep_global"] = sorted(
        a["index"] for i, a in enumerate(audio_streams, 1)
        if i not in aud_rm and a.get("index") is not None
    ) if aud_rm else None  # None = "keep all audio" (no -a needed)
    sub_rm = set(pinfo["sub_to_remove_s"])
    sub_keep_global = [
        s["index"] for i, s in enumerate(item.get("subtitle_streams") or [], 1)
        if i not in sub_rm and s.get("index") is not None
    ] if sub_rm else None
    pinfo["sub_keep_global"] = sub_keep_global  # [] => drop ALL (-S); None => no sub action

    # --- language restatement: re-assert every KEPT track's known language so a
    #     re-mux cannot silently drop one (mkvmerge 84.0 quirk, Back Arrow S01E17).
    #     Kept-set semantics mirror build_mkvmerge_cmd: None = no removal (all kept).
    keep_a = pinfo.get("aud_keep_global")
    keep_a_ids = {i for i in keep_a} if keep_a is not None else \
        {a["index"] for a in item.get("audio_streams") or [] if a.get("index") is not None}
    keep_s = pinfo.get("sub_keep_global")
    keep_s_ids = {i for i in keep_s} if keep_s is not None else \
        {s["index"] for s in item.get("subtitle_streams") or [] if s.get("index") is not None}
    pinfo["track_langs"] = _restated_track_langs(item, keep_a_ids, keep_s_ids)

    # --- default audio reorder (only when we are not already removing audio) ---
    if not pinfo["actions"] or "AUD" not in " ".join(pinfo["actions"]):
        if c["default_audio_fixable"]:
            target = _global_a_target(item["audio_streams"], default_lang)
            if target is not None:
                pinfo["default_target_a"] = target
                pinfo["actions"].insert(0, "DEF: set audio track %d as sole default" % target)
            else:
                pinfo["skip"] = "preferred audio not found"
                return pinfo

    # --- default audio: express the target as a GLOBAL track ID (mkvmerge --default-track-flag) ---
    if pinfo["default_target_a"] is not None:
        # position is 1-based probe-order; map to that stream's global index
        n_aud = len(audio_streams)
        if aud_rm:
            # position among survivors -> find surviving stream at that position
            surv = [i for i in range(1, n_aud + 1) if i not in aud_rm]
            stream_pos = surv[pinfo["default_target_a"] - 1]
        else:
            stream_pos = pinfo["default_target_a"]
        tgt = audio_streams[stream_pos - 1].get("index")
        pinfo["default_target_global"] = tgt
        # only tracks that SURVIVE need (can have) flags — dropped tracks are excluded
        kept = set(pinfo.get("aud_keep_global")) if pinfo.get("aud_keep_global") is not None else \
            {s["index"] for s in audio_streams if s.get("index") is not None}
        pinfo["default_others_global"] = [
            s["index"] for s in audio_streams
            if s.get("index") is not None and s["index"] in kept and s["index"] != tgt
        ]

    if not pinfo["actions"]:
        pinfo["skip"] = "no action needed"
    return pinfo


def _global_a_target(audio_list: list, default_lang: str) -> int | None:
    """1-based probe-order position of the first track matching the default language."""
    for i, a in enumerate(audio_list, 1):
        if lp.matches_whitelist(a.get("language"), default_lang):
            return i
    return None


def _restated_track_langs(item: dict, keep_a_ids: set, keep_s_ids: set) -> dict:
    """Map global track id -> language code for every kept track with a clean code.

    Used to re-assert languages inside the mkvmerge pass (some subtitle tracks lose
    their language tag on re-mux — see module docstring). Non-code values (labels,
    title fallbacks, empties) are skipped: asserting them would abort the mux.
    """
    out: dict[int, str] = {}
    for s in item.get("audio_streams") or []:
        i, code = s.get("index"), s.get("language")
        if i is not None and i in keep_a_ids and _LANG_CODE_RE.fullmatch(code or ""):
            out[int(i)] = code.lower()
    for s in item.get("subtitle_streams") or []:
        i, code = s.get("index"), s.get("language")
        if i is not None and i in keep_s_ids and _LANG_CODE_RE.fullmatch(code or ""):
            out[int(i)] = code.lower()
    return out


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #
def expected_state_after(pinfo: dict, item: dict) -> dict:
    """What the file MUST probe as after the fix (used by verify_file)."""
    aud_keep = [a for i, a in enumerate(item.get("audio_streams") or [], 1) if i not in set(pinfo["aud_to_remove_a"])]
    sub_keep = [s for i, s in enumerate(item.get("subtitle_streams") or [], 1) if i not in set(pinfo["sub_to_remove_s"])]
    return {
        "audio_count": len(aud_keep),
        "audio_langs": sorted((a.get("language") or "unknown") for a in aud_keep),
        "sub_count": len(sub_keep),
        "sub_langs": sorted((s.get("language") or "unknown") for s in sub_keep),
        "default_audio_pos": pinfo["default_target_a"],
    }


def probe_state(path: Path, timeout: float) -> dict | None:
    item = rv.analyze_file(path, timeout)
    if not item or "error" in item:
        return None
    aud = item.get("audio_streams") or []
    sub = item.get("subtitle_streams") or []
    raw = rv.run_ffprobe(path, timeout)
    default_pos = None
    for i, a in enumerate(aud, 1):
        if a.get("default"):
            default_pos = i  # (may be multi-default -> verifier flags if !=1 later)
    return {
        "audio_count": len(aud),
        "audio_langs": sorted((a.get("language") or "unknown") for a in aud),
        "audio_defaults": [i for i, a in enumerate(aud, 1) if a.get("default")],
        "sub_count": len(sub),
        "sub_langs": sorted((s.get("language") or "unknown") for s in sub),
        "video_count": video_track_count(raw),
    }


def verify_file(path: Path, expected: dict, video_before: int, timeout: float) -> tuple[bool, str, dict | None]:
    st = probe_state(path, timeout)
    if st is None:
        return False, "cannot ffprobe result", None
    if video_before >= 0 and st["video_count"] != video_before:
        return False, "video track count changed (%d -> %d)" % (video_before, st["video_count"]), st
    if st["audio_count"] != expected["audio_count"]:
        return False, "audio count %d != expected %d" % (st["audio_count"], expected["audio_count"]), st
    if st["audio_langs"] != expected["audio_langs"]:
        return False, "audio langs %s != expected %s" % (st["audio_langs"], expected["audio_langs"]), st
    if st["sub_count"] != expected["sub_count"]:
        return False, "sub count %d != expected %d" % (st["sub_count"], expected["sub_count"]), st
    if st["sub_langs"] != expected["sub_langs"]:
        return False, "sub langs %s != expected %s" % (st["sub_langs"], expected["sub_langs"]), st
    if expected["default_audio_pos"] is not None:
        if st["audio_defaults"] != [expected["default_audio_pos"]]:
            return False, "default audio not exactly track %d (got %s)" % (expected["default_audio_pos"], st["audio_defaults"]), st
    return True, "ok", st


# --------------------------------------------------------------------------- #
# apply loop
# --------------------------------------------------------------------------- #
def free_space_ok(paths: list, margin_gib: float) -> list[str]:
    """Per-directory gate: free >= 2*dir_bytes + margin (backup + temp both live beside original)."""
    import collections
    per = collections.defaultdict(int)
    for p in paths:
        per[os.path.dirname(p)] += pstat_size(p)
    gi = int(margin_gib * 1024 ** 3)
    bad = []
    for d, total in per.items():
        need = 2 * total + gi
        free = shutil.disk_usage(d).free
        if free < need:
            bad.append(f"{d}: free {free//1024**2}MiB < needed {need//1024**2}MiB")
    return bad


def pstat_size(p: str) -> int:
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def build_mkvmerge_cmd(pinfo: dict, out: str, inpath: str) -> list:
    """Construct the mkvmerge stream-copy command for one planned file.

    Pure function (no filesystem/subprocess) so the EXACT command can be unit
    tested against the empirically verified mkvmerge 84.0 syntax:
      * no `-y` (it means `--sync TID:d` and aborts the run)
      * positive keep-lists over GLOBAL 0-based track IDs: `-a 1,2` / `-s 3,4`
      * `-S` drops all subtitles (the "ALL" class); there is no per-track `--no-s:`
      * default flags in the same pass: `--default-track-flag <TID>:true|false`
      * language restatement (kept tracks with clean codes): `--language <TID>:<code>`
    """
    cmd = ["mkvmerge", "-o", out]
    # audio: classifier guarantees at least one audio always survives, so a
    # non-empty keep-list is always available whenever audio was removed
    keep_a = pinfo.get("aud_keep_global")
    if keep_a:
        cmd += ["-a", ",".join(str(i) for i in keep_a)]
    # subtitles: None = no subtitle action; [] = drop ALL (-S); [ids] = keep-list
    sub_keep = pinfo.get("sub_keep_global")
    if sub_keep is not None:
        if sub_keep:
            cmd += ["-s", ",".join(str(i) for i in sub_keep)]
        else:
            cmd += ["-S"]
    # language restatement: keeps a re-mux from dropping a track's language tag
    # (observed on mkvmerge 84.0; Back Arrow S01E17 signs sub, 2026-10-30)
    track_langs = pinfo.get("track_langs") or {}
    for tid in sorted(track_langs):
        cmd += ["--language", "%d:%s" % (tid, track_langs[tid])]
    # default audio: target true, every other surviving audio explicitly false
    tgt = pinfo.get("default_target_global")
    if tgt is not None:
        cmd += ["--default-track-flag", "%d:true" % tgt]
        for g in pinfo.get("default_others_global") or []:
            cmd += ["--default-track-flag", "%d:false" % g]
    cmd.append(inpath)
    return cmd


def apply_file(pinfo: dict, item: dict, probe_timeout: float, backup: bool = True) -> dict:
    """Apply one planned file. Returns a result dict (never raises)."""
    src = Path(pinfo["path"])
    bak = Path(str(src) + BACKUP_SUFFIX)
    tmp = Path(str(src) + TMP_SUFFIX)
    res = {"path": str(src), "status": "ok", "detail": "", "actions": list(pinfo["actions"])}
    try:
        # 1) backup (never clobber an existing original backup)
        if backup:
            if bak.exists():
                res.update(status="skipped_backup_conflict", detail=f"{bak.name} already exists; original already altered before - refusing to clobber")
                return res
            shutil.copy2(src, bak)
            if os.path.getsize(bak) != os.path.getsize(src):
                bak.unlink(missing_ok=True)
                res.update(status="failed_backup", detail="backup size mismatch")
                return res
        else:
            bak = None  # --no-backup
        # 2) mux — track removal and/or the default flag, one stream-copy pass
        #    (mkvmerge 84.0; verified syntax in the module docstring)
        needs_mux = bool(
            pinfo.get("aud_rm_global")
            or pinfo.get("sub_rm_global")
            or pinfo.get("default_target_global") is not None
        )
        if needs_mux:
            if tmp.exists():
                tmp.unlink()  # never feed a stale/partial output file to the muxer
            cmd = build_mkvmerge_cmd(pinfo, out=str(tmp), inpath=str(src))
            _run(cmd, res)
            if res["status"] != "ok":
                _restore(src, bak, tmp)
                return res
        # 3) verify
        expected = expected_state_after(pinfo, item)
        target_file = Path(str(tmp)) if needs_mux else Path(str(src))
        ok, why, st = verify_file(target_file, expected, -1, probe_timeout)
        if not ok:
            res.update(status="failed_verify", detail=why)
            _restore(src, bak, tmp)
            return res
        # 5) atomic swap (only when we muxed)
        if needs_mux:
            os.replace(tmp, src)
        res["after"] = st
        if bak is not None:
            res["backup"] = str(bak)
        return res
    except Exception as e:  # noqa: BLE001 - a crash here must not kill the batch or lose the backup
        res.update(status="failed_exception", detail=repr(e))
        _restore(src, bak, tmp)
        return res


def _run(cmd: list, res: dict) -> None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, check=True)
    except subprocess.CalledProcessError as e:
        res.update(status="failed_cmd", detail=(e.stderr or e.stdout or "")[-400:])
    except FileNotFoundError:
        res.update(status="failed_cmd", detail=f"binary not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        res.update(status="failed_cmd", detail="command timed out")


def _restore(src: Path, bak: Path | None, tmp: Path) -> None:
    tmp.unlink(missing_ok=True)
    if bak is not None and Path(bak).exists():
        try:
            os.replace(bak, src)
        except OSError:
            pass


def bin_check() -> list[str]:
    missing = [b for b in ("ffprobe", "mkvmerge") if not shutil.which(b)]
    return missing


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Apply video subtitle/audio metadata fixes (matroska, stream-copy).")
    ap.add_argument("root", help="media root to scan/apply")
    ap.add_argument("--scan", help="reuse a runVideoMetadata scan JSON instead of re-probing")
    ap.add_argument("--subtitle-whitelist", default="English")
    ap.add_argument("--audio-whitelist", default="English, Japanese, Korean")
    ap.add_argument("--default-audio-language", default="English")
    ap.add_argument("--ignore", action="append", default=[], help="path prefix to ignore (repeatable)")
    ap.add_argument("--only", action="append", default=[], help="case-insensitive substring filter on path (repeatable, pilots)")
    ap.add_argument("--limit", type=int, default=0, help="max files to apply (0 = all)")
    ap.add_argument("--min-free-gib", type=float, default=MARGIN_GIB_DEFAULT)
    ap.add_argument("--probe-timeout", type=float, default=60.0)
    ap.add_argument("--output-dir", default="output-apply")
    ap.add_argument("--apply", action="store_true", help="PERFORM the fixes (default is dry-run: plan only)")
    ap.add_argument("--no-backup", action="store_false", dest="backup", default=True,
                    help="skip .orig backups (DANGEROUS; not recommended)")
    ap.add_argument("--max-consecutive-failures", type=int, default=5,
                    help="stop the run after this many back-to-back file failures (default 5; 0 = unlimited)")
    ap.add_argument("--max-total-failures", type=int, default=20,
                    help="stop the run after this many file failures in total (default 20; 0 = unlimited)")
    args = ap.parse_args()

    missing = bin_check()
    if missing:
        print("ERROR: missing required binaries: %s" % ", ".join(missing), file=sys.stderr)
        return 3

    roots = [args.root]
    ignore = {rv.norm(x) for x in args.ignore}
    videos, _, strays = rv.collect_files(roots, ignore)
    if not videos:
        print("No video files found under %s" % args.root, file=sys.stderr)
        return 3

    # gather items (reuse scan if provided)
    scanmap = {}
    if args.scan:
        try:
            s = json.loads(Path(args.scan).read_text(encoding="utf-8"))
            for r in s.get("results", []):
                if "error" not in r:
                    scanmap[r["path"]] = r
        except Exception as e:
            print("ERROR: cannot read --scan file: %r" % e, file=sys.stderr)
            return 3

    items = []
    for v in videos:
        it = scanmap.get(v)
        if it is None or it.get("size") in (None, "N/A", ""):
            it = rv.analyze_file(Path(v), args.probe_timeout)
        if not it or "error" in it:
            continue
        items.append(it)

    plans = [plan_file(it, args.subtitle_whitelist, args.audio_whitelist, args.default_audio_language) for it in items]

    if args.only:
        needles = [x.lower() for x in args.only]
        before = len(plans)
        plans = [p for p in plans if any(n in p["path"].lower() for n in needles)]
        print("filter --only: %d -> %d files" % (before, len(plans)))
    if args.limit > 0:
        plans = plans[:args.limit]

    actionable = [p for p in plans if not p["skip"] and p["actions"]]
    skipped = [p for p in plans if p["skip"]]

    # free-space gate on actionable files
    space_problems = free_space_ok([p["path"] for p in actionable], args.min_free_gib)

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = rv.ts_tag()
    mode = "APPLY" if args.apply else "DRY-RUN"

    print("=" * 78)
    print("applyVideoMetadata  %s  %s" % (mode, rv.now_utc()))
    print("=" * 78)
    print("root:      %s" % args.root)
    print("config:    sub-wl=%r aud-wl=%r default=%r" % (args.subtitle_whitelist, args.audio_whitelist, args.default_audio_language))
    print("files:     scanned=%d  actionable=%d  skipped=%d" % (len(plans), len(actionable), len(skipped)))
    total_bytes = sum(int(p.get("size") or 0) for p in actionable)
    print("bytes:     %.1f GiB to be rewritten (each gets a .orig backup + temp)" % (total_bytes / 1024 ** 3))
    if space_problems:
        print("SPACE GATE: FAIL ->")
        for s in space_problems:
            print("   ! " + s)
        if args.apply:
            return 3
    elif actionable:
        print("SPACE GATE: ok (>=2x+%.1fGiB free on every target dir)" % args.min_free_gib)

    print("-" * 78)
    for p in sorted(actionable, key=lambda x: x["path"]):
        print("  %s" % p["path"])
        for a in p["actions"]:
            print("      - %s" % a)
    if skipped:
        print("-" * 78)
        print("SKIPPED (%d):" % len(skipped))
        for p in sorted(skipped, key=lambda x: x["path"]):
            print("  ! %s (%s)" % (p["path"], p["skip"]))
    print("-" * 78)

    if not args.apply:
        print("DRY-RUN complete: nothing was modified. Re-run with --apply to execute (%d files)." % len(actionable))
        summary = {
            "mode": "dry-run", "generated_utc": rv.now_utc(), "root": args.root,
            "config": {"sub": args.subtitle_whitelist, "aud": args.audio_whitelist, "default": args.default_audio_language},
            "actionable": len(actionable), "skipped": len(skipped), "bytes": total_bytes,
            "files": sorted(actionable, key=lambda x: x["path"]),
            "run_summary": "applyVideoMetadata dry-run | files=%d skipped=%d rc=0" % (len(actionable), len(skipped)),
        }
        (outdir / ("apply_%s_dryrun.json" % stamp)).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return 0

    # ---- APPLY ----
    max_consec = max(0, args.max_consecutive_failures)
    max_total = max(0, args.max_total_failures)
    print("APPLY: executing %d file(s)..." % len(actionable))
    print("limits:  max-consecutive-failures=%s  max-total-failures=%s (0 = unlimited)" % (
        max_consec or "unlimited", max_total or "unlimited"))
    results = []
    consec_fail = 0
    total_fail = 0
    threshold_hit = False
    for i, p in enumerate(sorted(actionable, key=lambda x: x["path"]), 1):
        print("[%d/%d] %s" % (i, len(actionable), p["path"]))
        it = next(x for x in items if x["path"] == p["path"])
        res = apply_file(p, it, args.probe_timeout, backup=args.backup)
        results.append(res)
        tag = res["status"].upper().ljust(20)
        print("    -> %s %s" % (tag, res.get("detail", "")))
        if res["status"].startswith("failed_"):
            # A per-file failure never destroys the original (apply_file restores
            # the .orig and/or cleans the temp before returning), so log-and-
            # continue is safe. We only stop when the FAILURE PATTERN suggests a
            # systemic problem (wedged mount, out of space, wrong policy) rather
            # than one bad file.
            consec_fail += 1
            total_fail += 1
            print("    failures so far: consecutive=%d total=%d" % (consec_fail, total_fail))
            if (max_consec and consec_fail >= max_consec) or (max_total and total_fail >= max_total):
                threshold_hit = True
                print("THRESHOLD REACHED: stopping early — consecutive=%s/%s total=%s/%s. "
                      "Remaining %d file(s) left untouched. Investigate before re-running (exit 2)."
                      % (consec_fail, max_consec or "*", total_fail, max_total or "*",
                         len(actionable) - i), file=sys.stderr)
                break
        else:
            consec_fail = 0  # success re-arms the consecutive counter

    rc = 0
    if threshold_hit or any(r["status"] == "failed_verify" for r in results):
        rc = 2
    elif any(r["status"].startswith(("failed_", "skipped_")) for r in results):
        rc = 1

    summary = {
        "mode": "apply", "generated_utc": rv.now_utc(), "root": args.root,
        "config": {
            "sub": args.subtitle_whitelist, "aud": args.audio_whitelist,
            "default": args.default_audio_language,
            "max_consecutive_failures": max_consec, "max_total_failures": max_total,
        },
        "threshold": {
            "hit": threshold_hit,
            "consecutive_failures": consec_fail,
            "total_failures": total_fail,
            "files_left_untouched": max(0, len(actionable) - len(results)),
        },
        "results": results, "rc": rc,
        "run_summary": "applyVideoMetadata apply | files=%d ok=%d failed=%d stopped_early=%s rc=%d" % (
            len(results),
            sum(1 for r in results if r["status"] == "ok"),
            sum(1 for r in results if r["status"] != "ok"),
            threshold_hit,
            rc,
        ),
    }
    (outdir / ("apply_%s.json" % stamp)).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("DONE: ok=%d not-ok=%d rc=%d (backups: *.orig next to each fixed file)" % (
        sum(1 for r in results if r["status"] == "ok"),
        sum(1 for r in results if r["status"] != "ok"),
        rc,
    ))
    return rc


if __name__ == "__main__":
    sys.exit(main())
