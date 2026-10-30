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

sys.path.insert(0, str(Path(__file__).resolve().parent))  # shared-policy import (script & package runs)
import languagePolicy  # noqa: E402

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
    """STRICT whitelist match (delegates to languagePolicy.matches_whitelist).

    Kept for back-compat: analyzeVideoMetadata.py / gui_app.py import this
    name. The old fuzzy prefix-matching implementation was replaced because
    it could mis-classify ambiguous values. Policy (user, 2026-10-28):

    - Only a CONFIRMED language token (en/eng/English, ja/jpn/Japanese, ...)
      can match; entries are normalized to canonical ISO codes first.
    - Ambiguous values ('und', '', 'unknown', leaked labels like 'Stereo'/'MRSK',
      fan-sub names, 'English [CC]', format tokens) NEVER match here. Decide
      their fate with languagePolicy.lang_state -> 'ambiguous' = held on the
      EXCLUDE list, never auto-removed. (Closes BUG-5 + RISK-2.)
    """
    return languagePolicy.matches_whitelist(lang, whitelist)


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


def backup_file_before_fix(path: str, keep_backup: bool = True):
    """Create a backup copy with -original suffix before modifying.
    
    Args:
        path: Path to the file to backup
        keep_backup: If False, skip creating a backup
    """
    if not keep_backup:
        return
    
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


