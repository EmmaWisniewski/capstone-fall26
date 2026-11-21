"""Run context: repo paths and settings shared by every stage (DESIGN §6, §15)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_settings(path: Path | None = None) -> dict[str, Any]:
    with open(path or REPO_ROOT / "config" / "settings.toml", "rb") as f:
        return tomllib.load(f)


@dataclass
class Context:
    """Where a run reads and writes. Tests point ``raw_dir`` at ``tests/samples``."""

    root: Path = REPO_ROOT
    raw_dir: Path | None = None
    interim_dir: Path | None = None
    output_dir: Path | None = None
    reports_dir: Path | None = None
    review_queue: Path | None = None  # generated (§7.12); see __post_init__
    law: str | None = None  # restrict a run to one law_key
    offline: bool = False  # never touch the network; read only from raw_dir
    settings: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.raw_dir = self.raw_dir or self.root / "data" / "raw"
        self.interim_dir = self.interim_dir or self.root / "data" / "interim"
        default_output = self.root / "data" / "output"
        self.output_dir = self.output_dir or default_output
        self.reports_dir = self.reports_dir or self.root / "reports"
        # The queue sits in review/ for a normal run. A run that writes its files elsewhere (every
        # test) keeps the queue with them, so it never overwrites the real one.
        if self.review_queue is None:
            in_review = self.output_dir == default_output
            folder = self.root / "review" if in_review else self.output_dir
            self.review_queue = folder / "review_queue.csv"
        if not self.settings:
            self.settings = load_settings(self.root / "config" / "settings.toml")

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def review_dir(self) -> Path:
        return self.root / "review"
