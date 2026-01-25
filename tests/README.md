Testing
=======

Quick guide to run the test suite for this repository.

Prerequisites
-------------
- Python 3.8+ (3.10 recommended)
- git

Setup (recommended)
-------------------
Create and activate a virtual environment, then install dev requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

(You can also use the preconfigured venv at `.venv` if present.)

Run tests
---------
Run the full test suite:

```bash
python -m pytest -q
```

Run a single test file:

```bash
python -m pytest tests/test_scan.py -q
```

Run a single test case:

```bash
python -m pytest tests/test_analyze.py::test_analyze_basic -q
```

Useful options
--------------
- `-q` quiet output (used above)
- `-k <expr>` run tests matching expression
- `-x` stop after first failure
- `-v` more verbose output

Test layout and notes
---------------------
- Tests live in the `tests/` directory and follow the `test_*.py` naming convention.
- The scripts under `tools/video_audio_scripts` are the primary unit targets.
- Tests use `monkeypatch` where external tools (ffprobe/ffmpeg/mkvpropedit) would be required.

Adding tests
------------
- Add new files as `tests/test_*.py`.
- Use assertions and pytest fixtures/monkeypatch to avoid calling external binaries in CI.

CI / Automation
----------------
- The `requirements-dev.txt` file lists `pytest`. Use it to install test deps in CI.

Contact
-------
If a test fails or you want help writing assertions for a particular function, tell me which file/function and I can add/adjust tests.
