#!/usr/bin/env python
"""
CST Vibe Runner

Runs a small JSON/YAML command plan against CST Studio Suite through the
Windows COM interface. The plan is intended to be produced by a local LLM or
written by hand. Use --dry-run first to inspect the generated CST macros.
"""

from __future__ import annotations

import argparse
import ast
import copy
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from cst_plan_defaults import normalize_boundary_value


class PlanError(Exception):
    """Raised when the command plan is invalid."""


def load_plan(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PlanError(f"Plan file not found: {path}")

    text = path.read_text(encoding="utf-8-sig")
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


def fmt_number(value: float) -> str:
    return f"{value:.12g}"


def eval_numeric_expression(value: Any, context: dict[str, float]) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        raise PlanError("Numeric expression is empty.")
    try:
        return float(text)
    except ValueError:
        pass

    operators = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.USub: lambda a: -a,
        ast.UAdd: lambda a: a,
    }

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in context:
                raise PlanError(f"Unknown numeric parameter '{node.id}' in expression '{text}'.")
            return context[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.operand))
        raise PlanError(f"Unsupported numeric expression: {text}")

    try:
        parsed = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise PlanError(f"Invalid numeric expression: {text}") from exc
    return visit(parsed)


def resolve_numeric(value: Any, context: dict[str, float]) -> str:
    return fmt_number(eval_numeric_expression(value, context))


def build_numeric_context(parameters: dict[str, Any]) -> dict[str, float]:
    context: dict[str, float] = {}
    pending = dict(parameters)
    while pending:
        progressed = False
        for key, value in list(pending.items()):
            try:
                context[str(key)] = eval_numeric_expression(value, context)
            except PlanError:
                continue
            del pending[key]
            progressed = True
        if not progressed:
            names = ", ".join(str(name) for name in pending)
            raise PlanError(f"Could not resolve numeric parameters: {names}")
    return context


def resolve_pair(values: list[Any], context: dict[str, float]) -> list[str]:
    return [resolve_numeric(values[0], context), resolve_numeric(values[1], context)]


def resolve_point(values: Any, context: dict[str, float], field: str) -> list[str]:
    if not isinstance(values, list) or len(values) != 3:
        raise PlanError(f"{field} must be [x, y, z].")
    return [resolve_numeric(item, context) for item in values]


def resolve_command_numbers(command: dict[str, Any], context: dict[str, float]) -> None:
    op = command.get("op")
    if op == "frequency_range":
        command["fmin"] = resolve_numeric(require(command, "fmin"), context)
        command["fmax"] = resolve_numeric(require(command, "fmax"), context)
    elif op == "brick":
        command["xrange"] = resolve_pair(expect_pair(command, "xrange"), context)
        command["yrange"] = resolve_pair(expect_pair(command, "yrange"), context)
        command["zrange"] = resolve_pair(expect_pair(command, "zrange"), context)
    elif op == "cylinder":
        command["radius"] = resolve_numeric(require(command, "radius"), context)
        command["zrange"] = resolve_pair(expect_pair(command, "zrange"), context)
        command["xcenter"] = resolve_numeric(command.get("xcenter", 0), context)
        command["ycenter"] = resolve_numeric(command.get("ycenter", 0), context)
    elif op == "discrete_port":
        command["point1"] = resolve_point(command.get("point1"), context, "discrete_port.point1")
        command["point2"] = resolve_point(command.get("point2"), context, "discrete_port.point2")
    elif op == "material":
        for key in ("epsilon", "mue", "tand", "sigma", "rho"):
            if key in command:
                command[key] = resolve_numeric(command[key], context)
    elif op == "background":
        for key in ("epsilon", "mue", "xmin_space", "xmax_space", "ymin_space", "ymax_space", "zmin_space", "zmax_space"):
            if key in command:
                command[key] = resolve_numeric(command[key], context)
    elif op == "sweep":
        nested = require(command, "commands")
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    resolve_command_numbers(item, context)
    elif op == "case_sweep":
        nested = require(command, "commands")
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    resolve_command_numbers(item, context)


def resolve_plan_numbers(commands: list[Any], context: dict[str, float]) -> None:
    for raw in commands:
        if isinstance(raw, dict):
            resolve_command_numbers(raw, context)


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


