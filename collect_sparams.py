#!/usr/bin/env python
"""
Collect S11/S21 results from CST export folders.

Supported inputs:
- Touchstone .s2p files
- CSV/TXT files with frequency, s11, and s21 columns
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path
from typing import Iterable


FREQ_SCALE_TO_GHZ = {
    "hz": 1e-9,
    "khz": 1e-6,
    "mhz": 1e-3,
    "ghz": 1.0,
}


def db_from_mag(mag: float) -> float:
    if mag <= 0:
        return float("-inf")
    return 20.0 * math.log10(mag)


def pair_to_db(a: float, b: float, fmt: str) -> float:
    fmt = fmt.lower()
    if fmt == "ri":
        return db_from_mag(math.hypot(a, b))
    if fmt == "ma":
        return db_from_mag(a)
    if fmt == "db":
        return a
    raise ValueError(f"Unsupported Touchstone format: {fmt}")


def strip_comment(line: str) -> str:
    return line.split("!", 1)[0].strip().lstrip("\ufeff")


def parse_touchstone(path: Path) -> list[dict[str, str]]:
    freq_unit = "ghz"
    data_format = "ma"
    rows: list[dict[str, str]] = []

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = strip_comment(raw_line)
        if not line:
            continue
        if line.startswith("#"):
            tokens = line[1:].lower().split()
            if tokens:
                freq_unit = tokens[0]
            if "ri" in tokens:
                data_format = "ri"
            elif "db" in tokens:
                data_format = "db"
            elif "ma" in tokens:
                data_format = "ma"
            continue

        parts = line.split()
        if len(parts) < 9:
            continue
        values = [float(item) for item in parts[:9]]
        freq_ghz = values[0] * FREQ_SCALE_TO_GHZ.get(freq_unit, 1.0)
        s11_db = pair_to_db(values[1], values[2], data_format)
        s21_db = pair_to_db(values[3], values[4], data_format)
        rows.append(
            {
                "source": str(path),
                "freq_ghz": f"{freq_ghz:.12g}",
                "s11_db": f"{s11_db:.12g}",
                "s21_db": f"{s21_db:.12g}",
            }
        )
    return rows


def normalized(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def find_column(fieldnames: Iterable[str], candidates: tuple[str, ...]) -> str | None:
    normalized_fields = {normalized(field): field for field in fieldnames}
    for candidate in candidates:
        for norm, original in normalized_fields.items():
            if candidate in norm:
                return original
    return None


def delimiter_for(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t ").delimiter
    except csv.Error:
        return ","


def parse_csv_result(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    delimiter = delimiter_for("\n".join(lines[:10]))
    reader = csv.DictReader(lines, delimiter=delimiter)
    if not reader.fieldnames:
        return []

    freq_col = find_column(reader.fieldnames, ("freq", "frequency"))
    s11_col = find_column(reader.fieldnames, ("s11",))
    s21_col = find_column(reader.fieldnames, ("s21",))
    if not (freq_col and s11_col and s21_col):
        return []

    scale = 1.0
    freq_norm = normalized(freq_col)
    if "hz" in freq_norm and "ghz" not in freq_norm:
        scale = 1e-9
    if "mhz" in freq_norm:
        scale = 1e-3
    if "khz" in freq_norm:
        scale = 1e-6

    rows: list[dict[str, str]] = []
    for row in reader:
        try:
            freq_ghz = float(row[freq_col]) * scale
            s11 = float(str(row[s11_col]).strip())
            s21 = float(str(row[s21_col]).strip())
        except Exception:
            continue
        rows.append(
            {
                "source": str(path),
                "freq_ghz": f"{freq_ghz:.12g}",
                "s11_db": f"{s11:.12g}",
                "s21_db": f"{s21:.12g}",
            }
        )
    return rows


def collect(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() == "s11_s21_summary.csv":
            continue
        suffix = path.suffix.lower()
        try:
            if suffix == ".s2p":
                rows.extend(parse_touchstone(path))
            elif suffix in {".csv", ".txt"}:
                rows.extend(parse_csv_result(path))
        except Exception as exc:
            rows.append(
                {
                    "source": str(path),
                    "freq_ghz": "",
                    "s11_db": "",
                    "s21_db": "",
                    "note": f"parse_failed: {exc}",
                }
            )
    return rows


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["source", "freq_ghz", "s11_db", "s21_db", "note"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect S11/S21 data from CST exports.")
    parser.add_argument("root", type=Path, help="Folder containing CST result exports.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path. Default: <root>/s11_s21_summary.csv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        print(f"error: folder not found: {root}")
        return 2
    output = args.output.resolve() if args.output else root / "s11_s21_summary.csv"
    rows = collect(root)
    write_summary(output, rows)
    print(f"[collect] rows={len(rows)}")
    print(f"[collect] output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
