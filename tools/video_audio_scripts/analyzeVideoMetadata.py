#!/usr/bin/env python3
"""Analyze previous scan JSONs to find audio/subtitle issues.

Usage:
  python3 analyzeVideoMetadata.py [path-to-scan.json]
  python3 analyzeVideoMetadata.py -i jpn --require-default-english

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


def analyze(scan_json: dict, subtitle_whitelist=None, default_audio_language=None, audio_whitelist=None):
    """Analyze scan results using configuration-based rules.
    
    Args:
        scan_json: Scan results dictionary
        subtitle_whitelist: List/string of languages to keep in subtitles (e.g., "English, Spanish")
        default_audio_language: Preferred default audio language (e.g., "English")
        audio_whitelist: List/string of languages to keep in audio (e.g., "English, Spanish")
    
    Returns:
        Tuple of (default_audio_issues, subtitle_issues, unknown_issues, timing_issues)
    """
    results = scan_json.get("results") or []
    
    # Parse configuration parameters
    def parse_language_list(value):
        """Parse language list from string or list format."""
        if isinstance(value, str):
            return [lang.strip() for lang in value.split(",") if lang.strip()]
        elif isinstance(value, list):
            return value
        return []
    
    subtitle_langs = parse_language_list(subtitle_whitelist) or ["English"]
    default_audio_lang = (default_audio_language.strip() if isinstance(default_audio_language, str) else "English") or "English"
    audio_langs = parse_language_list(audio_whitelist) or ["English"]

    default_audio_issues = []
    subtitle_issues = []
    unknown_issues = []
    timing_issues = []

    for item in results:
        # Keep full original item
        audio_streams = item.get("audio_streams") or []
        subtitle_streams = item.get("subtitle_streams") or []

        # ===== AUDIO ANALYSIS =====
        # Check if default audio is not in the preferred language
        default_audio_lang_lower = default_audio_lang.lower().strip()
        default_non_preferred = False
        has_preferred_audio = False
        
        for a in audio_streams:
            lang = a.get("language")
            lang_lower = str(lang).lower().strip() if lang else ""
            
            # Check if this is the default stream and not the preferred language
            if a.get("default"):
                if lang_lower not in (default_audio_lang_lower, "unknown", "", "none"):
                    # Check if preferred language is in the language name
                    if not (default_audio_lang_lower in lang_lower or lang_lower in default_audio_lang_lower):
                        default_non_preferred = True
            
            # Check if we have a stream in the preferred language
            if lang_lower in (default_audio_lang_lower, "unknown") or default_audio_lang_lower in lang_lower or lang_lower in default_audio_lang_lower:
                has_preferred_audio = True
        
        # Mark if default is not preferred but preferred audio exists
        if default_non_preferred and has_preferred_audio:
            e = dict(item)
            e["analyze_issue"] = "default_audio_not_preferred_but_has_preferred_stream"
            default_audio_issues.append(e)
        
        # Check for audio streams not in whitelist (excluding unknown)
        audio_to_remove = []
        if len(audio_streams) > 1:  # Only if there are multiple streams
            for a in audio_streams:
                lang = a.get("language")
                lang_lower = str(lang).lower().strip() if lang else ""
                
                # Skip unknown language streams
                if lang_lower in ("unknown", "", "none"):
                    continue
                
                # Check if this language is in the whitelist
                is_whitelisted = False
                for whitelist_lang in audio_langs:
                    whitelist_lower = whitelist_lang.lower().strip()
                    if lang_lower == whitelist_lower or whitelist_lower in lang_lower or lang_lower in whitelist_lower:
                        is_whitelisted = True
                        break
                
                if not is_whitelisted:
                    audio_to_remove.append(a)
        
        # Only flag for removal if we won't remove all audio streams
        if audio_to_remove and len(audio_to_remove) < len(audio_streams):
            e = dict(item)
            e["analyze_issue"] = "audio_streams_not_in_whitelist"
            e["streams_to_remove"] = audio_to_remove
            default_audio_issues.append(e)

        # ===== SUBTITLE ANALYSIS =====
        # Check subtitles that are not in the whitelist
        non_whitelisted_subs = []
        for s in subtitle_streams:
            lang = s.get("language")
            lang_lower = str(lang).lower().strip() if lang else ""
            
            # Skip unknown subtitle languages
            if lang_lower in ("unknown", "", "none"):
                continue
            
            # Check if this language is in the subtitle whitelist
            is_whitelisted = False
            for whitelist_lang in subtitle_langs:
                whitelist_lower = whitelist_lang.lower().strip()
                if lang_lower == whitelist_lower or whitelist_lower in lang_lower or lang_lower in whitelist_lower:
                    is_whitelisted = True
                    break
            
            if not is_whitelisted:
                non_whitelisted_subs.append(s)
        
        if non_whitelisted_subs:
            e = dict(item)
            e["analyze_issue"] = "subtitle_not_in_whitelist"
            e["subtitles_to_remove"] = non_whitelisted_subs
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
        
        # Check subtitle timing issues
        video_duration = item.get("duration")
        if video_duration and subtitle_streams:
            try:
                video_dur_sec = float(video_duration)
                timing_problems = []
                
                for idx, sub in enumerate(subtitle_streams):
                    sub_duration = sub.get("duration")
                    if sub_duration:
                        try:
                            sub_dur_sec = float(sub_duration)
                            
                            # Flag if subtitle extends 5+ seconds beyond video
                            if sub_dur_sec > video_dur_sec + 5.0:
                                timing_problems.append({
                                    "subtitle_index": idx,
                                    "language": sub.get("language"),
                                    "codec": sub.get("codec"),
                                    "issue": "extends_beyond_video",
                                    "subtitle_duration": sub_dur_sec,
                                    "video_duration": video_dur_sec,
                                    "difference": sub_dur_sec - video_dur_sec
                                })
                            
                            # Flag if subtitle is significantly shorter (more than 10% shorter)
                            elif sub_dur_sec < video_dur_sec * 0.9:
                                timing_problems.append({
                                    "subtitle_index": idx,
                                    "language": sub.get("language"),
                                    "codec": sub.get("codec"),
                                    "issue": "abnormally_short",
                                    "subtitle_duration": sub_dur_sec,
                                    "video_duration": video_dur_sec,
                                    "percentage": (sub_dur_sec / video_dur_sec) * 100
                                })
                        except (ValueError, TypeError):
                            pass
                
                if timing_problems:
                    e = dict(item)
                    e["analyze_issue"] = "subtitle_timing_issues"
                    e["timing_problems"] = timing_problems
                    timing_issues.append(e)
            except (ValueError, TypeError):
                pass

    return default_audio_issues, subtitle_issues, unknown_issues, timing_issues


def analyze_subtitle_whitelist(scan_json: dict, subtitle_whitelist=None):
    """Analyze subtitles against whitelist - focused analysis.
    
    Returns:
        List of items with subtitle_not_in_whitelist issues
    """
    results = scan_json.get("results") or []
    
    def parse_language_list(value):
        if isinstance(value, str):
            return [lang.strip() for lang in value.split(",") if lang.strip()]
        elif isinstance(value, list):
            return value
        return []
    
    subtitle_langs = parse_language_list(subtitle_whitelist) or ["English"]
    issues = []
    
    for item in results:
        subtitle_streams = item.get("subtitle_streams") or []
        non_whitelisted_subs = []
        
        for s in subtitle_streams:
            lang = s.get("language")
            lang_lower = str(lang).lower().strip() if lang else ""
            
            if lang_lower in ("unknown", "", "none"):
                continue
            
            is_whitelisted = False
            for whitelist_lang in subtitle_langs:
                whitelist_lower = whitelist_lang.lower().strip()
                if lang_lower == whitelist_lower or whitelist_lower in lang_lower or lang_lower in whitelist_lower:
                    is_whitelisted = True
                    break
            
            if not is_whitelisted:
                non_whitelisted_subs.append(s)
        
        if non_whitelisted_subs:
            e = dict(item)
            e["analyze_issue"] = "subtitle_not_in_whitelist"
            e["subtitles_to_remove"] = non_whitelisted_subs
            issues.append(e)
    
    return issues


def analyze_allowed_subtitle_types(scan_json: dict, allowed_subtitle_types=None):
    """Analyze subtitle formats against allowed types - focused analysis.
    
    Returns:
        List of items with incompatible_subtitle_format issues
    """
    results = scan_json.get("results") or []
    
    codec_to_format = {
        'subrip': 'SRT',
        'ass': 'ASS',
        'ssa': 'SSA',
        'webvtt': 'VTT',
        'microdvd': 'SUB',
        'subviewer': 'SBV',
        'json': 'JSON',
        'hdmv_pgs_subtitle': 'PGS',
        'dvd_subtitle': 'DVD',
        'dvdsub': 'DVD',
    }
    
    allowed_types_str = allowed_subtitle_types or "SRT"
    allowed_types = {t.strip().upper() for t in str(allowed_types_str).split(",")}
    
    issues = []
    
    for item in results:
        subtitle_streams = item.get("subtitle_streams") or []
        incompatible_subs = []
        
        for sub in subtitle_streams:
            codec = sub.get("codec") or ""
            codec_lower = codec.lower() if codec else ""
            fmt_type = codec_to_format.get(codec_lower)
            
            if fmt_type and fmt_type not in allowed_types:
                incompatible_subs.append({
                    "index": sub.get("index"),
                    "codec": codec_lower,
                    "codec_name": fmt_type,
                    "language": sub.get("language"),
                })
        
        if incompatible_subs:
            e = dict(item)
            e["analyze_issue"] = "incompatible_subtitle_format"
            e["incompatible_subtitles"] = incompatible_subs
            issues.append(e)
    
    return issues


def analyze_default_audio(scan_json: dict, default_audio_language=None):
    """Analyze default audio language - focused analysis.
    
    Returns:
        List of items with default_audio issues
    """
    results = scan_json.get("results") or []
    default_audio_lang = (default_audio_language.strip() if isinstance(default_audio_language, str) else "English") or "English"
    default_audio_lang_lower = default_audio_lang.lower().strip()
    issues = []
    
    for item in results:
        audio_streams = item.get("audio_streams") or []
        default_non_preferred = False
        has_preferred_audio = False
        
        for a in audio_streams:
            lang = a.get("language")
            lang_lower = str(lang).lower().strip() if lang else ""
            
            if a.get("default"):
                if lang_lower not in (default_audio_lang_lower, "unknown", "", "none"):
                    if not (default_audio_lang_lower in lang_lower or lang_lower in default_audio_lang_lower):
                        default_non_preferred = True
            
            if lang_lower in (default_audio_lang_lower, "unknown") or default_audio_lang_lower in lang_lower or lang_lower in default_audio_lang_lower:
                has_preferred_audio = True
        
        if default_non_preferred and has_preferred_audio:
            e = dict(item)
            e["analyze_issue"] = "default_audio_not_preferred"
            issues.append(e)
    
    return issues


def analyze_audio_whitelist(scan_json: dict, audio_whitelist=None):
    """Analyze audio streams against whitelist - focused analysis.
    
    Returns:
        List of items with audio_streams_not_in_whitelist issues
    """
    from fixVideoMetadata import language_matches_whitelist
    
    results = scan_json.get("results") or []
    
    def parse_language_list(value):
        if isinstance(value, str):
            return [lang.strip() for lang in value.split(",") if lang.strip()]
        elif isinstance(value, list):
            return value
        return []
    
    audio_langs_str = parse_language_list(audio_whitelist) or ["English"]
    audio_whitelist_str = ", ".join(audio_langs_str)  # Convert to string format for language_matches_whitelist
    issues = []
    
    for item in results:
        audio_streams = item.get("audio_streams") or []
        audio_to_remove = []
        
        for a in audio_streams:
            lang = a.get("language")
            
            if not lang or str(lang).lower().strip() in ("unknown", "", "none"):
                continue
            
            # Use the robust language matching function
            if not language_matches_whitelist(lang, audio_whitelist_str):
                audio_to_remove.append(a)
        
        # Only add to issues if there are audio streams to remove AND at least 1 would remain
        if audio_to_remove and len(audio_to_remove) < len(audio_streams):
            e = dict(item)
            e["analyze_issue"] = "audio_streams_not_in_whitelist"
            e["streams_to_remove"] = audio_to_remove
            issues.append(e)
    
    return issues


def main():
    p = argparse.ArgumentParser(description="Analyze previous scan JSON for audio/subtitle issues")
    p.add_argument("file", nargs="?", help="Path to scan JSON file (defaults to latest in ./tools/output)")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
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

    default_audio_issues, subtitle_issues, unknown_issues, timing_issues = analyze(scan)

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
    
    if timing_issues:
        payload = {
            "source": str(input_path),
            "generated_utc": datetime.utcnow().isoformat() + "Z",
            "count": len(timing_issues),
            "results": timing_issues,
        }
        out = write_output("analyze_timing", base_scan_path, payload)
        outputs.append(str(out))

    if outputs:
        print("Wrote output files:")
        for o in outputs:
            print(f" - {o}")
    else:
        print("No issues found; no output files generated.")


if __name__ == "__main__":
    main()