def safe_slug(value: Any, fallback: str = "cst_run") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9가-힣_.-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_.-")
    return text or fallback


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_run_dir(args: argparse.Namespace, plan: dict[str, Any]) -> Path | None:
    if args.run_dir:
        return Path(args.run_dir).resolve()
    if not args.package_run:
        return None

    parameters = plan.get("parameters", {})
    design_id = plan.get("design_id") or plan.get("name") or "mesh_unitcell"
    if isinstance(parameters, dict):
        suffix_parts = []
        for key in ("length", "width", "thickness", "p", "sub_t", "patch_w"):
            if key in parameters:
                suffix_parts.append(f"{key}{parameters[key]}")
        if suffix_parts:
            design_id = f"{design_id}_{'_'.join(suffix_parts)}"

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return (Path(args.runs_root).resolve() / f"{timestamp}_{safe_slug(design_id)}")


def prepare_run_package(plan: dict[str, Any], args: argparse.Namespace) -> Path | None:
    run_dir = make_run_dir(args, plan)
    if run_dir is None:
        return None

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "exports").mkdir(exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)

    project = plan.setdefault("project", {"mode": "new"})
    if not isinstance(project, dict):
        raise PlanError("project must be an object.")
    project["save_as"] = str(run_dir / "cst_project.cst")

    parameters = plan.get("parameters", {})
    commands = plan.get("commands", [])
    write_json(run_dir / "input_plan.json", plan)
    write_json(run_dir / "design_params.json", parameters if isinstance(parameters, dict) else {})
    write_json(
        run_dir / "summary.json",
        {
            "status": "prepared",
            "source": "cst",
            "tool": "CST Vibe Runner",
            "run_dir": str(run_dir),
            "cst_project": "cst_project.cst",
            "parameters_file": "design_params.json",
            "input_plan_file": "input_plan.json",
            "exports_dir": "exports",
            "command_count": len(commands) if isinstance(commands, list) else None,
            "notes": [
                "This package is the standard handoff format for later CST-vs-Python comparison.",
                "Put exported CST result files such as Touchstone or CSV under exports/.",
            ],
        },
    )
    (run_dir / "exports" / "README.txt").write_text(
        "Place CST exported results here, for example sparameters.s2p, s11.csv, s21.csv.\n",
        encoding="utf-8",
    )
    print(f"[package] Run folder: {run_dir}")
    print(f"[package] CST project target: {run_dir / 'cst_project.cst'}")
    return run_dir


