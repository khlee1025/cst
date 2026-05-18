from __future__ import annotations

import argparse
from pathlib import Path

from src.sweep import load_config, run_sweep


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CST parameter sweeps.")
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to sweep config JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate run folders and logs without opening CST.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    run_sweep(config=config, config_path=args.config, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

