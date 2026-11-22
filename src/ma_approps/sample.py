"""Draw a random sample of the main file for people to check against the laws.

    python -m ma_approps sample [--size 200] [--seed 2026]

Reads the main file in ``data/output/`` and writes ``reports/random_review_sample.csv``: the
sampled rows, every column of the main file, plus blank columns for the reviewer. The same file,
size and seed always give the same rows, so the draw can be repeated; a new seed gives a new draw.

Rows are grouped by fiscal year and funding action. Each group gets a share of the sample in
proportion to the square root of its size, and at least one row, so the big groups (original
appropriations) don't crowd out the small ones (vetoes, transfers, supplementals).
"""

from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from ma_approps import schemas
from ma_approps.context import Context
from ma_approps.export import output_name

DEFAULT_SIZE = 200
DEFAULT_SEED = 2026
SAMPLE_FILE = "random_review_sample.csv"
# Filled in by the reviewer; nothing reads them back (findings go into the fix files).
REVIEW_COLUMNS = ("Matches the law? (Yes/No)", "What is wrong", "Reviewer", "Date checked")
GROUP_COLUMNS = ("Fiscal year", "Funding action")
# Added for the reviewer from the program's working file (not part of the main file).
SOURCE_COLUMN = "Amount source (CTHRU / Law text)"
SOURCE_LABELS = {"cthru": "CTHRU", "law_text": "Law text", "manual": "Manual"}


def _group_key(row: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(row[c] for c in GROUP_COLUMNS)


def shares(sizes: Mapping[tuple, int], total: int) -> dict[tuple, int]:
    """How many rows each group gets: proportional to sqrt(size), at least 1, at most its size.

    Uses the largest-remainder method so the shares add up to ``total`` (or to every row, when
    ``total`` is at least the number of rows)."""
    if total >= sum(sizes.values()):
        return dict(sizes)
    weights = {k: math.sqrt(n) for k, n in sizes.items()}
    scale = total / sum(weights.values())
    out = {k: min(sizes[k], max(1, int(w * scale))) for k, w in weights.items()}
    # Hand out (or take back) the difference one row at a time, biggest fractional part first.
    frac = {k: w * scale - int(w * scale) for k, w in weights.items()}
    order = sorted(weights, key=lambda k: frac[k], reverse=True)
    while sum(out.values()) < total:
        grew = False
        for k in order:
            if sum(out.values()) < total and out[k] < sizes[k]:
                out[k] += 1
                grew = True
        if not grew:
            break
    while sum(out.values()) > total:
        k = max((k for k in out if out[k] > 1), key=lambda k: out[k], default=None)
        if k is None:
            break
        out[k] -= 1
    return out


def draw(rows: Sequence[Mapping[str, str]], size: int, seed: int) -> list[dict[str, str]]:
    """The sampled rows, in the main file's order. Deterministic for a given input and seed."""
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        groups[_group_key(row)].append(i)
    want = shares({k: len(v) for k, v in groups.items()}, size)
    rng = random.Random(seed)
    picked: list[int] = []
    for key in sorted(groups):  # sorted, so the seed means the same thing on every run
        picked += rng.sample(groups[key], want[key])
    return [dict(rows[i]) for i in sorted(picked)]


def amount_sources(ctx: Context) -> dict[str, str]:
    """Record ID -> where its amount came from (CTHRU or the law's text), from combine's output."""
    path = ctx.interim_dir / "funding_actions.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {
            r["record_id"]: SOURCE_LABELS.get(r["amount_source"], r["amount_source"])
            for r in csv.DictReader(f)
        }


def run(ctx: Context, size: int = DEFAULT_SIZE, seed: int = DEFAULT_SEED) -> int:
    source: Path = ctx.output_dir / output_name("ma_appropriations", ctx.settings)
    if not source.exists():
        print(f"  {source.name} not found in {ctx.output_dir}; run the export stage first")
        return 1
    with open(source, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"  {source.name} has no rows")
        return 1
    chosen = draw(rows, size, seed)
    sources = amount_sources(ctx)
    if not sources:
        print("  note: data/interim/funding_actions.csv not found; 'Amount source' left blank")
    for row in chosen:
        row[SOURCE_COLUMN] = sources.get(row["Record ID"], "")
    out = ctx.reports_dir / SAMPLE_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = [*schemas.EXPORT_COLUMNS, SOURCE_COLUMN, *REVIEW_COLUMNS]
    # utf-8-sig so Excel shows curly quotes and accents correctly.
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n", restval="")
        w.writeheader()
        w.writerows(chosen)
    groups = len({_group_key(r) for r in chosen})
    print(f"  drew {len(chosen)} of {len(rows)} rows from {source.name} (seed {seed})")
    print(f"  covering {groups} fiscal year / funding action groups: {out}")
    return 0