class CSTSession:
    def __init__(
        self,
        dry_run: bool,
        prog_id: str,
        visible: bool,
        continue_on_error: bool = False,
        skip_saves: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.prog_id = prog_id
        self.visible = visible
        self.continue_on_error = continue_on_error
        self.skip_saves = skip_saves
        self.errors: list[str] = []
        self.cst = None
        self.mws = None

    def connect_project(self, project: dict[str, Any]) -> None:
        mode = project.get("mode", "new")
        path = project.get("path")

        if self.dry_run:
            print(f"[dry-run] COM Dispatch: {self.prog_id}")
            if mode == "open":
                print(f"[dry-run] Open CST project: {Path(path).resolve() if path else path}")
            elif mode == "active":
                print("[dry-run] Attach to current active CST Microwave Studio project")
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

        self.cst = self.dispatch_cst(win32com, prefer_running=(mode == "active"))
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
        elif mode == "active":
            self.mws = self.active_3d_project()
        else:
            raise PlanError("project.mode must be 'new', 'open', or 'active'.")

    def active_3d_project(self) -> Any:
        errors: list[str] = []
        for method_name in ("Active3D", "ActiveMWS", "ActiveProject"):
            try:
                attr = getattr(self.cst, method_name)
            except Exception as exc:
                errors.append(f"{method_name} lookup failed: {exc}")
                continue
            for call_style, project in self.active_project_candidates(method_name, attr, errors):
                if self.is_cst_project_object(project):
                    print(f"[cst] Attached to current CST project via {method_name} {call_style}")
                    return project
                errors.append(f"{method_name} {call_style} returned {type(project).__name__}: {project!r}")
            try:
                import pythoncom  # type: ignore

                dispid = self.cst._oleobj_.GetIDsOfNames(method_name)
                for dispatch_type, label in (
                    (pythoncom.DISPATCH_PROPERTYGET, "raw property"),
                    (pythoncom.DISPATCH_METHOD, "raw method"),
                ):
                    try:
                        project = self.cst._oleobj_.Invoke(dispid, 0, dispatch_type, False)
                    except Exception as exc:
                        errors.append(f"{method_name} {label} failed: {exc}")
                        continue
                    if self.is_cst_project_object(project):
                        print(f"[cst] Attached to current CST project via {method_name} {label}")
                        return project
                    errors.append(f"{method_name} {label} returned {type(project).__name__}: {project!r}")
            except Exception as exc:
                errors.append(f"{method_name} raw COM lookup failed: {exc}")
        raise PlanError(
            "Could not attach to the currently open CST project. "
            "CST returned no usable project object. Open a Microwave Studio 3D project, "
            "or use the main simulation button to create a new project.\n"
            + "\n".join(errors)
        )

    def active_project_candidates(self, method_name: str, attr: Any, errors: list[str]) -> list[tuple[str, Any]]:
        candidates: list[tuple[str, Any]] = []
        if callable(attr):
            try:
                candidates.append(("call", attr()))
            except Exception as exc:
                errors.append(f"{method_name} call failed: {exc}")
        else:
            candidates.append(("property", attr))
        return candidates

    def is_cst_project_object(self, value: Any) -> bool:
        if value is None or isinstance(value, bool):
            return False
        if hasattr(value, "_oleobj_"):
            return True
        return any(hasattr(value, name) for name in ("AddToHistory", "Rebuild", "SaveAs", "Save"))

    def dispatch_cst(self, win32com: Any, prefer_running: bool = False) -> Any:
        candidates = [self.prog_id]
        for prog_id in (
            "CSTStudio.Application.2025",
            "CSTStudio.Application",
            "CSTStudio.Application.2024",
            "CSTStudio.Application.2023",
        ):
            if prog_id not in candidates:
                candidates.append(prog_id)

        errors = []
        for prog_id in candidates:
            if prefer_running:
                try:
                    cst = win32com.client.GetActiveObject(prog_id)
                    self.prog_id = prog_id
                    print(f"[cst] Connected running ProgID: {prog_id}")
                    return cst
                except Exception as exc:
                    errors.append(f"{prog_id} GetActiveObject: {exc}")
            try:
                cst = win32com.client.Dispatch(prog_id)
            except Exception as exc:
                errors.append(f"{prog_id}: {exc}")
                continue
            self.prog_id = prog_id
            print(f"[cst] Connected ProgID: {prog_id}")
            return cst

        raise PlanError(
            "Could not start CST through COM. CST 2025 is the default, but no "
            "registered CST COM ProgID responded.\n"
            "Tried:\n- "
            + "\n- ".join(errors)
        )

    def add_history(self, name: str, code: str) -> None:
        name_text = str(name).strip()
        code_text = str(code).strip()
        if not name_text or not code_text:
            raise PlanError(
                "AddToHistory requires non-empty name and code. "
                f"name={name_text!r}, code_length={len(code_text)}"
            )
        if self.dry_run:
            print(f"\n--- AddToHistory: {name_text} ---")
            print(code_text)
            print("--- end ---")
            return
        self._require_mws()
        print(f"[cst] AddToHistory: {name_text}")
        print(f"[cst] AddToHistory args: name_length={len(name_text)}, code_length={len(code_text)}")
        try:
            self._add_to_history(name_text, code_text)
        except Exception as exc:
            raise PlanError(
                "CST AddToHistory failed. CST is connected, but it rejected this "
                "macro block.\n\n"
                f"History name:\n{name_text}\n\n"
                f"Macro code:\n{code_text}\n\n"
                f"Original error:\n{exc}"
            ) from exc

    def _add_to_history(self, name: str, code: str) -> None:
        errors: list[str] = []

        try:
            self.mws.AddToHistory(name, code)
            return
        except Exception as exc:
            errors.append(f"normal call failed: {exc}")

        try:
            import pythoncom  # type: ignore

            dispid = self.mws._oleobj_.GetIDsOfNames("AddToHistory")
            self.mws._oleobj_.Invoke(
                dispid,
                0,
                pythoncom.DISPATCH_METHOD,
                False,
                name,
                code,
            )
            return
        except Exception as exc:
            errors.append(f"raw COM Invoke failed: {exc}")

        joined = "\n".join(errors)
        raise PlanError(
            "AddToHistory could not be called with either pywin32 dispatch style.\n"
            "This usually means CST 2025 is receiving the method call with the "
            "wrong argument binding, even though the Python strings are not empty.\n"
            f"name={name!r}, code_length={len(code)}\n{joined}"
        )

    def store_parameter(self, name: str, value: Any) -> None:
        print(f"[param] {name} = {value}")
        if self.dry_run:
            print(f"[dry-run] StoreParameter {name} = {value}")
            return
        self._require_mws()
        try:
            self.mws.StoreParameter(str(name), str(value))
        except Exception as exc:
            raise PlanError(
                "CST StoreParameter failed. The parameter was not applied.\n"
                f"name={name!r}, value={value!r}\n"
                f"Original error:\n{exc}"
            ) from exc

    def rebuild(self) -> None:
        if self.dry_run:
            print("[dry-run] Rebuild")
            return
        self._require_mws()
        errors: list[str] = []
        try:
            self.mws.Rebuild()
            print("[cst] Rebuild completed")
            return
        except Exception as exc:
            errors.append(f"mws.Rebuild() failed: {exc}")
        try:
            import pythoncom  # type: ignore

            self.mws._oleobj_.Invoke(
                self.mws._oleobj_.GetIDsOfNames("Rebuild"),
                0,
                pythoncom.DISPATCH_METHOD,
                False,
            )
            print("[cst] Rebuild completed by raw COM")
            return
        except Exception as exc:
            errors.append(f"raw COM Rebuild failed: {exc}")
        try:
            self.add_history("rebuild model", "Rebuild")
            return
        except Exception as exc:
            errors.append(f"AddToHistory Rebuild fallback failed: {exc}")
        raise PlanError("CST Rebuild failed.\n" + "\n".join(errors))

    def start_solver(self, solver: str | None = None) -> None:
        order = ["Solver", "FDSolver"]
        if solver == "frequency_direct":
            order = ["FDSolver", "Solver"]
        if solver == "time":
            order = ["Solver"]
        if self.dry_run:
            print(f"[dry-run] Start solver via {order[0]}.Start")
            return
        self._require_mws()
        errors: list[str] = []
        for object_name in order:
            try:
                solver_object = self.get_cst_child_object(object_name)
            except Exception as exc:
                errors.append(f"{object_name} object lookup failed: {exc}")
                continue
            for method_name in ("Start", "start"):
                try:
                    getattr(solver_object, method_name)()
                    print(f"[cst] {object_name}.{method_name} completed")
                    return
                except Exception as exc:
                    errors.append(f"{object_name}.{method_name} failed: {exc}")
            try:
                solver_object._oleobj_.Invoke(
                    solver_object._oleobj_.GetIDsOfNames("Start"),
                    0,
                    1,
                    False,
                )
                print(f"[cst] {object_name}.Start completed by raw COM")
                return
            except Exception as exc:
                errors.append(f"{object_name}.Start raw COM failed: {exc}")
        name, code = macro_solver_start({"solver": solver})
        try:
            self.add_history(name, code)
            return
        except Exception as exc:
            errors.append(f"AddToHistory fallback failed: {exc}")
        raise PlanError("CST solver start failed.\n" + "\n".join(errors))

    def get_cst_child_object(self, object_name: str) -> Any:
        attr = getattr(self.mws, object_name)
        errors: list[str] = []
        try:
            obj = attr()
            if obj is not None:
                return obj
        except Exception as exc:
            errors.append(f"{object_name}() failed: {exc}")
        if hasattr(attr, "Start") or hasattr(attr, "start"):
            return attr
        try:
            import pythoncom  # type: ignore

            return self.mws._oleobj_.Invoke(
                self.mws._oleobj_.GetIDsOfNames(object_name),
                0,
                pythoncom.DISPATCH_METHOD,
                False,
            )
        except Exception as exc:
            errors.append(f"raw COM method invoke failed: {exc}")
        try:
            import pythoncom  # type: ignore

            return self.mws._oleobj_.Invoke(
                self.mws._oleobj_.GetIDsOfNames(object_name),
                0,
                pythoncom.DISPATCH_PROPERTYGET,
                False,
            )
        except Exception as exc:
            errors.append(f"raw COM property invoke failed: {exc}")
        raise PlanError("; ".join(errors))

    def save(self) -> None:
        if self.skip_saves:
            print("[save] Save skipped by --no-project-save.")
            return
        if self.dry_run:
            print("[dry-run] Save")
            return
        self._require_mws()
        self.mws.Save()

    def save_as(self, path: Any) -> None:
        resolved = Path(str(path)).resolve()
        if self.skip_saves:
            print(f"[save] SaveAs skipped by --no-project-save: {resolved}")
            return
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


def macro_solver_type(command: dict[str, Any]) -> tuple[str, str]:
    solver_type = command.get("type", "HF Time Domain")
    return "set solver type", f"ChangeSolverType {q(solver_type)}"


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
            lines.append(f"    .{cst_name} {q(normalize_boundary_value(command[key]))}")
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


def macro_floquet_port(command: dict[str, Any]) -> tuple[str, str]:
    modes = command.get("modes", command.get("mode_count", 2))
    theta = command.get("theta", 0)
    phi = command.get("phi", 0)
    polarization_angle = command.get("polarization_angle", 0)
    ports = command.get("ports", ["Zmin", "Zmax"])
    if not isinstance(ports, list) or not ports:
        raise PlanError("floquet_port.ports must be a non-empty list.")

    lines = [
        "With FloquetPort",
        "    .Reset",
        f"    .SetDialogTheta {q(theta)}",
        f"    .SetDialogPhi {q(phi)}",
        f"    .SetPolarizationIndependentOfScanAnglePhi {q(polarization_angle)}, {q(False)}",
        '    .SetSortCode "+beta/pw"',
        f"    .SetCustomizedListFlag {q(False)}",
    ]
    for port in ports:
        lines.extend(
            [
                f"    .Port {q(port)}",
                f"    .SetNumberOfModesConsidered {q(modes)}",
                '    .SetDistanceToReferencePlane "0.0"',
                f"    .SetUseCircularPolarization {q(False)}",
            ]
        )
    lines.extend(
        [
            "End With",
            "With Boundary",
            f"    .SetPeriodicBoundaryAngles {q(theta)}, {q(phi)}",
            '    .SetPeriodicBoundaryAnglesDirection "outward"',
            "End With",
        ]
    )
    return f"set floquet port modes {modes}", indented(lines)


def macro_solver_start(command: dict[str, Any]) -> tuple[str, str]:
    solver = command.get("solver")
    if solver == "frequency_direct":
        return "start frequency solver", indented(["With FDSolver", "    .Start", "End With"])
    if solver == "frequency":
        return "start solver", indented(["With Solver", "    .Start", "End With"])
    if solver == "time":
        return "start time solver", indented(["With Solver", "    .Start", "End With"])
    return "start solver", indented(["With Solver", "    .Start", "End With"])


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
    "solver_type": macro_solver_type,
    "boundary": macro_boundary,
    "background": macro_background,
    "material": macro_material,
    "brick": macro_brick,
    "cylinder": macro_cylinder,
    "boolean": macro_boolean,
    "discrete_port": macro_discrete_port,
    "floquet_port": macro_floquet_port,
    "solver_start": macro_solver_start,
    "export_touchstone": macro_export_touchstone,
}


