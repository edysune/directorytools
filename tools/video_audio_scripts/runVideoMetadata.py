#!/usr/bin/env python3
"""runVideoMetadata.py — non-interactive video subtitle/audio metadata runner (Phase 1).

What it does (READ-ONLY, dry-run only — it never modifies media):
  1. Walks one or more media roots (skipping configured/CLI ignore dirs and
     `-original` backup copies).
  2. Probes every video with ffprobe (parallel, configurable timeout).
  3. Classifies each file against the configured language whitelists using the
     SAME decision rules as fixVideoMetadata.py (imported, not duplicated) plus
     the safety guardrails from the project strategy:
       - default-audio fix : preferred audio exists, current default is not
                             preferred, no unknown-language audio track
       - audio removal     : non-whitelisted audio exists, >=1 whitelisted
                             audio remains, no unknown-language audio track
       - subtitle removal  : non-whitelisted subs exist, >=1 whitelisted sub
                             remains, no unknown-language sub track
       - unknown tracks    : 'und'/'unknown'/''/'none' anywhere -> report only
                             (NEVER in a fix candidate; note: 'und' is handled
                             here but NOT by fixVideoMetadata.py — BUG-5)
  4. Writes reports (per-file scan JSON, machine JSON report, human markdown)
     and prints a single JSON run-summary on the LAST line of stdout.

Exit codes: 0 = ok, 1 = completed with warnings, 2 = failed/aborted,
            3 = aborted on critical (reserved for --apply phases).

Example:
  python3 runVideoMetadata.py /media \
      --subtitle-whitelist English \
      --audio-whitelist "English, Japanese, Korean" \
      --default-audio-language English \
      --ignore /media/emulator --ignore /media/youtube \
      --output-dir /work

NOTE: --apply is intentionally NOT implemented in Phase 1. Apply-mode requires
the Phase-2 hardening (BUG-1..5 fixes, free-space gate, atomic rename,
re-verification) before it may exist.
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse the project's language matcher; do NOT duplicate it (standing rule).
from fixVideoMetadata import language_matches_whitelist  # noqa: E402

JOB_NAME = "video_metadata"
MODE = "dry-run"

VIDEO_EXTS = {
    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".m4v",
    ".webm", ".ts", ".m2ts", ".mpg", ".mpeg",
}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa"}

# ISO-639-2/B 'und' (undetermined) is an unknown language too.
# fixVideoMetadata.py's skip set is ("unknown", "none") and does NOT include
# 'und' (BUG-5) — this runner treats it as unknown and refuses to fix it.
UNKNOWN_LANGS = {"", "none", "unknown", "und"}

STRAY_TEMP_RE = re.compile(r"\.(tmp|fixed)\.[A-Za-z0-9]+$")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def is_unknown_lang(lang) -> bool:
    return not lang or str(lang).lower().strip() in UNKNOWN_LANGS


def norm(p: str) -> str:
    return os.path.normpath(os.path.abspath(p))


def git_revision(script_dir: Path) -> str:
    """Best-effort repo revision for run traceability."""
    d = script_dir
    for _ in range(6):
        head = d / ".git" / "HEAD"
        if head.is_file():
            ref = head.read_text(encoding="utf-8", errors="replace").strip()
            prefix = "ref: refs/heads/"
            if ref.startswith(prefix):
                rel = ref[len(prefix):].split("/")
                branch_file = (d / ".git" / "refs" / "heads").joinpath(*rel)
                if branch_file.is_file():
                    return branch_file.read_text(encoding="utf-8").strip()[:12]
            return ref[:12]
        d = d.parent
    return "unknown"


def run_ffprobe(path: Path, timeout: float):
    """ffprobe a file; returns parsed JSON dict or None (missing/hung/bad)."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
    except FileNotFoundError:
        print("ffprobe not found. Install ffmpeg and ensure ffprobe is on PATH.", file=sys.stderr)
        sys.exit(2)
    except subprocess.TimeoutExpired:
        return None
    except subprocess.CalledProcessError as e:
        output = e.stdout or b""
    except Exception:
        return None
    else:
        output = res.stdout
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def analyze_file(path: Path, timeout: float):
    """Same result schema as scanVideoMetadata.analyze_file."""
    info = run_ffprobe(path, timeout)
    if not info:
        return {"path": str(path), "error": "no ffprobe output"}
    result = {
        "path": str(path),
        "filename": path.name,
        "format": (info.get("format") or {}).get("format_name"),
        "duration": (info.get("format") or {}).get("duration"),
        "size": (info.get("format") or {}).get("size"),
        "audio_streams": [],
        "subtitle_streams": [],
    }
    for s in info.get("streams", []):
        stype = s.get("codec_type")
        tags = s.get("tags") or {}
        lang = next((tags[k] for k in ("language", "lang", "title") if tags.get(k)), None)
        disp = s.get("disposition") or {}
        stream_info = {
            "index": s.get("index"),
            "codec": s.get("codec_name"),
            "language": lang or "unknown",
            "default": bool(disp.get("default")),
            "forced": bool(disp.get("forced")),
        }
        if stype == "audio":
            stream_info["channels"] = s.get("channels")
            result["audio_streams"].append(stream_info)
        elif stype == "subtitle":
            stream_info["duration"] = s.get("duration")
            result["subtitle_streams"].append(stream_info)
    return result


