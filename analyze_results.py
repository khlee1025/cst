from __future__ import annotations

import argparse
from pathlib import Path

from src.results import analyze_runs, write_analysis_csv
from src.sweep import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze CST sweep S11 result files.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/sweep.patch_antenna.example.json"),
        help="Path to sweep config JSON.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Override runs directory. Defaults to project.runs_dir from config.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    scoring = config.get("scoring", {})
    runs_dir = args.runs_dir or Path(config.get("project", {}).get("runs_dir", "runs"))
    patterns = config.get("results", {}).get("s11_file_patterns")

    rows = analyze_runs(
        runs_dir=runs_dir,
        target_frequency_ghz=scoring.get("target_frequency_ghz"),
        s11_goal_db=scoring.get("s11_goal_db", -10.0),
        patterns=patterns if patterns else None,
    )
    output_path = runs_dir / "analysis_results.csv"
    write_analysis_csv(output_path, rows)
    print(f"Analyzed {len(rows)} run folders.")
    print(f"Wrote {output_path}")
    analyzed_rows = [row for row in rows if row.get("result_status") == "analyzed"]
    if analyzed_rows:
        best = analyzed_rows[0]
        print(
            "Best run: "
            f"{best.get('run')} "
            f"S11@target={best.get('s11_at_target_db')} dB "
            f"min={best.get('s11_min_db')} dB "
            f"bw={best.get('bandwidth_10db_ghz')} GHz"
        )
    elif rows:
        print("No S11 files found yet. Export S11 into each run folder, then analyze again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
