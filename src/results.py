from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_S11_PATTERNS = (
    "s11.csv",
    "result_s11.csv",
    "s11.txt",
    "result_s11.txt",
    "*s11*.csv",
    "*S11*.csv",
    "*s11*.txt",
    "*S11*.txt",
)


@dataclass(frozen=True)
class S11Point:
    frequency_ghz: float
    s11_db: float


def analyze_run_dir(
    run_dir: Path,
    target_frequency_ghz: float | None,
    s11_goal_db: float | None,
    patterns: Iterable[str] | None = DEFAULT_S11_PATTERNS,
) -> dict[str, Any]:
    patterns = patterns or DEFAULT_S11_PATTERNS
    s11_path = find_s11_file(run_dir, patterns)
    if s11_path is None:
        return {
            "result_status": "missing_s11",
            "s11_file": "",
            "s11_min_db": "",
            "s11_min_freq_ghz": "",
            "s11_at_target_db": "",
            "bandwidth_10db_ghz": "",
            "bandwidth_10db_low_ghz": "",
            "bandwidth_10db_high_ghz": "",
            "meets_s11_goal": "",
            "score": "",
        }

    points = read_s11_file(s11_path)
    metrics = analyze_s11_points(
        points=points,
        target_frequency_ghz=target_frequency_ghz,
        s11_goal_db=s11_goal_db,
    )
    metrics["result_status"] = "analyzed"
    metrics["s11_file"] = str(s11_path)
    return metrics


def analyze_runs(
    runs_dir: Path,
    target_frequency_ghz: float | None,
    s11_goal_db: float | None,
    patterns: Iterable[str] | None = DEFAULT_S11_PATTERNS,
) -> list[dict[str, Any]]:
    patterns = patterns or DEFAULT_S11_PATTERNS
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(path for path in runs_dir.glob("run_*") if path.is_dir()):
        row: dict[str, Any] = {"run_dir": str(run_dir), "run": _run_index(run_dir)}
        row.update(analyze_run_dir(run_dir, target_frequency_ghz, s11_goal_db, patterns))
        rows.append(row)
    return sort_analysis_rows(rows)


def write_analysis_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def find_s11_file(run_dir: Path, patterns: Iterable[str]) -> Path | None:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(path for path in run_dir.glob(pattern) if path.is_file())
    if not matches:
        return None
    return sorted(set(matches), key=lambda path: (len(path.name), path.name.lower()))[0]


def read_s11_file(path: Path) -> list[S11Point]:
    raw_points: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        numbers = _extract_numbers(line)
        if len(numbers) >= 2:
            raw_points.append((numbers[0], numbers[1]))

    if not raw_points:
        raise ValueError(f"No numeric S11 points found in {path}")

    frequency_scale = _infer_frequency_scale([point[0] for point in raw_points])
    s11_scale = _infer_s11_scale([point[1] for point in raw_points])

    points = [
        S11Point(frequency_ghz=freq * frequency_scale, s11_db=_to_s11_db(value, s11_scale))
        for freq, value in raw_points
    ]
    return sorted(points, key=lambda point: point.frequency_ghz)


def analyze_s11_points(
    points: list[S11Point],
    target_frequency_ghz: float | None,
    s11_goal_db: float | None,
) -> dict[str, Any]:
    if not points:
        raise ValueError("At least one S11 point is required.")

    min_point = min(points, key=lambda point: point.s11_db)
    s11_at_target = ""
    if target_frequency_ghz is not None:
        s11_at_target = interpolate_s11(points, target_frequency_ghz)

    low, high = bandwidth_below_threshold(points, s11_goal_db if s11_goal_db is not None else -10.0)
    bandwidth = "" if low is None or high is None else high - low

    if s11_goal_db is None or s11_at_target == "":
        meets_goal: bool | str = ""
    else:
        meets_goal = bool(s11_at_target <= s11_goal_db)

    score = _score(s11_at_target=s11_at_target, min_s11=min_point.s11_db, bandwidth=bandwidth)

    return {
        "s11_min_db": round(min_point.s11_db, 6),
        "s11_min_freq_ghz": round(min_point.frequency_ghz, 9),
        "s11_at_target_db": "" if s11_at_target == "" else round(float(s11_at_target), 6),
        "bandwidth_10db_ghz": "" if bandwidth == "" else round(float(bandwidth), 9),
        "bandwidth_10db_low_ghz": "" if low is None else round(low, 9),
        "bandwidth_10db_high_ghz": "" if high is None else round(high, 9),
        "meets_s11_goal": meets_goal,
        "score": round(score, 6),
    }