def collect_files(roots, ignore: set):
    """Walk roots; return (video_files, sidecar_files, stray_temp_files)."""
    videos, sidecars, strays = [], [], []
    for root in roots:
        root_n = norm(str(root))
        if not os.path.isdir(root_n):
            print(f"warning: root not found, skipping: {root}", file=sys.stderr)
            continue
        for dirpath, dirnames, filenames in os.walk(root_n):
            dir_n = dirpath
            # prune ignored dirs in place
            dirnames[:] = [
                d for d in dirnames
                if norm(os.path.join(dir_n, d)) not in ignore
            ]
            for name in filenames:
                full = os.path.join(dir_n, name)
                if norm(full) in ignore:
                    continue
                low = name.lower()
                suffix = os.path.splitext(low)[1]
                if suffix in VIDEO_EXTS:
                    if "-original" in name:
                        continue
                    if STRAY_TEMP_RE.search(low):
                        strays.append(full)
                    else:
                        videos.append(full)
                elif suffix in SUBTITLE_EXTS and "-original" not in name:
                    sidecars.append(full)
    return videos, sidecars, strays


def classify(item: dict, sub_wl: str, audio_wl: str, default_lang: str) -> dict:
    """Apply fixer decision rules + safety guardrails to one scanned file."""
    c = {
        "default_audio_fixable": False,
        "default_missing": False,
        "audio_removal_fixable": False,
        "subtitle_removal_fixable": False,
        "all_subs_would_be_lost": False,
        "blocked_unknown": False,
        "missing_preferred_audio": False,
        "no_audio": False,
        "timing_issues": [],
        "unknown_audio": [],
        "unknown_sub": [],
        "audio_to_remove": [],
        "subtitle_to_remove": [],
    }
    audio = item.get("audio_streams") or []
    subs = item.get("subtitle_streams") or []

    c["unknown_audio"] = [a for a in audio if is_unknown_lang(a.get("language"))]
    c["unknown_sub"] = [s for s in subs if is_unknown_lang(s.get("language"))]
    c["blocked_unknown"] = bool(c["unknown_audio"] or c["unknown_sub"])

    # ---- audio: default track ----
    defaults = [a for a in audio if a.get("default")]
    if audio:
        preferred = [a for a in audio if language_matches_whitelist(a.get("language"), default_lang)]
        if not defaults:
            c["default_missing"] = True
        elif any(not language_matches_whitelist(a.get("language"), default_lang) for a in defaults) and preferred:
            c["default_audio_fixable"] = True
        if not any(language_matches_whitelist(a.get("language"), audio_wl) for a in audio):
            c["missing_preferred_audio"] = True
    else:
        c["no_audio"] = True

    # ---- audio removal ----
    if len(audio) > 1 and not c["unknown_audio"]:
        wl_pos = [i for i, a in enumerate(audio) if language_matches_whitelist(a.get("language"), audio_wl)]
        rem_pos = [
            i for i, a in enumerate(audio)
            if not is_unknown_lang(a.get("language")) and not language_matches_whitelist(a.get("language"), audio_wl)
        ]
        if wl_pos and rem_pos:  # >=1 whitelisted remains; never remove all
            c["audio_removal_fixable"] = True
            c["audio_to_remove"] = [audio[i] for i in rem_pos]

    # ---- subtitle removal (safe subset: >=1 whitelisted sub must remain) ----
    if subs and not c["unknown_sub"]:
        wl_subs = [s for s in subs if language_matches_whitelist(s.get("language"), sub_wl)]
        rem_subs = [s for s in subs if not is_unknown_lang(s.get("language")) and not language_matches_whitelist(s.get("language"), sub_wl)]
        if wl_subs and rem_subs:
            c["subtitle_removal_fixable"] = True
            c["subtitle_to_remove"] = rem_subs
        elif rem_subs and not wl_subs and len(rem_subs) == len(subs):
            # every sub would be removed -> guardrail: never remove all subs
            c["all_subs_would_be_lost"] = True

    # ---- timing checks (mirror analyzeVideoMetadata.analyze) ----
    dur = item.get("duration")
    if dur:
        try:
            d_sec = float(dur)
            for idx, s in enumerate(subs):
                sd = s.get("duration")
                if not sd:
                    continue
                try:
                    s_sec = float(sd)
                except (ValueError, TypeError):
                    continue
                if s_sec > d_sec + 5.0:
                    c["timing_issues"].append({
                        "subtitle_index": idx,
                        "language": s.get("language"),
                        "issue": "extends_beyond_video",
                        "difference": s_sec - d_sec,
                    })
                elif s_sec < d_sec * 0.9:
                    c["timing_issues"].append({
                        "subtitle_index": idx,
                        "language": s.get("language"),
                        "issue": "abnormally_short",
                        "percentage": round((s_sec / d_sec) * 100, 1),
                    })
        except (ValueError, TypeError):
            pass

    return c


