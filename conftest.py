"""Ensure the repo root is importable + small shared fixtures."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402


@pytest.fixture
def fkey():
    return Fernet.generate_key().decode()
