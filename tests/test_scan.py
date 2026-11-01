from pathlib import Path

from tools.video_audio_scripts import scanVideoMetadata as svm


def test_is_video_file():
    assert svm.is_video_file(Path('movie.MP4'))
    assert not svm.is_video_file(Path('document.txt'))


def test_detect_language_from_tags():
    assert svm.detect_language_from_tags({'language': 'eng'}) == 'eng'
    assert svm.detect_language_from_tags({'lang': 'jpn'}) == 'jpn'
    assert svm.detect_language_from_tags({'title': 'Spanish subs'}) == 'Spanish subs'
    assert svm.detect_language_from_tags({}) is None


def test_analyze_file_monkeypatch(monkeypatch):
    # Provide a fake ffprobe output
    fake_info = {
        'format': {'format_name': 'matroska', 'duration': '10.0', 'size': '12345'},
        'streams': [
            {'index': 0, 'codec_type': 'audio', 'codec_name': 'aac', 'tags': {'language': 'eng'}, 'disposition': {'default': 1}, 'channels': 2, 'sample_rate': '48000'},
            {'index': 1, 'codec_type': 'subtitle', 'codec_name': 'subrip', 'tags': {'language': 'jpn'}, 'disposition': {}},
        ]
    }

    def fake_ffprobe(path):
        return fake_info

    monkeypatch.setattr(svm, 'run_ffprobe', fake_ffprobe)

    out = svm.analyze_file(Path('/tmp/fake.mkv'))
    assert out['format'] == 'matroska'
    assert len(out['audio_streams']) == 1
    assert len(out['subtitle_streams']) == 1
    assert out['audio_streams'][0]['language'] == 'eng'