def summarize(items: list, classes: dict, sidecars: list, strays: list,
              roots: list, warnings: list, opts) -> dict:
    """Build the machine report + human-readable markdown."""
    n = len(items)
    by_dir = Counter()
    audio_langs = Counter()
    sub_langs = Counter()
    formats = Counter()
    for it in items:
        fmt = (it.get("format") or "").split(",")[0]
        if fmt:
            formats[fmt] += 1
        for a in it.get("audio_streams") or []:
            audio_langs[str(a.get("language"))] += 1
        for s in it.get("subtitle_streams") or []:
            sub_langs[str(s.get("language"))] += 1
        # directory (first two components under any root)
        p = it["path"]
        for root in roots:
            r = norm(root)
            if p.startswith(r + os.sep):
                rel = p[len(r) + 1:]
                parts = rel.split(os.sep)
                by_dir[os.path.join(*parts[:2]) if len(parts) > 2 else parts[0]] += 1
                break

    def bucket(key, files=None):
        out = []
        for it, c in zip(items, classes.values()):
            if c[key]:
                e = {"path": it["path"]}
                if key in ("default_audio_fixable",):
                    e["current_default"] = [a.get("language") for a in it.get("audio_streams", []) if a.get("default")]
                    e["preferred_available"] = [a.get("language") for a in it.get("audio_streams", []) if language_matches_whitelist(a.get("language"), opts.default_audio_language)]
                if key == "audio_removal_fixable":
                    e["remove"] = c["audio_to_remove"]
                if key == "subtitle_removal_fixable":
                    e["remove"] = c["subtitle_to_remove"]
                if key == "blocked_unknown":
                    e["unknown_audio"] = c["unknown_audio"]
                    e["unknown_sub"] = c["unknown_sub"]
                if key == "all_subs_would_be_lost":
                    e["subs"] = [s.get("language") for s in it.get("subtitle_streams", [])]
                if key == "timing_issues":
                    e["timing"] = c["timing_issues"]
                if key == "no_audio":
                    e["note"] = "file has no audio streams"
                out.append(e)
        return out

    issues = {
        "default_audio": bucket("default_audio_fixable"),
        "audio": bucket("audio_removal_fixable"),
        "subtitles": bucket("subtitle_removal_fixable"),
        "unknown": bucket("blocked_unknown"),
        "timing": bucket("timing_issues"),
        "all_subs_would_be_lost": bucket("all_subs_would_be_lost"),
        "default_missing": bucket("default_missing"),
        "no_audio": bucket("no_audio"),
        "missing_preferred_audio": bucket("missing_preferred_audio"),
    }
    counts = {
        "default_audio_fixable": len(issues["default_audio"]),
        "audio_removal_fixable": len(issues["audio"]),
        "subtitle_removal_fixable": len(issues["subtitles"]),
        "blocked_unknown": len(issues["unknown"]),
        "timing_issues": len(issues["timing"]),
        "all_subs_would_be_lost": len(issues["all_subs_would_be_lost"]),
        "default_missing": len(issues["default_missing"]),
        "no_audio": len(issues["no_audio"]),
        "missing_preferred_audio": len(issues["missing_preferred_audio"]),
    }

    report = {
        "job": JOB_NAME,
        "mode": MODE,
        "generated_utc": now_utc(),
        "revision": opts.revision,
        "roots": [norm(r) for r in roots],
        "config": {
            "subtitle_whitelist": opts.subtitle_whitelist,
            "audio_whitelist": opts.audio_whitelist,
            "default_audio_language": opts.default_audio_language,
            "ignore": sorted(opts.ignore),
        },
        "files_scanned": n,
        "sidecar_subtitle_files": sidecars,
        "stray_temp_files": strays,
        "issues": issues,
        "counts": counts,
        "language_frequencies": {
            "audio": dict(audio_langs.most_common()),
            "subtitle": dict(sub_langs.most_common()),
        },
        "formats": dict(formats.most_common()),
        "per_directory": dict(sorted(by_dir.items(), key=lambda kv: -kv[1])),
        "sidecar_count": len(sidecars),
        "warnings": warnings,
    }
    return report


