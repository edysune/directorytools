
#!/usr/bin/env python3
"""Shim forwarding to tools/video_audio_scripts/scanVideoMetadata.py"""
from pathlib import Path
import subprocess
import sys

script = Path(__file__).resolve().parent / "video_audio_scripts" / "scanVideoMetadata.py"
if not script.exists():
    print(f"Moved script not found: {script}")
    sys.exit(1)

cmd = [sys.executable, str(script)] + sys.argv[1:]
rc = subprocess.call(cmd)
sys.exit(rc)
