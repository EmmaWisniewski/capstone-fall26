"""Command line for the pipeline.

    python -m ma_approps run --stage {laws…validate|all} [--law 2023-28] [--offline]
    python -m ma_approps validate

Stages run in DESIGN §6 order. A stage module exposes ``IMPLEMENTED`` and ``run(ctx)``; stubs
are skipped with a message so the empty pipeline stays green (M0).
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from ma_approps.context import Context

# (stage name, module, workstream owner) in DESIGN §6 order. "all" = Putting it together.
STAGES = (
    ("laws", "ma_approps.laws", "A"),
    ("cthru", "ma_approps.cthru", "E"),
    ("read_items", "ma_approps.read_items", "B"),
    ("read_bonds", "ma_approps.read_bonds", "A"),
    ("read_amendments", "ma_approps.read_amendments", "C"),
    ("assemble", "ma_approps.assemble", "all"),
    ("describe", "ma_approps.describe", "D"),
    ("export", "ma_approps.export", "all"),
    ("validate", "ma_approps.validate", "E"),
)
STAGE_NAMES = tuple(name for name, _, _ in STAGES)


def stage_module(name: str):
    module = dict((n, m) for n, m, _ in STAGES)[name]
    return importlib.import_module(module)


def run_stages(ctx: Context, names: list[str]) -> int:
    status = 0
    for name, _, owner in STAGES:
        if name not in names:
            continue
        mod = stage_module(name)
        if not getattr(mod, "IMPLEMENTED", False):
            print(f"[{name}] skipped: not implemented yet (owner: {owner})")
            continue
        print(f"[{name}] running")
        status = mod.run(ctx) or 0
        if status:
            print(f"[{name}] failed with status {status}")
            return status
    return status


def _context(args: argparse.Namespace) -> Context:
    return Context(
        raw_dir=Path(args.raw_dir) if getattr(args, "raw_dir", None) else None,
        law=getattr(args, "law", None),
        offline=getattr(args, "offline", False),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ma_approps")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one stage or all stages")
    run.add_argument("--stage", required=True, choices=(*STAGE_NAMES, "all"))
    run.add_argument("--law", help="restrict to one law_key, e.g. 2023-28")
    run.add_argument("--offline", action="store_true", help="read only from the raw cache")
    run.add_argument("--raw-dir", help="override data/raw (e.g. tests/fixtures)")

    sub.add_parser("validate", help="shortcut for run --stage validate")

    args = parser.parse_args(argv)
    ctx = _context(args)
    if args.command == "validate":
        return run_stages(ctx, ["validate"])
    names = list(STAGE_NAMES) if args.stage == "all" else [args.stage]
    return run_stages(ctx, names)
