import sys
from pathlib import Path

from tools.video_audio_scripts import fixVideoMetadata as fvm


def test_run_reanalyze_invokes_subprocess(monkeypatch):
    calls = {}

    def fake_run(cmd, *args, **kwargs):
        calls['cmd'] = cmd
        class Res: pass
        return Res()

    monkeypatch.setattr('subprocess.run', fake_run)

    fvm.run_reanalyze('/some/scan.json')

    # script path should point into tools/video_audio_scripts
    assert any('analyzeVideoMetadata.py' in p for p in calls['cmd'])
    # the scan source is passed through
    assert '/some/scan.json' in calls['cmd']
