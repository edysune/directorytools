#!/usr/bin/env python3
"""Analyze previous scan JSONs to find audio/subtitle issues.

Usage:
  python3 analyzeVideoMetadata.py [path-to-scan.json]

If no argument is given, defaults to ./tools/output and picks the latest
`scan_*.json` file based on the embedded timestamp in the filename.

Produces JSON files in ./tools/output with prefixes:
  - analyze_default_audio
  - analyze_subtitle
  - analyze_unknown
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def is_english(lang: str) -> bool:
    if not lang:
        return False
    s = str(lang).lower().strip()
    if s in ("unknown", "", "none"):
        return False
    if s.startswith("en") or "eng" in s or s == "english":
        return True
    return False


def matches_any(lang: str, patterns) -> bool:
    if not lang or not patterns:
        return False
    s = str(lang).lower().strip()
    # common alias expansions
    aliases = {
        "jpn": ["jpn", "ja", "jp", "japanese", "japan"],
        "eng": ["eng", "en", "english"],
    }

    for pat in patterns:
        if not pat:
            continue
        p = str(pat).lower().strip()
        variants = [p]
        if p in aliases:
            variants.extend(aliases[p])
        # also allow plain words like 'japan' -> match 'japan' in strings
        for v in variants:
            if s == v or s.startswith(v) or v in s:
                return True
    return False


def find_latest_scan_file(output_dir: Path) -> Path:
    # Only consider files that begin with the prefix 'scan_'
    pattern = re.compile(r"scan_.*_(\d{4}-\d{2}-\d{2}T[0-9\-\.:]+)\.json$")
    candidates = []
    if not output_dir.exists() or not output_dir.is_dir():
        return None
    for p in output_dir.iterdir():
        if not p.is_file():
            continue
        # require filename prefix 'scan_'
        if not p.name.startswith("scan_"):
            continue
        m = pattern.search(p.name)
        if m:
            ts_str = m.group(1)
            try:
                date_part, time_part = ts_str.split("T", 1)
                time_part = time_part.replace("-", ":")
                iso = date_part + "T" + time_part
                dt = datetime.fromisoformat(iso)
            except Exception:
                dt = datetime.fromtimestamp(p.stat().st_mtime)
        else:
            dt = datetime.fromtimestamp(p.stat().st_mtime)
        candidates.append((dt, p))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def load_scan(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_output(prefix: str, base_scan_path: Path, data):
    out_dir = base_scan_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    # Reuse the original scan filename (which already contains a timestamp)
    base_name = base_scan_path.name
    out_name = f"{prefix}_{base_name}"
    out_path = out_dir / out_name
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return out_path


def analyze(scan_json: dict, ignore_patterns=None):
    results = scan_json.get("results") or []

    default_audio_issues = []
    subtitle_issues = []
    unknown_issues = []

    for item in results:
        # Keep full original item
        audio_streams = item.get("audio_streams") or []
        subtitle_streams = item.get("subtitle_streams") or []

        # Check default audio not English but has some English audio
        default_non_eng = False
        has_english_audio = False
        for a in audio_streams:
            lang = a.get("language")
            if a.get("default") and not is_english(lang) and not matches_any(lang, ignore_patterns):
                default_non_eng = True
            if is_english(lang):
                has_english_audio = True

        if default_non_eng and has_english_audio:
            e = dict(item)
            e["analyze_issue"] = "default_audio_non_english_but_has_english_stream"
            default_audio_issues.append(e)

        # Check subtitles that are not English
        non_eng_subs = [s for s in subtitle_streams if not is_english(s.get("language")) and not matches_any(s.get("language"), ignore_patterns)]
        if non_eng_subs:
            e = dict(item)
            e["analyze_issue"] = "subtitle_non_english_present"
            subtitle_issues.append(e)

        # Check unknown audio or subtitle
        unknown_audio = any((a.get("language") in (None, "unknown") or str(a.get("language") ).strip()=="") for a in audio_streams)
        unknown_sub = any((s.get("language") in (None, "unknown") or str(s.get("language") ).strip()=="") for s in subtitle_streams)
        if unknown_audio or unknown_sub:
            e = dict(item)
            flags = []
            if unknown_audio:
                flags.append("audio")
            if unknown_sub:
                flags.append("subtitle")
            e["analyze_issue"] = "unknown_streams"
            e["unknown_types"] = flags
            unknown_issues.append(e)

    return default_audio_issues, subtitle_issues, unknown_issues


def main():
    p = argparse.ArgumentParser(description="Analyze previous scan JSON for audio/subtitle issues")
    p.add_argument("file", nargs="?", help="Path to scan JSON file (defaults to latest in ./tools/output)")
    p.add_argument("--ignore-language", "-i", action="append", help="Language to ignore (e.g. 'jpn' or 'Japan'). Can be provided multiple times or comma-separated.")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent
    default_output_dir = repo_root / "output"

    input_path = None
    if args.file:
        input_path = Path(args.file)
        if not input_path.is_absolute():
            input_path = (Path.cwd() / input_path).resolve()
    else:
        latest = find_latest_scan_file(default_output_dir)
        if not latest:
            print("No scan JSON files found in tools/output and no file argument provided.")
            sys.exit(2)
        input_path = latest

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    scan = load_scan(input_path)

    # normalize ignore patterns: flatten and split comma-separated entries
    ignore_patterns = []
    if args.ignore_language:
        for entry in args.ignore_language:
            for part in str(entry).split(","):
                v = part.strip()
                if v:
                    ignore_patterns.append(v)

    default_audio_issues, subtitle_issues, unknown_issues = analyze(scan, ignore_patterns)

    base_scan_path = input_path

    outputs = []
    if default_audio_issues:
        payload = {
            "source": str(input_path),
            "generated_utc": datetime.utcnow().isoformat() + "Z",
            "count": len(default_audio_issues),
            "results": default_audio_issues,
        }
        out = write_output("analyze_default_audio", base_scan_path, payload)
        outputs.append(str(out))

    if subtitle_issues:
        payload = {
            "source": str(input_path),
            "generated_utc": datetime.utcnow().isoformat() + "Z",
            "count": len(subtitle_issues),
            "results": subtitle_issues,
        }
        out = write_output("analyze_subtitle", base_scan_path, payload)
        outputs.append(str(out))

    if unknown_issues:
        payload = {
            "source": str(input_path),
            "generated_utc": datetime.utcnow().isoformat() + "Z",
            "count": len(unknown_issues),
            "results": unknown_issues,
        }
        out = write_output("analyze_unknown", base_scan_path, payload)
        outputs.append(str(out))

    if outputs:
        print("Wrote output files:")
        for o in outputs:
            print(f" - {o}")
    else:
        print("No issues found; no output files generated.")


if __name__ == "__main__":
    main()
