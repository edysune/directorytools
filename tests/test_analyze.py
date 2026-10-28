import pytest
from pathlib import Path

from tools.video_audio_scripts import analyzeVideoMetadata as avm


def test_english_whitelist_match_strict():
    """analyze keeps the local name `language_matches_whitelist`; it must be
    the STRICT policy matcher (no fuzzy prefix matching)."""
    m = avm.language_matches_whitelist
    assert m("eng", "English") is True
    assert m("en", "English") is True
    assert m("English", "English") is True
    assert not m("jpn", "English")
    assert not m(None, "English")
    assert not m("", "English")
    # strict (no fuzzy prefix), and ambiguous values never match:
    assert not m("und", "English")
    assert not m("English [CC]", "English")
    assert not m("morsk", "English")


def test_whitelist_multi_entry():
    m = avm.language_matches_whitelist
    assert m("jpn", "English, Japanese, Korean") is True
    assert m("kor", "English, Japanese, Korean") is True
    assert not m("fre", "English, Japanese, Korean")


def test_analyze_basic():
    # Build a synthetic scan JSON
    scan = {
        'results': [
            {
                'path': '/tmp/video1.mkv',
                'format': 'matroska',
                'audio_streams': [
                    {'index': 0, 'language': 'jpn', 'default': True},
                    {'index': 1, 'language': 'eng', 'default': False},
                ],
                'subtitle_streams': [
                    {'index': 0, 'language': 'jpn'},
                ],
            },
            {
                'path': '/tmp/video2.mkv',
                'format': 'matroska',
                'audio_streams': [
                    {'index': 0, 'language': 'eng', 'default': True},
                ],
                'subtitle_streams': [],
            },
            {
                'path': '/tmp/video3.mkv',
                'format': 'matroska',
                'audio_streams': [
                    {'index': 0, 'language': None, 'default': True},
                ],
                'subtitle_streams': [],
            },
        ]
    }

    default_audio, subtitle, unknown, timing = avm.analyze(
        scan,
        subtitle_whitelist='English',
        default_audio_language='English',
        audio_whitelist='English',
    )
    # video1 should appear in default_audio (default non-eng but has eng)
    assert any(d['path'].endswith('video1.mkv') for d in default_audio)
    # subtitle issues for video1
    assert any(s['path'].endswith('video1.mkv') for s in subtitle)
    # unknown for video3
    assert any(u['path'].endswith('video3.mkv') for u in unknown)
