import pytest
from pathlib import Path

from tools.video_audio_scripts import analyzeVideoMetadata as avm


def test_is_english():
    assert avm.is_english('eng')
    assert avm.is_english('en')
    assert avm.is_english('English')
    assert not avm.is_english('jpn')
    assert not avm.is_english(None)
    assert not avm.is_english('')


def test_matches_any():
    assert avm.matches_any('japanese', ['jpn'])
    assert avm.matches_any('jp', ['jpn'])
    assert avm.matches_any('english', ['eng'])
    assert not avm.matches_any('spanish', ['eng', 'jpn'])


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

    default_audio, subtitle, unknown = avm.analyze(scan, ignore_patterns=None, require_default_english=False)
    # video1 should appear in default_audio (default non-eng but has eng)
    assert any(d['path'].endswith('video1.mkv') for d in default_audio)
    # subtitle issues for video1
    assert any(s['path'].endswith('video1.mkv') for s in subtitle)
    # unknown for video3
    assert any(u['path'].endswith('video3.mkv') for u in unknown)

    # test require_default_english flag - should include video1 and video3 as default not english
    default_audio2, _, _ = avm.analyze(scan, ignore_patterns=None, require_default_english=True)
    assert any(d['path'].endswith('video1.mkv') for d in default_audio2)
    assert any(d['path'].endswith('video3.mkv') for d in default_audio2)
