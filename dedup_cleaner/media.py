"""Optional media-integrity probe (pluggable).

Spec: "ideally use FFmpeg / another similar tool to determine if the file has
issues when being played."  Keeping that a *hook* means the tool never hard-
requires ffmpeg, and the probe is only exercised on files the corruption check
wants inspected. A default no-op is safe: return ``None`` to skip.

To wire in ffprobe, subclass/replace :func:`probe_media` or set
``DEDUP_MEDIA_PROBE_CMD`` (one argv list) in the future.
"""

from __future__ import annotations
import os
from typing import Callable, List, Optional

# extensions treated as media (video/audio) for corruption probing
MEDIA_EXTS = {".mp4",".mkv",".avi",".mov",".m4v",".webm",".mp3",
              ".flac",".m4a",".aac",".wav",".opus",".ogg"}

def is_media(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in MEDIA_EXTS


def probe_media(path: str) -> Optional["tuple[bool, str]"]:
    """Default probe = disabled. Return ``(True,"")`` ok, ``(False,msg)`` bad,
    or ``None`` to skip. Never raises."""
    return None
