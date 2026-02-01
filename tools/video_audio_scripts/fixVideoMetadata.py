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


def language_matches_whitelist(lang: str, whitelist: str) -> bool:
    """Check if a language matches any language in the whitelist.
    
    Args:
        lang: The language code/name to check (e.g., "en", "English", "eng", "und")
        whitelist: Comma-separated list of preferred languages (e.g., "English, Japanese")
    
    Returns:
        True if lang is in the whitelist, False otherwise
    """
    if not lang or not whitelist:
        return False
    
    lang_lower = str(lang).lower().strip()
    
    # Parse the whitelist
    preferred_langs = [l.lower().strip() for l in str(whitelist).split(",")]
    
    # ISO 639-2 to ISO 639-1 common mappings
    iso_639_2_to_1 = {
        "eng": "en", "fra": "fr", "fre": "fr", "deu": "de", "ger": "de",
        "ita": "it", "spa": "es", "por": "pt", "rus": "ru", "jpn": "ja",
        "kor": "ko", "chi": "zh", "ces": "cs", "dan": "da", "nld": "nl",
        "fin": "fi", "heb": "he", "hul": "hu", "pol": "pl", "swe": "sv",
        "tur": "tr", "ara": "ar", "cat": "ca", "ell": "el", "hye": "hy",
        "vie": "vi", "tha": "th", "ron": "ro", "srp": "sr", "ukr": "uk",
        "hind": "hi", "ben": "bn", "tam": "ta", "tel": "te", "mar": "mr",
        "guj": "gu", "kan": "kn", "mal": "ml", "kok": "kok"
    }
    
    # Known language names and their 2-letter codes
    language_name_to_code = {
        "english": "en", "spanish": "es", "castilian": "es",
        "french": "fr", "german": "de", "italian": "it", 
        "portuguese": "pt", "russian": "ru", "japanese": "ja",
        "korean": "ko", "chinese": "zh", "czech": "cs",
        "danish": "da", "dutch": "nl", "finnish": "fi",
        "hebrew": "he", "hungarian": "hu", "polish": "pl",
        "swedish": "sv", "turkish": "tr", "arabic": "ar",
        "catalan": "ca", "greek": "el", "armenian": "hy",
        "vietnamese": "vi", "thai": "th", "romanian": "ro",
        "serbian": "sr", "ukrainian": "uk", "hindi": "hi",
        "bengali": "bn", "tamil": "ta", "telugu": "te",
        "marathi": "mr", "gujarati": "gu", "kannada": "kn",
        "malayalam": "ml"
    }
    
    # Check if any preferred language matches this language
    for pref in preferred_langs:
        if pref in ("unknown", "", "none"):
            continue
        # Check exact match
        if lang_lower == pref:
            return True
        
        # Get language codes for both lang and pref for comparison
        lang_code = iso_639_2_to_1.get(lang_lower) or language_name_to_code.get(lang_lower)
        pref_code = iso_639_2_to_1.get(pref) or language_name_to_code.get(pref)
        
        # If we found codes for both, compare them
        if lang_code and pref_code and lang_code == pref_code:
            return True
        
        # Check if language name starts with a code (e.g., "ja" in "japanese")
        if len(lang_lower) == 2 and pref.startswith(lang_lower):
            return True
        if len(pref) == 2 and lang_lower.startswith(pref):
            return True
        
        # Check if both are language names and match approximately
        if len(lang_lower) > 2 and len(pref) > 2:
            if lang_lower.startswith(pref[:3]) or pref.startswith(lang_lower[:3]):
                return True
    
    return False


def run_reanalyze(scan_source: str):
    # call analyzeVideoMetadata.py to refresh analyze outputs
    script = REPO_ROOT / "video_audio_scripts" / "analyzeVideoMetadata.py"
    cmd = [sys.executable, str(script), scan_source]
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


def attempt_set_default_audio(item: dict, default_audio_language: str = "English"):
    path = item.get("path")
    fmt = item.get("format", "")
    audio_streams = item.get("audio_streams") or []
    preferred_stream = None
    for a in audio_streams:
        if language_matches_whitelist(a.get("language"), default_audio_language):
            preferred_stream = a
            break

    if not preferred_stream:
        print(f"No {default_audio_language} audio streams for {path}; skipping.")
        return False

    if preferred_stream.get("default"):
        print(f"{default_audio_language} audio already default for {path}; skipping.")
        return False

    # Create backup before making changes
    backup_file_before_fix(path)

    # Attempt container-specific commands
    if "matroska" in fmt:
        # use mkvpropedit to set default flags
        cmds = []
        # set chosen stream default=1
        idx = preferred_stream.get("index")
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
        print(f"Set {default_audio_language} audio as default for {path}")
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


