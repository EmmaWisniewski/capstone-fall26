from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "tests" / "samples"


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES
