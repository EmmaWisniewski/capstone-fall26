from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