def execute_commands(session: CSTSession, commands: list[Any]) -> None:
    for index, raw in enumerate(commands, start=1):
        op = raw.get("op") if isinstance(raw, dict) else "<invalid>"
        try:
            execute_one_command(session, raw, index)
            print(f"[ok] commands[{index}] op={op}")
        except Exception as exc:
            message = f"commands[{index}] op={op} failed: {exc}"
            if not session.continue_on_error:
                raise
            session.errors.append(message)
            print(f"\n[diagnostic-error] {message}\n", file=sys.stderr)


def execute_one_command(session: CSTSession, raw: Any, index: int) -> None:
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
    elif op == "case_sweep":
        execute_case_sweep(session, command)
    elif op == "solver_start":
        session.start_solver(command.get("solver"))
    elif op in MACRO_BUILDERS:
        name, code = MACRO_BUILDERS[op](command)
        session.add_history(str(command.get("name_for_history", name)), code)
    else:
        allowed = ", ".join(sorted([*MACRO_BUILDERS.keys(), "case_sweep", "parameter", "rebuild", "save", "sweep", "vba_history"]))
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


def format_case_value(value: Any, data: dict[str, Any]) -> Any:
    if isinstance(value, str):
        try:
            return value.format(**data)
        except KeyError:
            return value
    if isinstance(value, list):
        return [format_case_value(item, data) for item in value]
    if isinstance(value, dict):
        return {key: format_case_value(item, data) for key, item in value.items()}
    return value


