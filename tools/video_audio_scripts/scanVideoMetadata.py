#!/usr/bin/env python3
"""Scan video files for audio/subtitle metadata using ffprobe.

Works on Windows and Linux (requires ffprobe on PATH).

Usage: python3 scanVideoMetadata.py <path-to-file-or-directory>
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VIDEO_EXTS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".wmv",
    ".flv",
    ".m4v",
    ".webm",
    ".ts",
    ".m2ts",
    ".mpg",
    ".mpeg",
}

SUBTITLE_EXTS = {
    ".srt",
    ".ass",
    ".ssa",
}


def is_video_file(p: Path):
    return p.suffix.lower() in VIDEO_EXTS


def is_subtitle_file(p: Path):
    return p.suffix.lower() in SUBTITLE_EXTS


def should_skip_file(p: Path):
    """Skip files with -original in the filename (backup copies)."""
    return "-original" in p.name


def run_ffprobe(path: Path):
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
    except FileNotFoundError:
        print("ffprobe not found. Please install ffmpeg/ffprobe and ensure it's on PATH.")
        sys.exit(2)
    except subprocess.TimeoutExpired:
        # ffprobe hung on this file, return None to skip it
        return None
    except subprocess.CalledProcessError as e:
        # ffprobe may return non-zero for some files; still try to parse stdout
        output = e.stdout or e.stderr
    except Exception as e:
        # Catch any other exceptions (including segfaults caught as OSError)
        print(f"Warning: ffprobe error on {path.name}: {e}")
        return None
    else:
        output = res.stdout

    if not output:
        return None

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def detect_language_from_tags(tags: dict):
    if not tags:
        return None
    # common tag names
    for key in ("language", "lang", "title"):
        v = tags.get(key)
        if v:
            return v
    return None


def analyze_file(path: Path):
    info = run_ffprobe(path)
    if not info:
        return {"path": str(path), "error": "no ffprobe output"}

    result = {
        "path": str(path),
        "filename": path.name,
        "format": info.get("format", {}).get("format_name"),
        "duration": info.get("format", {}).get("duration"),
        "size": info.get("format", {}).get("size"),
        "audio_streams": [],
        "subtitle_streams": [],
    }

    streams = info.get("streams", [])
    for s in streams:
        stype = s.get("codec_type")
        tags = s.get("tags") or {}
        lang = detect_language_from_tags(tags) or "unknown"
        disposition = s.get("disposition") or {}
        is_default = bool(disposition.get("default"))
        is_forced = bool(disposition.get("forced"))

        stream_info = {
            "index": s.get("index"),
            "codec": s.get("codec_name"),
            "language": lang,
            "title": tags.get("title"),
            "default": is_default,
            "forced": is_forced,
        }

        if stype == "audio":
            stream_info.update({
                "channels": s.get("channels"),
                "sample_rate": s.get("sample_rate"),
            })
            result["audio_streams"].append(stream_info)
        elif stype == "subtitle":
            # subtitles often have codec_name like 'subrip' etc.
            # Add duration for timing analysis
            stream_info["duration"] = s.get("duration")
            result["subtitle_streams"].append(stream_info)

    return result


def analyze_subtitle_file(path: Path):
    """Analyze a standalone subtitle file (SRT, ASS, SSA).
    
    Args:
        path: Path to subtitle file
    
    Returns:
        Dictionary with subtitle file information
    """
    return {
        "path": str(path),
        "filename": path.name,
        "format": path.suffix.lower().lstrip('.'),
        "size": path.stat().st_size if path.exists() else None,
    }


def walk_and_scan(start_path: Path, progress_callback=None, ignore_dirs=None, log_callback=None):
    """Scan video files in a directory or file.
    
    Args:
        start_path: Path to scan (file or directory)
        progress_callback: Optional callback function(current_count, file_path) called for each file scanned
        ignore_dirs: Optional set of absolute directory paths to ignore during scanning
        log_callback: Optional callback function(message) for logging
    
    Returns:
        List of scan results for video files
    """
    results = []
    current_count = 0
    ignore_dirs = ignore_dirs or set()
    
    if start_path.is_file():
        if is_video_file(start_path) and not should_skip_file(start_path):
            current_count += 1
            if progress_callback:
                progress_callback(current_count, start_path)
            results.append(analyze_file(start_path))
        elif is_video_file(start_path) and should_skip_file(start_path):
            print(f"Skipping backup file: {start_path}")
        else:
            print(f"Skipping non-video file: {start_path}")
        return results

    for root, dirs, files in os.walk(start_path):
        # Log and filter out ignored directories in-place to prevent os.walk from descending into them
        ignored_in_current = []
        for d in dirs[:]:
            full_path = str(Path(root) / d)
            if full_path in ignore_dirs:
                ignored_in_current.append(d)
        
        if ignored_in_current:
            for ignored_dir in ignored_in_current:
                if log_callback:
                    log_callback(f"Ignoring directory: {Path(root) / ignored_dir}")
        
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if str(Path(root) / d) not in ignore_dirs]
        
        for fname in files:
            p = Path(root) / fname
            if is_video_file(p):
                if should_skip_file(p):
                    print(f"Skipping backup file: {p}")
                else:
                    current_count += 1
                    if progress_callback:
                        progress_callback(current_count, p)
                    results.append(analyze_file(p))

    return results


def walk_and_scan_subtitles(start_path: Path, progress_callback=None, ignore_dirs=None, log_callback=None):
    """Scan subtitle files in a directory or file.
    
    Args:
        start_path: Path to scan (file or directory)
        progress_callback: Optional callback function(current_count, file_path) called for each file scanned
        ignore_dirs: Optional set of absolute directory paths to ignore during scanning
        log_callback: Optional callback function(message) for logging
    
    Returns:
        List of scan results for subtitle files
    """
    results = []
    current_count = 0
    ignore_dirs = ignore_dirs or set()
    
    if start_path.is_file():
        if is_subtitle_file(start_path):
            current_count += 1
            if progress_callback:
                progress_callback(current_count, start_path)
            results.append(analyze_subtitle_file(start_path))
        else:
            print(f"Skipping non-subtitle file: {start_path}")
        return results

    for root, dirs, files in os.walk(start_path):
        # Log and filter out ignored directories in-place to prevent os.walk from descending into them
        ignored_in_current = []
        for d in dirs[:]:
            full_path = str(Path(root) / d)
            if full_path in ignore_dirs:
                ignored_in_current.append(d)
        
        if ignored_in_current:
            for ignored_dir in ignored_in_current:
                if log_callback:
                    log_callback(f"Ignoring directory: {Path(root) / ignored_dir}")
        
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if str(Path(root) / d) not in ignore_dirs]
        
        for fname in files:
            p = Path(root) / fname
            if is_subtitle_file(p):
                current_count += 1
                if progress_callback:
                    progress_callback(current_count, p)
                results.append(analyze_subtitle_file(p))

    return results


def print_results(results):
    for r in results:
        if "error" in r:
            print(f"{r.get('path')}: ERROR: {r.get('error')}")
            continue

        print("---")
        print(f"File: {r.get('filename')}")
        print(f"Path: {r.get('path')}")
        if r.get("format"):
            print(f"Format: {r.get('format')}")
        if r.get("duration"):
            print(f"Duration: {r.get('duration')} sec")
        if r.get("size"):
            print(f"Size: {r.get('size')} bytes")

        if r.get("audio_streams"):
            print("Audio streams:")
            for a in r["audio_streams"]:
                print(
                    f" - idx={a.get('index')} codec={a.get('codec')} lang={a.get('language')} default={a.get('default')} forced={a.get('forced')} channels={a.get('channels')}"
                )
        else:
            print("Audio streams: none")

        if r.get("subtitle_streams"):
            print("Subtitle streams:")
            for s in r["subtitle_streams"]:
                print(
                    f" - idx={s.get('index')} codec={s.get('codec')} lang={s.get('language')} default={s.get('default')} forced={s.get('forced')} title={s.get('title')}"
                )
        else:
            print("Subtitle streams: none")


def main():
    p = argparse.ArgumentParser(description="Scan video files for audio and subtitle metadata")
    p.add_argument("path", help="File or directory to scan")
    args = p.parse_args()

    start = Path(args.path)
    if not start.exists():
        print(f"Path does not exist: {start}")
        sys.exit(1)

    results = walk_and_scan(start)

    # Save structured JSON to ./output
    output_dir = Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat().replace(":", "-")
    out_name = f"scan_{start.name}_{timestamp}.json"
    out_path = output_dir / out_name

    payload = {
        "scanned_path": str(start),
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "file_count": len(results),
        "results": results,
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"Saved results to: {out_path}")
    print(f"Scanned files: {len(results)}")


if __name__ == "__main__":
    main()
