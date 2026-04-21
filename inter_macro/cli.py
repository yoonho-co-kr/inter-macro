from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Optional


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inter-macro",
        description="Screen color-based automation with retry, debounce, and profile support.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="profiles/default.json",
        help="Profile JSON path.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle and exit (no hotkey listener).",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Run hotkey listener (default mode).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect only; do not click.",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run interactive calibration and write profile JSON.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )

    if args.calibrate:
        from inter_macro.calibrate import run_calibration

        run_calibration(args.profile)
        return 0

    profile_path = Path(args.profile).expanduser().resolve()
    from inter_macro.config import load_profile

    profile = load_profile(profile_path)

    from inter_macro.runner import MacroRunner

    runner = MacroRunner(profile=profile, dry_run=args.dry_run)

    should_listen = args.listen or not args.once
    if args.once:
        runner.trigger()
        return 0

    if should_listen:
        runner.listen()
        return 0

    parser.error("Select one mode: --once or --listen")
    return 2