def interpolate_s11(points: list[S11Point], target_frequency_ghz: float) -> float | str:
    if target_frequency_ghz < points[0].frequency_ghz or target_frequency_ghz > points[-1].frequency_ghz:
        return ""

    for left, right in zip(points, points[1:]):
        if left.frequency_ghz == target_frequency_ghz:
            return left.s11_db
        if left.frequency_ghz <= target_frequency_ghz <= right.frequency_ghz:
            span = right.frequency_ghz - left.frequency_ghz
            if span == 0:
                return left.s11_db
            ratio = (target_frequency_ghz - left.frequency_ghz) / span
            return left.s11_db + ratio * (right.s11_db - left.s11_db)

    return points[-1].s11_db if points[-1].frequency_ghz == target_frequency_ghz else ""


def bandwidth_below_threshold(points: list[S11Point], threshold_db: float) -> tuple[float | None, float | None]:
    crossings: list[float] = []
    inside_frequencies = [point.frequency_ghz for point in points if point.s11_db <= threshold_db]
    if not inside_frequencies:
        return None, None

    for left, right in zip(points, points[1:]):
        left_delta = left.s11_db - threshold_db
        right_delta = right.s11_db - threshold_db
        if left_delta == 0:
            crossings.append(left.frequency_ghz)
        if left_delta * right_delta < 0:
            crossings.append(_crossing_frequency(left, right, threshold_db))
    if points[-1].s11_db == threshold_db:
        crossings.append(points[-1].frequency_ghz)

    low = min(crossings) if crossings else min(inside_frequencies)
    high = max(crossings) if crossings else max(inside_frequencies)
    return low, high


def sort_analysis_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[int, float]:
        score = row.get("score")
        if score == "":
            return (1, math.inf)
        return (0, float(score))

    return sorted(rows, key=key)


def _extract_numbers(line: str) -> list[float]:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "!", "%", "//")):
        return []
    return [
        float(match)
        for match in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", stripped)
    ]


def _infer_frequency_scale(values: list[float]) -> float:
    max_value = max(abs(value) for value in values)
    if max_value > 1_000_000:
        return 1e-9
    if max_value > 1_000:
        return 1e-3
    return 1.0


def _infer_s11_scale(values: list[float]) -> str:
    if values and all(0 <= value <= 1 for value in values):
        return "linear"
    return "db"


def _to_s11_db(value: float, scale: str) -> float:
    if scale == "linear":
        if value <= 0:
            return -300.0
        return 20.0 * math.log10(value)
    return value


def _crossing_frequency(left: S11Point, right: S11Point, threshold_db: float) -> float:
    span_db = right.s11_db - left.s11_db
    if span_db == 0:
        return left.frequency_ghz
    ratio = (threshold_db - left.s11_db) / span_db
    return left.frequency_ghz + ratio * (right.frequency_ghz - left.frequency_ghz)


def _score(s11_at_target: float | str, min_s11: float, bandwidth: float | str) -> float:
    primary = float(s11_at_target) if s11_at_target != "" else min_s11
    bandwidth_bonus = float(bandwidth) if bandwidth != "" else 0.0
    return primary - bandwidth_bonus


def _run_index(run_dir: Path) -> int | str:
    match = re.search(r"(\d+)$", run_dir.name)
    return int(match.group(1)) if match else run_dir.name
