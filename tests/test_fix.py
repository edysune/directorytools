import sys
from pathlib import Path

from tools.video_audio_scripts import fixVideoMetadata as fvm


def test_run_reanalyze_invokes_subprocess(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, check=True):
        calls['cmd'] = cmd
        calls['check'] = check
        class Res: pass
        return Res()

    monkeypatch.setattr('subprocess.run', fake_run)

    # call run_reanalyze
    fvm.run_reanalyze('/some/scan.json', require_default_english=True)

    # script path should point into tools/video_audio_scripts
    assert any('analyzeVideoMetadata.py' in p for p in calls['cmd'])
    assert '--require-default-english' in calls['cmd']
