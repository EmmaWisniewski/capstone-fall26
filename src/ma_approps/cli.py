"""Command line for the pipeline.

    python -m ma_approps run --stage {discover…export|all} [--law 2023-28] [--offline]
    python -m ma_approps validate

Stages run in DESIGN §6 order. A stage module exposes ``IMPLEMENTED`` and ``run(ctx)``; stubs
are skipped with a message so the empty pipeline stays green (M0).
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from ma_approps.context import Context

# (stage name, module, workstream owner) in DESIGN §6 order
STAGES = (
    ("discover", "ma_approps.discover", "A"),
    ("fetch", "ma_approps.fetch", "A"),
    ("normalize", "ma_approps.normalize", "B"),
    ("extract_items", "ma_approps.extract_items", "B"),
    ("extract_actions", "ma_approps.extract_actions", "C"),
    ("vetoes", "ma_approps.vetoes", "A"),
    ("assemble", "ma_approps.assemble", "E"),
    ("enrich", "ma_approps.enrich", "D"),
    ("classify", "ma_approps.classify", "D"),
    ("validate", "ma_approps.validate", "E"),
    ("review", "ma_approps.review", "E"),
    ("export", "ma_approps.export", "E"),
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
            print(f"[{name}] skipped: not implemented yet (workstream {owner})")
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
