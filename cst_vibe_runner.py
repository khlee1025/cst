#!/usr/bin/env python
"""
CST Vibe Runner

Runs a small JSON/YAML command plan against CST Studio Suite through the
Windows COM interface. The plan is intended to be produced by a local LLM or
written by hand. Use --dry-run first to inspect the generated CST macros.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


class PlanError(Exception):
    """Raised when the command plan is invalid."""


def load_plan(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PlanError(f"Plan file not found: {path}")

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise PlanError(
                "YAML plans require PyYAML. Install it or use JSON instead."
            ) from exc
        data = yaml.safe_load(text)
    else:
        raise PlanError("Use a .json, .yaml, or .yml plan file.")

    if not isinstance(data, dict):
        raise PlanError("The plan root must be an object.")
    return data


def q(value: Any) -> str:
    """Quote a value for CST macro strings."""

    if value is None:
        return '""'
    text = str(value).replace('"', '""')
    return f'"{text}"'


def expect_pair(command: dict[str, Any], key: str) -> list[Any]:
    value = command.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise PlanError(f"{command.get('op', '<command>')}.{key} must be a 2-item list.")
    return value


def require(command: dict[str, Any], key: str) -> Any:
    if key not in command:
        raise PlanError(f"{command.get('op', '<command>')} requires '{key}'.")
    return command[key]


def indented(lines: Iterable[str]) -> str:
    return "\n".join(lines)


class CSTSession:
    def __init__(self, dry_run: bool, prog_id: str, visible: bool) -> None:
        self.dry_run = dry_run
        self.prog_id = prog_id
        self.visible = visible
        self.cst = None
        self.mws = None

    def connect_project(self, project: dict[str, Any]) -> None:
        mode = project.get("mode", "new")
        path = project.get("path")

        if self.dry_run:
            print(f"[dry-run] COM Dispatch: {self.prog_id}")
            if mode == "open":
                print(f"[dry-run] Open CST project: {Path(path).resolve() if path else path}")
            else:
                print("[dry-run] Create new CST Microwave Studio project")
            return

        try:
            import win32com.client  # type: ignore
        except ImportError as exc:
            raise PlanError(
                "pywin32 is required for real CST execution. Install it with: "
                "python -m pip install pywin32"
            ) from exc

        self.cst = win32com.client.Dispatch(self.prog_id)
        if self.visible:
            try:
                self.cst.Visible = True
            except Exception:
                pass

        if mode == "open":
            if not path:
                raise PlanError("project.path is required when project.mode is 'open'.")
            self.mws = self.cst.OpenFile(str(Path(path).resolve()))
        elif mode == "new":
            self.mws = self.cst.NewMWS()
        else:
            raise PlanError("project.mode must be 'new' or 'open'.")

    def add_history(self, name: str, code: str) -> None:
        if self.dry_run:
            print(f"\n--- AddToHistory: {name} ---")
            print(code.rstrip())
            print("--- end ---")
            return
        self._require_mws()
        self.mws.AddToHistory(name, code)

    def store_parameter(self, name: str, value: Any) -> None:
        if self.dry_run:
            print(f"[dry-run] StoreParameter {name} = {value}")
            return
        self._require_mws()
        self.mws.StoreParameter(str(name), str(value))

    def rebuild(self) -> None:
        if self.dry_run:
            print("[dry-run] Rebuild")
            return
        self._require_mws()
        self.mws.Rebuild()

    def save(self) -> None:
        if self.dry_run:
            print("[dry-run] Save")
            return
        self._require_mws()
        self.mws.Save()

    def save_as(self, path: Any) -> None:
        resolved = Path(str(path)).resolve()
        if self.dry_run:
            print(f"[dry-run] SaveAs {resolved}")
            return
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self._require_mws()
        self.mws.SaveAs(str(resolved), True)

    def _require_mws(self) -> None:
        if self.mws is None:
            raise PlanError("CST project is not connected.")


def macro_units(command: dict[str, Any]) -> tuple[str, str]:
    fields = {
        "geometry": "Geometry",
        "frequency": "Frequency",
        "time": "Time",
        "temperature": "TemperatureUnit",
        "voltage": "Voltage",
        "current": "Current",
        "resistance": "Resistance",
        "conductance": "Conductance",
        "capacitance": "Capacitance",
        "inductance": "Inductance",
    }
    lines = ["With Units"]
    for key, cst_name in fields.items():
        if key in command:
            lines.append(f"    .{cst_name} {q(command[key])}")
    lines.append("End With")
    return "set units", indented(lines)


def macro_frequency_range(command: dict[str, Any]) -> tuple[str, str]:
    fmin = require(command, "fmin")
    fmax = require(command, "fmax")
    return "set frequency range", f"Solver.FrequencyRange {q(fmin)}, {q(fmax)}"


def macro_boundary(command: dict[str, Any]) -> tuple[str, str]:
    aliases = {
        "xmin": "Xmin",
        "xmax": "Xmax",
        "ymin": "Ymin",
        "ymax": "Ymax",
        "zmin": "Zmin",
        "zmax": "Zmax",
    }
    lines = ["With Boundary"]
    for key, cst_name in aliases.items():
        if key in command:
            lines.append(f"    .{cst_name} {q(command[key])}")
    if "apply_in_all_directions" in command:
        value = "True" if command["apply_in_all_directions"] else "False"
        lines.append(f"    .ApplyInAllDirections {q(value)}")
    lines.append("End With")
    return "set boundary conditions", indented(lines)


def macro_background(command: dict[str, Any]) -> tuple[str, str]:
    lines = ["With Background", "    .Reset"]
    fields = {
        "type": "Type",
        "epsilon": "Epsilon",
        "mue": "Mue",
        "xmin_space": "XminSpace",
        "xmax_space": "XmaxSpace",
        "ymin_space": "YminSpace",
        "ymax_space": "YmaxSpace",
        "zmin_space": "ZminSpace",
        "zmax_space": "ZmaxSpace",
    }
    for key, cst_name in fields.items():
        if key in command:
            lines.append(f"    .{cst_name} {q(command[key])}")
    lines.append("End With")
    return "set background", indented(lines)


def macro_material(command: dict[str, Any]) -> tuple[str, str]:
    name = require(command, "name")
    lines = [
        "With Material",
        "    .Reset",
        f"    .Name {q(name)}",
        f"    .Type {q(command.get('type', 'Normal'))}",
    ]
    fields = {
        "epsilon": "Epsilon",
        "mue": "Mue",
        "tand": "TanD",
        "sigma": "Sigma",
        "rho": "Rho",
    }
    for key, cst_name in fields.items():
        if key in command:
            lines.append(f"    .{cst_name} {q(command[key])}")
    if "color" in command:
        color = command["color"]
        if not isinstance(color, list) or len(color) != 3:
            raise PlanError("material.color must be [r, g, b].")
        lines.append(f"    .Colour {q(color[0])}, {q(color[1])}, {q(color[2])}")
    lines.append("    .Create")
    lines.append("End With")
    return f"create material {name}", indented(lines)


def macro_brick(command: dict[str, Any]) -> tuple[str, str]:
    name = require(command, "name")
    component = command.get("component", "component1")
    material = command.get("material", "Vacuum")
    xrange = expect_pair(command, "xrange")
    yrange = expect_pair(command, "yrange")
    zrange = expect_pair(command, "zrange")

    lines = [
        "With Brick",
        "    .Reset",
        f"    .Name {q(name)}",
        f"    .Component {q(component)}",
        f"    .Material {q(material)}",
        f"    .Xrange {q(xrange[0])}, {q(xrange[1])}",
        f"    .Yrange {q(yrange[0])}, {q(yrange[1])}",
        f"    .Zrange {q(zrange[0])}, {q(zrange[1])}",
        "    .Create",
        "End With",
    ]
    return f"create brick {name}", indented(lines)


def macro_cylinder(command: dict[str, Any]) -> tuple[str, str]:
    name = require(command, "name")
    component = command.get("component", "component1")
    material = command.get("material", "Vacuum")
    axis = command.get("axis", "z")
    radius = require(command, "radius")
    zrange = expect_pair(command, "zrange")
    xcenter = command.get("xcenter", 0)
    ycenter = command.get("ycenter", 0)

    lines = [
        "With Cylinder",
        "    .Reset",
        f"    .Name {q(name)}",
        f"    .Component {q(component)}",
        f"    .Material {q(material)}",
        f"    .Axis {q(axis)}",
        f"    .OuterRadius {q(radius)}",
        '    .InnerRadius "0"',
        f"    .Xcenter {q(xcenter)}",
        f"    .Ycenter {q(ycenter)}",
        f"    .Zrange {q(zrange[0])}, {q(zrange[1])}",
        "    .Create",
        "End With",
    ]
    return f"create cylinder {name}", indented(lines)


def macro_boolean(command: dict[str, Any]) -> tuple[str, str]:
    operation = require(command, "operation")
    target = require(command, "target")
    tool = require(command, "tool")
    allowed = {"add": "Add", "subtract": "Subtract", "intersect": "Intersect"}
    if operation not in allowed:
        raise PlanError("boolean.operation must be add, subtract, or intersect.")
    code = f'Solid.{allowed[operation]} {q(target)}, {q(tool)}'
    return f"boolean {operation}", code


def macro_discrete_port(command: dict[str, Any]) -> tuple[str, str]:
    name = command.get("name", "1")
    p1 = command.get("point1")
    p2 = command.get("point2")
    if not (isinstance(p1, list) and len(p1) == 3 and isinstance(p2, list) and len(p2) == 3):
        raise PlanError("discrete_port requires point1 and point2 as [x, y, z].")
    impedance = command.get("impedance", 50)
    lines = [
        "With DiscretePort",
        "    .Reset",
        f"    .PortNumber {q(name)}",
        f"    .Impedance {q(impedance)}",
        f"    .SetP1 {q(False)}, {q(p1[0])}, {q(p1[1])}, {q(p1[2])}",
        f"    .SetP2 {q(False)}, {q(p2[0])}, {q(p2[1])}, {q(p2[2])}",
        "    .Create",
        "End With",
    ]
    return f"create discrete port {name}", indented(lines)


def macro_solver_start(command: dict[str, Any]) -> tuple[str, str]:
    solver = command.get("solver")
    if solver == "frequency":
        return "start frequency solver", "FDSolver.Start"
    if solver == "time":
        return "start time solver", "Solver.Start"
    return "start solver", "Solver.Start"


def macro_export_touchstone(command: dict[str, Any]) -> tuple[str, str]:
    path = require(command, "path")
    lines = [
        "With TOUCHSTONE",
        "    .Reset",
        f"    .FileName {q(Path(str(path)).resolve())}",
        f"    .Impedance {q(command.get('impedance', 50))}",
        "    .Renormalize True",
        "    .Write",
        "End With",
    ]
    return "export touchstone", indented(lines)


MACRO_BUILDERS = {
    "units": macro_units,
    "frequency_range": macro_frequency_range,
    "boundary": macro_boundary,
    "background": macro_background,
    "material": macro_material,
    "brick": macro_brick,
    "cylinder": macro_cylinder,
    "boolean": macro_boolean,
    "discrete_port": macro_discrete_port,
    "solver_start": macro_solver_start,
    "export_touchstone": macro_export_touchstone,
}


def execute_commands(session: CSTSession, commands: list[Any]) -> None:
    for index, raw in enumerate(commands, start=1):
        if not isinstance(raw, dict):
            raise PlanError(f"commands[{index}] must be an object.")
        command = raw
        op = command.get("op")
        if not isinstance(op, str):
            raise PlanError(f"commands[{index}] requires string field 'op'.")

        if op == "vba_history":
            name = str(command.get("name", f"custom macro {index}"))
            code = require(command, "code")
            session.add_history(name, str(code))
        elif op == "parameter":
            session.store_parameter(str(require(command, "name")), require(command, "value"))
        elif op == "rebuild":
            session.rebuild()
        elif op == "save":
            if "path" in command:
                session.save_as(command["path"])
            else:
                session.save()
        elif op == "sweep":
            execute_sweep(session, command)
        elif op in MACRO_BUILDERS:
            name, code = MACRO_BUILDERS[op](command)
            session.add_history(str(command.get("name_for_history", name)), code)
        else:
            allowed = ", ".join(sorted([*MACRO_BUILDERS.keys(), "parameter", "rebuild", "save", "sweep", "vba_history"]))
            raise PlanError(f"Unknown op '{op}'. Allowed ops: {allowed}")


def execute_sweep(session: CSTSession, command: dict[str, Any]) -> None:
    parameter = str(require(command, "parameter"))
    values = require(command, "values")
    nested = require(command, "commands")
    save_template = command.get("save_template")

    if not isinstance(values, list) or not values:
        raise PlanError("sweep.values must be a non-empty list.")
    if not isinstance(nested, list):
        raise PlanError("sweep.commands must be a list.")

    for value in values:
        session.store_parameter(parameter, value)
        session.rebuild()
        execute_commands(session, nested)
        if save_template:
            path = str(save_template).format(parameter=parameter, value=value)
            session.save_as(path)


def run_plan(plan: dict[str, Any], args: argparse.Namespace) -> None:
    project = plan.get("project", {"mode": "new"})
    if not isinstance(project, dict):
        raise PlanError("project must be an object.")

    session = CSTSession(args.dry_run, args.prog_id, args.visible)
    session.connect_project(project)

    parameters = plan.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PlanError("parameters must be an object.")
    for name, value in parameters.items():
        session.store_parameter(str(name), value)

    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        raise PlanError("commands must be a list.")
    execute_commands(session, commands)

    if project.get("save_as"):
        session.save_as(project["save_as"])
    elif project.get("save", False):
        session.save()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CST command plans through COM.")
    parser.add_argument("plan", type=Path, help="Path to a JSON/YAML CST command plan.")
    parser.add_argument("--dry-run", action="store_true", help="Print generated actions without opening CST.")
    parser.add_argument("--visible", action="store_true", help="Ask CST to show its UI during execution.")
    parser.add_argument(
        "--prog-id",
        default="CSTStudio.Application",
        help="CST COM ProgID. Default: CSTStudio.Application",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        plan = load_plan(args.plan)
        run_plan(plan, args)
    except PlanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