def case_slug(updates: dict[str, Any]) -> str:
    return "_".join(f"{safe_slug(key)}{safe_slug(value)}" for key, value in updates.items()) or "case"


def execute_case_sweep(session: CSTSession, command: dict[str, Any]) -> None:
    cases = require(command, "cases")
    nested = require(command, "commands")
    if not isinstance(cases, list) or not cases:
        raise PlanError("case_sweep.cases must be a non-empty list.")
    if not isinstance(nested, list):
        raise PlanError("case_sweep.commands must be a list.")

    for index, raw_case in enumerate(cases, start=1):
        if not isinstance(raw_case, dict):
            raise PlanError("Each case_sweep case must be an object.")
        slug = case_slug(raw_case)
        print(f"[case_sweep] case {index}/{len(cases)}: {raw_case}")
        for name, value in raw_case.items():
            session.store_parameter(str(name), value)
        session.rebuild()
        data = {"case_index": f"{index:03d}", "case_number": index, "case_slug": slug, **raw_case}
        for nested_index, nested_command in enumerate(nested, start=1):
            execute_one_command(session, format_case_value(copy.deepcopy(nested_command), data), nested_index)


def run_plan(plan: dict[str, Any], args: argparse.Namespace) -> None:
    plan = copy.deepcopy(plan)
    run_dir = prepare_run_package(plan, args)
    project = plan.get("project", {"mode": "new"})
    if not isinstance(project, dict):
        raise PlanError("project must be an object.")

    session = CSTSession(args.dry_run, args.prog_id, args.visible, args.continue_on_error, args.no_project_save)
    session.connect_project(project)

    parameters = plan.get("parameters", {})
    if not isinstance(parameters, dict):
        raise PlanError("parameters must be an object.")

    commands = plan.get("commands", [])
    if not isinstance(commands, list):
        raise PlanError("commands must be a list.")
    numeric_context = build_numeric_context(parameters)
    if numeric_context:
        for name, value in numeric_context.items():
            print(f"[param] {name} = {fmt_number(value)}")
        if args.keep_expressions:
            print("[param] CST parameter expressions kept for solver/sweep automation.")
        else:
            resolve_plan_numbers(commands, numeric_context)
            print("[param] CST macro expressions resolved to numbers; no New Parameter dialog is needed.")
    if args.store_parameters:
        for name, value in parameters.items():
            session.store_parameter(str(name), value)
    execute_commands(session, commands)

    if args.no_project_save:
        print("[save] Project save skipped by --no-project-save.")
    elif project.get("save_as"):
        session.save_as(project["save_as"])
    elif project.get("save", False):
        session.save()

    if session.errors:
        print("\n=== Diagnostic summary ===", file=sys.stderr)
        for item in session.errors:
            print(f"- {item}", file=sys.stderr)
        if run_dir is not None:
            write_json(
                run_dir / "summary.json",
                {
                    "status": "failed",
                    "source": "cst",
                    "tool": "CST Vibe Runner",
                    "run_dir": str(run_dir),
                    "cst_project": "cst_project.cst",
                    "parameters_file": "design_params.json",
                    "input_plan_file": "input_plan.json",
                    "exports_dir": "exports",
                    "errors": session.errors,
                },
            )
        raise PlanError(f"{len(session.errors)} command(s) failed. See diagnostic summary above.")

    if run_dir is not None:
        write_json(
            run_dir / "summary.json",
            {
                "status": "dry_run_completed" if args.dry_run else "completed",
                "source": "cst",
                "tool": "CST Vibe Runner",
                "run_dir": str(run_dir),
                "cst_project": "cst_project.cst",
                "parameters_file": "design_params.json",
                "input_plan_file": "input_plan.json",
                "exports_dir": "exports",
                "result_files": {},
            },
        )
        print(f"[package] Summary updated: {run_dir / 'summary.json'}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CST command plans through COM.")
    parser.add_argument("plan", type=Path, help="Path to a JSON/YAML CST command plan.")
    parser.add_argument("--dry-run", action="store_true", help="Print generated actions without opening CST.")
    parser.add_argument("--visible", action="store_true", help="Ask CST to show its UI during execution.")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Diagnostic mode: keep running later commands after a command fails.",
    )
    parser.add_argument(
        "--package-run",
        action="store_true",
        help="Create a standard runs/<timestamp> package for CST-vs-Python comparison.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="Create/use this exact run folder and write input_plan/design_params/summary there.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("runs"),
        help="Root folder for --package-run. Default: runs",
    )
    parser.add_argument(
        "--prog-id",
        default="CSTStudio.Application.2025",
        help="CST COM ProgID. Default: CSTStudio.Application.2025",
    )
    parser.add_argument(
        "--store-parameters",
        action="store_true",
        help="Also create CST parameters with StoreParameter. Off by default to avoid CST New Parameter popups.",
    )
    parser.add_argument(
        "--keep-expressions",
        action="store_true",
        help="Keep parameter expressions such as length-width in CST macros. Use with --store-parameters for sweeps.",
    )
    parser.add_argument(
        "--no-project-save",
        action="store_true",
        help="Run commands without saving a CST project file. Useful for diagnostics.",
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