def attempt_set_default_audio(item: dict, default_audio_language: str = "English", keep_backup: bool = True):
    """Set the default audio track to the preferred language.
    
    Args:
        item: Scan result dict with audio_streams
        default_audio_language: Preferred audio language (e.g., "English")
        keep_backup: Whether to create a backup before modifying
    
    Returns:
        Dict with keys: success (bool), previous (str), new (str) for logging
    """
    path = item.get("path")
    if languagePolicy.is_path_excluded(path):
        print(f"Path in excluded (foreign) category; skipping ALL changes for {path}.")
        return {"success": False}
    fmt = item.get("format", "")
    audio_streams = item.get("audio_streams") or []
    preferred_stream = None
    preferred_idx = None
    old_default = None
    
    # Find current default and preferred streams (preferred = confirmed 'keep')
    for idx, a in enumerate(audio_streams):
        if a.get("default"):
            old_default = a.get("language", "unknown")
        if languagePolicy.lang_state(a.get("language"), default_audio_language) == "keep":
            preferred_stream = a
            preferred_idx = idx

    if not preferred_stream:
        print(f"No {default_audio_language} audio streams for {path}; skipping.")
        return {"success": False, "error": f"No {default_audio_language} audio streams found"}

    if preferred_stream.get("default"):
        print(f"{default_audio_language} audio already default for {path}; skipping.")
        return {"success": False, "error": f"{default_audio_language} audio already default"}

    # Create backup before making changes
    backup_file_before_fix(path, keep_backup=keep_backup)
    
    preferred_lang = preferred_stream.get("language", "unknown")
    
    # Attempt container-specific commands
    if "matroska" in fmt:
        # Use ffmpeg to rewrite the file with the preferred audio as default
        # This is more reliable than mkvpropedit for setting default dispositions
        try:
            # Insert .tmp before the extension so ffmpeg can detect the container format
            # e.g., video.mkv -> video.tmp.mkv instead of video.mkv.tmp
            tmp = str(Path(path).with_suffix(".tmp" + Path(path).suffix))
            # Use ffmpeg to copy file with disposition changes
            cmd = ["ffmpeg", "-y", "-i", path, "-map", "0", "-c", "copy"]

            # Set disposition for audio streams
            # -disposition:a:N can be used where N is the audio stream index (0-based among audio streams only)
            for idx in range(len(audio_streams)):
                if idx == preferred_idx:
                    cmd += ["-disposition:a:{}".format(idx), "default"]
                else:
                    cmd += ["-disposition:a:{}".format(idx), "0"]

            cmd += [tmp]

            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            shutil.move(tmp, path)

            # VALIDATION: Re-scan the file to verify the change actually persisted
            from scanVideoMetadata import analyze_file
            rescanned = analyze_file(Path(path))
            rescanned_audio = rescanned.get("audio_streams") or []

            # Find the audio stream we just set as default
            default_found = False
            for idx, a in enumerate(rescanned_audio):
                if language_matches_whitelist(a.get("language"), default_audio_language):
                    if a.get("default"):
                        default_found = True

            if not default_found:
                print(f"CRITICAL: ffmpeg succeeded but validation FAILED - changes did not persist!")
                return {
                    "success": False,
                    "error": "ffmpeg validation failed - changes not persisted"
                }

            print(f"Set {default_audio_language} audio as default for {path}")
            return {
                "success": True,
                "previous": old_default or "none",
                "new": preferred_lang
            }
        except subprocess.CalledProcessError as e:
            print(f"CRITICAL: ffmpeg FAILED for {path}")
            print(f"  Return code: {e.returncode}")
            print(f"  Stderr: {e.stderr}")
            return {"success": False, "error": f"ffmpeg failed: {e.stderr}"}
        except Exception as e:
            print(f"CRITICAL: Exception during audio fix: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    # For other containers, use ffmpeg to rewrite dispositions (copy)
    if any(x in fmt for x in ("mp4", "mov")):
        # find audio stream zero-based order for ffmpeg mapping
        # we'll set disposition for the chosen audio by copying file and adjusting dispositions
        # build ffmpeg metadata args
        try:
            # Insert .fixed before the extension so ffmpeg can detect the container format
            tmp = str(Path(path).with_suffix(".fixed" + Path(path).suffix))
            # build ffmpeg command with proper stream mapping
            cmd = ["ffmpeg", "-y", "-i", path, "-map", "0", "-c", "copy"]
            # set default disposition: set chosen audio to default
            cmd += ["-disposition:a:0", "default"]
            cmd += [tmp]
            subprocess.run(cmd, check=True)
            shutil.move(tmp, path)
            print(f"Rewrote container to set default audio for {path}")
            return {
                "success": True,
                "previous": old_default or "none",
                "new": preferred_lang
            }
        except Exception as e:
            print(f"Failed to set default audio via ffmpeg: {e}")
            return {"success": False}

    print(f"Unsupported container for setting default audio: {fmt} for {path}")
    return {"success": False}


def attempt_remove_non_whitelisted_subs(item: dict, subtitle_whitelist: str = "English", keep_backup: bool = True):
    """Remove subtitles that don't match the subtitle whitelist.
    
    Args:
        item: Video metadata dictionary with subtitle_streams
        subtitle_whitelist: Comma-separated list of languages to keep
        keep_backup: Whether to create backup before modifying
    
    Returns:
        Dict with keys: 'success' (bool), 'removed' (list of languages), 'remaining' (list of languages)
        Returns {'success': False} if no changes were made
    """
    path = item.get("path")
    if languagePolicy.is_path_excluded(path):
        print(f"Path in excluded (foreign) category; skipping ALL changes for {path}.")
        return {"success": False}
    fmt = item.get("format", "")
    subs = item.get("subtitle_streams") or []
    if not subs:
        print(f"No subtitles for {path}; skipping.")
        return {"success": False}

    # Create backup before making changes
    backup_file_before_fix(path, keep_backup=keep_backup)

    # Track-level policy (languagePolicy.lang_state):
    #   keep       -> kept
    #   confirmed  -> removed (specific, known non-whitelisted language)
    #   ambiguous  -> NEVER removed; EXCLUDED for human review (und/'unknown'/untagged,
    #                 ASSIST/SRT format tokens, fan-sub/alt-audio names, 'English [CC]',
    #                 channel labels). Closes BUG-5 + RISK-2 (user policy, 2026-10-28).
    # Removing ALL subtitles of a file is only ever the user-approved RISK-1 case:
    # every track confirmed non-whitelisted (no keep, no ambiguous).
    states = [languagePolicy.lang_state(s.get("language"), subtitle_whitelist) for s in subs]
    remove_positions = [i for i, st in enumerate(states) if st == "confirmed"]
    held_positions = [i for i, st in enumerate(states) if st == "ambiguous"]
    if held_positions:
        held_names = ", ".join(str(subs[i].get("language") or "(untagged)") for i in held_positions)
        print(f"Ambiguous subtitle track(s) [{held_names}] are EXCLUDED (not removed) for {path}.")
    if not remove_positions:
        print(f"No confirmed non-whitelisted subtitles to remove for {path}.")
        return {"success": False}

    # Get details of removed and remaining streams
    removed_langs = [subs[i].get("language") for i in remove_positions]
    remaining_langs = [subs[i].get("language") for i in range(len(subs)) if i not in remove_positions]

    # use ffmpeg to copy and drop these subtitle streams
    try:
        # Insert .tmp before the extension so ffmpeg can detect the container format
        tmp = str(Path(path).with_suffix(".tmp" + Path(path).suffix))
        cmd = ["ffmpeg", "-y", "-i", path, "-map", "0", "-c", "copy"]
        # Exclude non-whitelisted subtitle streams
        for pos in remove_positions:
            cmd += ["-map", f"-0:s:{pos}"]
        
        cmd += [tmp]
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.move(tmp, path)
        print(f"Removed non-whitelisted subtitles from {path}")
        return {"success": True, "removed": removed_langs, "remaining": remaining_langs}
    except Exception as e:
        print(f"Failed to remove subtitles via ffmpeg: {e}")
        return {"success": False}



def attempt_remove_non_whitelisted_audio(item: dict, audio_whitelist: str = "English", keep_backup: bool = True):
    """Remove audio streams not in the whitelist.
    
    Safety rules:
    1. Skip if no audio streams exist
    2. Skip if applying whitelist would remove ALL audio streams (never leave files without audio)
    3. Only remove if at least 1 audio stream matches whitelist
    
    Returns:
        Dict with keys: 'success' (bool), 'removed' (list of languages), 'remaining' (list of languages)
        Returns {'success': False} if no changes were made or if skipped for safety
    """
    path = item.get("path")
    if languagePolicy.is_path_excluded(path):
        print(f"Path in excluded (foreign) category; skipping ALL changes for {path}.")
        return {"success": False}
    fmt = item.get("format", "")
    audio_streams = item.get("audio_streams") or []
    
    # Rule 1: Check if audio streams exist
    if not audio_streams:
        print(f"No audio streams for {path}; skipping audio whitelist removal.")
        return {"success": False}

    # Track-level policy (languagePolicy.lang_state):
    #   keep       -> kept
    #   confirmed  -> removed
    #   ambiguous  -> KEPT (BUG-5: 'und'/labels/unknowns must never be auto-removed;
    #                 suspected-English gets no audio-strip)
    states = [languagePolicy.lang_state(a.get("language"), audio_whitelist) for a in audio_streams]
    kept_positions = [i for i, st in enumerate(states) if st != "confirmed"]
    remove_positions = [i for i, st in enumerate(states) if st == "confirmed"]

    # Rule 2: Safety check - never remove all audio streams (protects miscategorized
    # content that has no whitelisted audio at all)
    if not kept_positions:
        print(f"Applying audio whitelist would remove ALL audio streams from {path}; skipping to preserve audio.")
        return {"success": False}
    
    if not remove_positions:
        print(f"No non-whitelisted audio streams to remove for {path}.")
        return {"success": False}

    # Get details of removed and remaining streams
    removed_langs = [audio_streams[i].get("language") for i in remove_positions]
    remaining_langs = [audio_streams[i].get("language") for i in kept_positions]

    # Create backup before making changes
    backup_file_before_fix(path, keep_backup=keep_backup)
    try:
        # Insert .tmp before the extension so ffmpeg can detect the container format
        tmp = str(Path(path).with_suffix(".tmp" + Path(path).suffix))
        cmd = ["ffmpeg", "-y", "-i", path, "-map", "0", "-c", "copy"]
        # Exclude non-whitelisted audio streams
        for pos in remove_positions:
            cmd += ["-map", f"-0:a:{pos}"]
        
        cmd += [tmp]
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.move(tmp, path)
        print(f"Removed non-whitelisted audio streams from {path}")
        return {"success": True, "removed": removed_langs, "remaining": remaining_langs}
    except Exception as e:
        print(f"Failed to remove audio streams via ffmpeg: {e}")
        return {"success": False}



def attempt_identify_unknown(item: dict):
    path = item.get("path")
    if languagePolicy.is_path_excluded(path):
        print(f"Path in excluded (foreign) category; skipping for {path}.")
        return
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
                        # Insert .langset before the extension so ffmpeg can detect the container format
                        tmp = str(Path(path).with_suffix(".langset" + Path(path).suffix))
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
