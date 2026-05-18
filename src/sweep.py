from __future__ import annotations

import csv
import itertools
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cst_adapter import CstAdapter


@dataclass(frozen=True)
class SweepPoint:
    index: int
    parameters: dict[str, float]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_sweep(config: dict[str, Any], config_path: Path, dry_run: bool) -> None:
    project_config = config["project"]
    runs_dir = Path(project_config.get("runs_dir", "runs"))
    runs_dir.mkdir(parents=True, exist_ok=True)

    points = build_sweep_points(config["sweep"])
    max_runs = config["sweep"].get("max_runs")
    if max_runs is not None:
        points = points[: int(max_runs)]

    summary_path = runs_dir / "sweep_results.csv"
    adapter = None if dry_run else CstAdapter(config["cst"])

    rows: list[dict[str, Any]] = []
    for point in points:
        run_dir = runs_dir / f"run_{point.index:04d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        write_json(run_dir / "params.json", point.parameters)
        write_json(run_dir / "run_info.json", build_run_info(config_path, dry_run))

        cst_path = prepare_cst_project(project_config, run_dir)
        status = "dry_run"
        error = ""

        try:
            if adapter is not None:
                adapter.run_point(cst_path=cst_path, run_dir=run_dir, parameters=point.parameters)
                status = "completed"
        except Exception as exc:
            status = "failed"
            error = str(exc)

        row = {"run": point.index, "status": status, "error": error, "cst_path": str(cst_path)}
        row.update(point.parameters)
        rows.append(row)
        write_summary(summary_path, rows)

        if status == "failed":
            raise RuntimeError(f"Run {point.index:04d} failed: {error}") from None


def build_sweep_points(sweep_config: dict[str, Any]) -> list[SweepPoint]:
    parameter_specs = sweep_config["parameters"]
    names = [spec["name"] for spec in parameter_specs]
    value_lists = [expand_values(spec) for spec in parameter_specs]

    points: list[SweepPoint] = []
    for index, values in enumerate(itertools.product(*value_lists), start=1):
        points.append(SweepPoint(index=index, parameters=dict(zip(names, values))))
    return points


def expand_values(spec: dict[str, Any]) -> list[float]:
    if "values" in spec:
        return [float(value) for value in spec["values"]]

    start = float(spec["start"])
    stop = float(spec["stop"])
    step = float(spec["step"])
    if step == 0:
        raise ValueError(f"Parameter {spec['name']} has zero step.")
    if (stop - start) * step < 0:
        raise ValueError(f"Parameter {spec['name']} step direction does not reach stop.")

    values: list[float] = []
    current = start
    epsilon = abs(step) * 1e-9
    if step > 0:
        while current <= stop + epsilon:
            values.append(round(current, 12))
            current += step
    else:
        while current >= stop - epsilon:
            values.append(round(current, 12))
            current += step
    return values


def prepare_cst_project(project_config: dict[str, Any], run_dir: Path) -> Path:
    template = Path(project_config["template_cst"])
    cst_path = run_dir / "model.cst"

    if not project_config.get("copy_template_per_run", True):
        return template

    if not template.exists():
        write_json(
            run_dir / "missing_template.note.json",
            {
                "template_cst": str(template),
                "message": "Template CST file was not found. Dry-run can continue; real CST run needs this file.",
            },
        )
        return cst_path

    shutil.copy2(template, cst_path)
    return cst_path


def build_run_info(config_path: Path, dry_run: bool) -> dict[str, Any]:
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "dry_run": dry_run,
    }


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