def attempt_remove_non_whitelisted_subs(item: dict, subtitle_whitelist: str = "English"):
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

    # identify non-whitelisted subtitle positions (0-based among subtitle streams)
    remove_positions = [i for i, s in enumerate(subs) if not language_matches_whitelist(s.get("language"), subtitle_whitelist)]
    if not remove_positions:
        print(f"No non-whitelisted subtitles to remove for {path}.")
        return

    # use ffmpeg to copy and drop these subtitle streams
    try:
        tmp = str(Path(path).with_suffix(Path(path).suffix + ".tmp"))
        cmd = ["ffmpeg", "-y", "-i", path, "-map", "0"]
        for pos in remove_positions:
            cmd += ["-map", f"-0:s:{pos}"]
        cmd += ["-c", "copy"]
        
        # Specify output format based on container type
        if "matroska" in fmt:
            cmd += ["-f", "matroska"]
        elif any(x in fmt for x in ("mp4", "mov")):
            cmd += ["-f", "mp4"]
        
        cmd += [tmp]
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.move(tmp, path)
        print(f"Removed non-whitelisted subtitles from {path}")
    except Exception as e:
        print(f"Failed to remove subtitles via ffmpeg: {e}")


def attempt_remove_non_whitelisted_audio(item: dict, audio_whitelist: str = "English"):
    """Remove audio streams not in the whitelist.
    
    Safety rules:
    1. Skip if no audio streams exist
    2. Skip if applying whitelist would remove ALL audio streams (never leave files without audio)
    3. Only remove if at least 1 audio stream matches whitelist
    """
    path = item.get("path")
    fmt = item.get("format", "")
    audio_streams = item.get("audio_streams") or []
    
    # Rule 1: Check if audio streams exist
    if not audio_streams:
        print(f"No audio streams for {path}; skipping audio whitelist removal.")
        return

    # Rule 2: Check if any audio has unknown language
    for a in audio_streams:
        lang = a.get("language")
        if not lang or str(lang).lower() in ("unknown", "none"):
            print(f"Audio stream with unknown language in {path}; skipping removal for safety.")
            return

    # Determine which audio streams would remain (match whitelist)
    whitelisted_positions = [i for i, a in enumerate(audio_streams) if language_matches_whitelist(a.get("language"), audio_whitelist)]
    
    # Rule 2: Safety check - never remove all audio streams
    if not whitelisted_positions:
        print(f"Applying audio whitelist would remove ALL audio streams from {path}; skipping to preserve audio.")
        return

    # Rule 3: Determine which streams to remove
    remove_positions = [i for i in range(len(audio_streams)) if i not in whitelisted_positions]
    
    if not remove_positions:
        print(f"No non-whitelisted audio streams to remove for {path}.")
        return

    # Create backup before making changes
    backup_file_before_fix(path)

    # Use ffmpeg to copy and drop these audio streams
    try:
        tmp = str(Path(path).with_suffix(Path(path).suffix + ".tmp"))
        cmd = ["ffmpeg", "-y", "-i", path, "-map", "0"]
        for pos in remove_positions:
            cmd += ["-map", f"-0:a:{pos}"]
        cmd += ["-c", "copy"]
        
        # Specify output format based on container type
        if "matroska" in fmt:
            cmd += ["-f", "matroska"]
        elif any(x in fmt for x in ("mp4", "mov")):
            cmd += ["-f", "mp4"]
        
        cmd += [tmp]
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.move(tmp, path)
        print(f"Removed non-whitelisted audio streams from {path}")
    except Exception as e:
        print(f"Failed to remove audio streams via ffmpeg: {e}")



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


def process_flow(prefix: str, handler, handler_config: dict = None, overall_prompt=None):
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
        if src:
            run_reanalyze(src)
        # Call handler with config parameters if provided
        if handler_config:
            handler(item, **handler_config)
        else:
            handler(item)


def main():
    print("fixVideoMetadata: interactive metadata fixer\n")
    # Use default config values; in the future these could be loaded from config file
    default_audio_language = "English"
    subtitle_whitelist = "English"
    
    # 1: default audio
    process_flow(
        "default_audio", 
        attempt_set_default_audio, 
        handler_config={"default_audio_language": default_audio_language},
        overall_prompt="Run 'set default audio script'? "
    )
    # 2: subtitles
    process_flow(
        "subtitle", 
        attempt_remove_non_whitelisted_subs, 
        handler_config={"subtitle_whitelist": subtitle_whitelist},
        overall_prompt="Run 'removing subtitle script'? "
    )
    # 3: unknown
    process_flow("unknown", attempt_identify_unknown, overall_prompt="Run 'set unknown audio script'? ")


if __name__ == "__main__":
    main()
