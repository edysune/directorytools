#!/usr/bin/env python3
"""Interactive fixes for analyzed video metadata issues.

Runs three flows against the latest analyze JSONs found in `tools/output`:
- analyze_default_audio -> set English default audio (attempt)
- analyze_subtitle    -> remove non-English subtitles (attempt)
- analyze_unknown     -> try to identify unknown audio languages (heuristic)

This script prompts for each item with `Y`/`N`/`Q` (quit).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"


def find_latest_analyze(prefix: str):
    pattern = f"analyze*{prefix}*"
    candidates = list(OUTPUT_DIR.glob(pattern + ".json"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def is_english(lang: str) -> bool:
    if not lang:
        return False
    s = str(lang).lower().strip()
    if s in ("unknown", "", "none"):
        return False
    if s.startswith("en") or "eng" in s or s == "english":
        return True
    return False


def run_reanalyze(scan_source: str, require_default_english=False):
    # call analyzeVideoMetadata.py to refresh analyze outputs
    script = REPO_ROOT / "video_audio_scripts" / "analyzeVideoMetadata.py"
    cmd = [sys.executable, str(script), scan_source]
    if require_default_english:
        cmd.append("--require-default-english")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Re-analyze failed: {e}")


def prompt_choice(prompt: str):
    while True:
        v = input(prompt + " [Y/N/Q]: ").strip().upper()
        if v in ("Y", "N", "Q"):
            return v


def backup_file_before_fix(path: str):
    """Create a backup copy with -original suffix before modifying."""
    file_path = Path(path)
    name_parts = file_path.name.rsplit(".", 1)
    if len(name_parts) == 2:
        title, ext = name_parts
        backup_name = f"{title}-original.{ext}"
    else:
        backup_name = f"{file_path.name}-original"
    backup_path = file_path.parent / backup_name
    
    if not backup_path.exists():
        shutil.copy2(path, str(backup_path))
        print(f"Created backup: {backup_path}")


def attempt_set_default_audio(item: dict):
    path = item.get("path")
    fmt = item.get("format", "")
    audio_streams = item.get("audio_streams") or []
    eng_stream = None
    for a in audio_streams:
        if is_english(a.get("language")):
            eng_stream = a
            break

    if not eng_stream:
        print(f"No English audio streams for {path}; skipping.")
        return False

    if eng_stream.get("default"):
        print(f"English audio already default for {path}; skipping.")
        return False

    # Create backup before making changes
    backup_file_before_fix(path)

    # Attempt container-specific commands
    if "matroska" in fmt:
        # use mkvpropedit to set default flags
        cmds = []
        # set chosen stream default=1
        idx = eng_stream.get("index")
        cmds.append(["mkvpropedit", path, "--edit", f"track:a{idx}", "--set", "flag-default=1"]) 
        # clear other audio defaults
        for a in audio_streams:
            if a.get("index") != idx:
                cmds.append(["mkvpropedit", path, "--edit", f"track:a{a.get('index')}", "--set", "flag-default=0"]) 
        for c in cmds:
            try:
                subprocess.run(c, check=True)
            except Exception as e:
                print(f"Failed running: {' '.join(c)} -> {e}")
                return False
        print(f"Set English audio as default for {path}")
        return True

    # For other containers, use ffmpeg to rewrite dispositions (copy)
    if any(x in fmt for x in ("mp4", "mov")):
        # find audio stream zero-based order for ffmpeg mapping
        # we'll set disposition for the chosen audio by copying file and adjusting dispositions
        # build ffmpeg metadata args
        try:
            tmp = str(Path(path).with_suffix(Path(path).suffix + ".fixed"))
            # build -disposition:s or -disposition:a entries; the stream ordering is not reliable
            # so use a simple ffmpeg copy and set metadata for first audio found index 0
            cmd = ["ffmpeg", "-y", "-i", path, "-c", "copy"]
            # set language metadata for chosen audio stream if desired
            # set default disposition: set chosen audio to default
            cmd += ["-disposition:a:0", "default"]
            cmd += [tmp]
            subprocess.run(cmd, check=True)
            shutil.move(tmp, path)
            print(f"Rewrote container to set default audio for {path}")
            return True
        except Exception as e:
            print(f"Failed to set default audio via ffmpeg: {e}")
            return False

    print(f"Unsupported container for setting default audio: {fmt} for {path}")
    return False


def attempt_remove_non_english_subs(item: dict):
    path = item.get("path")
    fmt = item.get("format", "")
    subs = item.get("subtitle_streams") or []
    if not subs:
        print(f"No subtitles for {path}; skipping.")
        return

    # if any subtitle has unknown language, skip
    for s in subs:
        lang = s.get("language")
        if not lang or str(lang).lower() in ("unknown", "none"):
            print(f"Subtitle with unknown language in {path}; skipping removal for this file.")
            return

    # Create backup before making changes
    backup_file_before_fix(path)

    # identify non-english subtitle positions (0-based among subtitle streams)
    remove_positions = [i for i, s in enumerate(subs) if not is_english(s.get("language"))]
    if not remove_positions:
        print(f"No non-English subtitles to remove for {path}.")
        return

    # use ffmpeg to copy and drop these subtitle streams
    try:
        tmp = str(Path(path).with_suffix(Path(path).suffix + ".nosubs"))
        cmd = ["ffmpeg", "-y", "-i", path, "-map", "0"]
        for pos in remove_positions:
            cmd += ["-map", f"-0:s:{pos}"]
        cmd += ["-c", "copy", tmp]
        subprocess.run(cmd, check=True)
        shutil.move(tmp, path)
        print(f"Removed non-English subtitles from {path}")
    except Exception as e:
        print(f"Failed to remove subtitles via ffmpeg: {e}")


def attempt_identify_unknown(item: dict):
    path = item.get("path")
    audio_streams = item.get("audio_streams") or []
    # heuristic: try to infer from filename
    fname = os.path.basename(path).lower()
    guesses = ["eng", "jpn", "spa", "fra", "ger"]
    for g in guesses:
        if g in fname:
            print(f"Guessed language '{g}' from filename for {path}")
            choose = prompt_choice(f"Apply language '{g}' to unknown audio for {path}?")
            if choose == "Y":
                # Create backup before making changes
                backup_file_before_fix(path)
                # set metadata using mkvpropedit or ffmpeg
                fmt = item.get("format", "")
                if "matroska" in fmt:
                    for a in audio_streams:
                        if not a.get("language") or str(a.get("language")).lower() in ("unknown", ""):
                            idx = a.get("index")
                            try:
                                subprocess.run(["mkvpropedit", path, "--edit", f"track:a{idx}", "--set", f"language={g}"], check=True)
                                print(f"Set language={g} on track a{idx} for {path}")
                            except Exception as e:
                                print(f"Failed to set language: {e}")
                else:
                    # fallback: ffmpeg copy with metadata set for first audio stream
                    try:
                        tmp = str(Path(path).with_suffix(Path(path).suffix + ".langset"))
                        cmd = ["ffmpeg", "-y", "-i", path, "-c", "copy", "-metadata:s:a:0", f"language={g}", tmp]
                        subprocess.run(cmd, check=True)
                        shutil.move(tmp, path)
                        print(f"Set language metadata to {g} for {path}")
                    except Exception as e:
                        print(f"Failed to set language via ffmpeg: {e}")
                return

    print(f"Unable to heuristically identify unknown audio for {path}. Consider manual inspection.")


def process_flow(prefix: str, handler, reanalyze_flag=False, overall_prompt=None):
    path = find_latest_analyze(prefix)
    if not path:
        print(f"No analyze files found for prefix '{prefix}'.")
        return
    data = load_json(path)
    results = data.get("results") or []
    if not results:
        print(f"No results in {path}")
        return

    if overall_prompt:
        v = prompt_choice(overall_prompt)
        if v == "N":
            print("Skipping this flow.")
            return
        if v == "Q":
            print("Quitting.")
            sys.exit(0)

    for item in results:
        print("\nFile:", item.get("path"))
        choice = prompt_choice("Apply change for this file?")
        if choice == "Q":
            print("Quitting.")
            return
        if choice == "N":
            continue
        # re-analyze before making changes if requested
        src = data.get("source")
        if reanalyze_flag and src:
            run_reanalyze(src, require_default_english=(prefix == "default_audio"))
        handler(item)


def main():
    print("fixVideoMetadata: interactive metadata fixer\n")
    # 1: default audio
    process_flow("default_audio", attempt_set_default_audio, reanalyze_flag=True, overall_prompt="Run 'set english default audio script'? ")
    # 2: subtitles
    process_flow("subtitle", attempt_remove_non_english_subs, reanalyze_flag=True, overall_prompt="Run 'removing subtitle script'? ")
    # 3: unknown
    process_flow("unknown", attempt_identify_unknown, reanalyze_flag=True, overall_prompt="Run 'set unknown audio script'? ")


if __name__ == "__main__":
    main()