def write_markdown(report: dict, path: Path):
    c = report["counts"]
    L = []
    L.append(f"# Video metadata baseline — {report['generated_utc']}")
    L.append("")
    L.append(f"- mode: **{report['mode']}** (read-only, nothing modified)")
    L.append(f"- revision: {report['revision']}")
    L.append(f"- roots: {', '.join('`%s`' % r for r in report['roots'])}")
    L.append(f"- config: sub={report['config']['subtitle_whitelist']!r} "
             f"audio={report['config']['audio_whitelist']!r} "
             f"default={report['config']['default_audio_language']!r}")
    L.append(f"- files scanned: **{report['files_scanned']}** | sidecars: {report['sidecar_count']} | stray temp: {len(report['stray_temp_files'])}")
    L.append("")
    L.append("## Issues (fix candidates, dry-run)")
    L.append("")
    L.append("| category | files |")
    L.append("|---|---:|")
    L.append(f"| default audio needs re-order | {c['default_audio_fixable']} |")
    L.append(f"| non-whitelisted audio would be removed | {c['audio_removal_fixable']} |")
    L.append(f"| non-whitelisted subs would be removed | {c['subtitle_removal_fixable']} |")
    L.append(f"| blocked: unknown-language track (report only) | {c['blocked_unknown']} |")
    L.append(f"| subtitle timing issues | {c['timing_issues']} |")
    L.append(f"| **would lose ALL subs — needs your call (RISK-1)** | {c['all_subs_would_be_lost']} |")
    L.append(f"| no default audio track | {c['default_missing']} |")
    L.append(f"| no audio streams at all | {c['no_audio']} |")
    L.append(f"| no whitelisted audio present (unfixable) | {c['missing_preferred_audio']} |")
    L.append("")
    L.append("## Language frequencies")
    L.append("")
    L.append("- audio: " + (", ".join(f"{k} ×{v}" for k, v in report["language_frequencies"]["audio"].items()) or "none"))
    L.append("- subtitle: " + (", ".join(f"{k} ×{v}" for k, v in report["language_frequencies"]["subtitle"].items()) or "none"))
    L.append("")
    L.append("## Per directory (top)")
    L.append("")
    L.append("| directory | files |")
    L.append("|---|---:|")
    for d, n_ in list(report["per_directory"].items())[:40]:
        L.append(f"| {d} | {n_} |")
    L.append("")
    if report["issues"]["all_subs_would_be_lost"]:
        L.append("## RISK-1: files where removing non-whitelisted subs would remove ALL subs")
        L.append("")
        for e in report["issues"]["all_subs_would_be_lost"][:200]:
            L.append(f"- `{e['path']}` — subs: {', '.join(e['subs'])}")
    if report["issues"]["unknown"]:
        L.append("")
        L.append("## Unknown-language streams (report only; includes ISO 'und' — BUG-5)")
        L.append("")
        for e in report["issues"]["unknown"][:200]:
            ua = ", ".join(str(a.get("language")) for a in e["unknown_audio"])
            us = ", ".join(str(s.get("language")) for s in e["unknown_sub"])
            L.append(f"- `{e['path']}` — audio: {ua or '-'} | subs: {us or '-'}")
    if report["stray_temp_files"]:
        L.append("")
        L.append("## Stray temp files found (possible crashed prior fix run)")
        L.append("")
        for s in report["stray_temp_files"]:
            L.append(f"- `{s}`")
    if report["warnings"]:
        L.append("")
        L.append("## Warnings")
        L.append("")
        for w in report["warnings"]:
            L.append(f"- {w}")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Non-interactive video metadata baseline (dry-run only)")
    ap.add_argument("paths", nargs="+", help="Media root(s): file or directory")
    ap.add_argument("--config", help="JSON config (gui_config.json-compatible keys; CLI flags win)")
    ap.add_argument("--subtitle-whitelist", default=None)
    ap.add_argument("--audio-whitelist", default=None)
    ap.add_argument("--default-audio-language", default=None)
    ap.add_argument("--ignore", action="append", default=[], help="Path to ignore (repeatable)")
    ap.add_argument("--output-dir", default="output")
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--ffprobe-timeout", type=float, default=60.0)
    opts = ap.parse_args()

    # config file (optional); CLI overrides win
    cfg = {}
    if opts.config:
        with open(opts.config, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    opts.subtitle_whitelist = opts.subtitle_whitelist or cfg.get("subtitle_whitelist") or "English"
    opts.audio_whitelist = opts.audio_whitelist or cfg.get("audio_whitelist") or "English"
    opts.default_audio_language = opts.default_audio_language or cfg.get("default_audio_language") or "English"
    if cfg.get("ignore_directories"):
        opts.ignore += [p for p in str(cfg["ignore_directories"]).splitlines() if p.strip()]
    ignore = set()
    for ig in opts.ignore:
        cands = {norm(ig)}
        # remap configured host paths (e.g. /mnt/A18002/emulator) onto the
        # mounted roots (e.g. /media/emulator) so gui_config.json works in-docker
        suffix = ig.rstrip("/").split("/")
        root_parts = [
            norm(r).rstrip("/").split("/") for r in opts.paths
            if len(norm(r).rstrip("/").split("/")) >= 2
        ]
        for rs in root_parts:
            if suffix and suffix[-1] == rs[-1]:
                # same drive token -> this is the same drive mounted elsewhere
                cands.add("/".join(rs[:-1] + [suffix[-1]]))
        ignore |= cands
    opts.ignore = sorted(ignore)
    opts.revision = git_revision(Path(__file__).resolve().parent)

    start = time.time()
    warnings = []

    videos, sidecars, strays = collect_files(opts.paths, ignore)
    if strays:
        warnings.append(f"{len(strays)} stray temp file(s) excluded (possible crashed prior fix run)")
    print(f"collected {len(videos)} videos, {len(sidecars)} sidecars, "
          f"{len(strays)} stray temp files; scanning with {opts.jobs} workers...", file=sys.stderr)

    results, failures = [], 0
    if videos:
        with concurrent.futures.ThreadPoolExecutor(max_workers=opts.jobs) as ex:
            futs = {ex.submit(analyze_file, Path(v), opts.ffprobe_timeout): v for v in videos}
            done = 0
            for fut in concurrent.futures.as_completed(futs):
                res = fut.result()
                if "error" in res:
                    failures += 1
                results.append(res)
                done += 1
                if done % 400 == 0:
                    print(f"  scanned {done}/{len(videos)} ({failures} probe failures)", file=sys.stderr)

    results.sort(key=lambda r: r["path"])
    classes = {}
    for it in results:
        if "error" in it:
            continue
        classes[it["path"]] = classify(it, opts.subtitle_whitelist, opts.audio_whitelist, opts.default_audio_language)

    ok_items = [it for it in results if "error" not in it]
    if failures:
        warnings.append(f"{failures}/{len(videos)} files failed ffprobe (timeout or unreadable) — excluded from metrics")

    report = summarize(ok_items, classes, sidecars, strays, opts.paths, warnings, opts)
    report["probe_failures"] = failures

    outdir = Path(opts.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    tag = ts_tag()
    scan_out = outdir / f"baseline_{tag}_scan.json"
    scan_out.write_text(json.dumps({
        "scanned_paths": [norm(r) for r in opts.paths],
        "generated_utc": now_utc(),
        "file_count": len(results),
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    rep_out = outdir / f"baseline_{tag}_report.json"
    rep_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_out = outdir / f"baseline_{tag}_report.md"
    write_markdown(report, md_out)

    status = "ok"
    if failures or report["issues"]["all_subs_would_be_lost"] or not ok_items:
        status = "partial" if ok_items else "failed"

    summary = {
        "job": JOB_NAME,
        "mode": MODE,
        "status": status,
        "revision": opts.revision,
        "scanned": len(ok_items),
        "issues": {
            "default_audio": report["counts"]["default_audio_fixable"],
            "audio": report["counts"]["audio_removal_fixable"],
            "subtitles": report["counts"]["subtitle_removal_fixable"],
            "unknown": report["counts"]["blocked_unknown"],
            "timing": report["counts"]["timing_issues"],
        },
        "would_lose_all_subs": report["counts"]["all_subs_would_be_lost"],
        "applied": 0,
        "failed": failures,
        "skipped": 0,
        "warnings": warnings,
        "critical": [],
        "data_loss_risk": False,
        "outputs": {"scan": str(scan_out), "report": str(rep_out), "markdown": str(md_out)},
        "duration_s": round(time.time() - start, 1),
    }
    # last line of stdout = the run-summary JSON contract
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if status == "ok" else (1 if status == "partial" else 2)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print(json.dumps({"job": JOB_NAME, "mode": MODE, "status": "aborted", "critical": ["interrupted"], "data_loss_risk": False}))
        sys.exit(3)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(json.dumps({"job": JOB_NAME, "mode": MODE, "status": "failed", "critical": [str(e)], "data_loss_risk": False}))
        sys.exit(2)
