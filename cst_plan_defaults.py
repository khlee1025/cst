from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any


DEFAULT_SOLVER_TYPE = "HF Time Domain"
DEFAULT_FLOQUET_MODES = "2"
DEFAULT_BACKGROUND = {"op": "background", "type": "Normal", "epsilon": "1", "mue": "1"}
DEFAULT_BOUNDARY = {
    "op": "boundary",
    "xmin": "unit cell",
    "xmax": "unit cell",
    "ymin": "unit cell",
    "ymax": "unit cell",
    "zmin": "expanded open",
    "zmax": "expanded open",
}


def normalize_boundary_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = re.sub(r"[\s_()\-]+", " ", value.strip().lower()).strip()
    open_add_aliases = {
        "open add",
        "open add space",
        "open added space",
        "open with add space",
        "open with added space",
        "open pml add space",
        "expanded open",
    }
    if normalized in open_add_aliases:
        return "expanded open"
    return value


def normalize_simulation_setup(
    base_plan: dict[str, Any],
    solver_type: str = DEFAULT_SOLVER_TYPE,
    floquet_modes: str = DEFAULT_FLOQUET_MODES,
) -> dict[str, Any]:
    plan = copy.deepcopy(base_plan)
    ensure_default_solver_type(plan, solver_type)
    ensure_default_background(plan)
    ensure_default_boundary(plan)
    ensure_default_floquet(plan, floquet_modes)
    return plan


def prepare_solver_plan(
    base_plan: dict[str, Any],
    export_path: Path | None = None,
    include_solver: bool = True,
    solver_type: str = DEFAULT_SOLVER_TYPE,
    floquet_modes: str = DEFAULT_FLOQUET_MODES,
) -> dict[str, Any]:
    plan = normalize_simulation_setup(base_plan, solver_type, floquet_modes)
    commands = plan.get("commands")
    if not isinstance(commands, list):
        raise ValueError("commands는 list여야 합니다.")

    filtered = [
        item
        for item in commands
        if not (isinstance(item, dict) and item.get("op") in {"save", "solver_start", "export_touchstone"})
    ]
    if not any(isinstance(item, dict) and item.get("op") == "rebuild" for item in filtered):
        filtered.append({"op": "rebuild"})
    if include_solver:
        filtered.append({"op": "solver_start", "solver": solver_kind_from_plan(plan)})
    if export_path is not None:
        filtered.append({"op": "export_touchstone", "path": str(export_path), "impedance": 50})
    plan["commands"] = filtered

    project = plan.setdefault("project", {"mode": "new"})
    if isinstance(project, dict) and export_path is not None:
        project["save_as"] = str(export_path.parents[1] / "cst_project.cst")
    return plan


def ensure_default_solver_type(plan: dict[str, Any], solver_type: str = DEFAULT_SOLVER_TYPE) -> dict[str, Any]:
    commands = plan.get("commands")
    if not isinstance(commands, list):
        return plan
    if any(isinstance(item, dict) and item.get("op") == "solver_type" for item in commands):
        return plan
    insert_at = 0
    for index, item in enumerate(commands):
        if isinstance(item, dict) and item.get("op") == "units":
            insert_at = index + 1
    commands.insert(insert_at, {"op": "solver_type", "type": solver_type or DEFAULT_SOLVER_TYPE})
    return plan


def ensure_default_background(plan: dict[str, Any]) -> dict[str, Any]:
    commands = plan.get("commands")
    if not isinstance(commands, list):
        return plan
    if any(isinstance(item, dict) and item.get("op") == "background" for item in commands):
        return plan
    insert_at = 0
    for index, item in enumerate(commands):
        if isinstance(item, dict) and item.get("op") in {"units", "solver_type"}:
            insert_at = index + 1
    commands.insert(insert_at, copy.deepcopy(DEFAULT_BACKGROUND))
    return plan


def ensure_default_boundary(plan: dict[str, Any]) -> dict[str, Any]:
    commands = plan.get("commands")
    if not isinstance(commands, list):
        return plan
    if any(isinstance(item, dict) and item.get("op") == "boundary" for item in commands):
        normalize_boundary_defaults(commands)
        return plan
    insert_at = 0
    for index, item in enumerate(commands):
        if isinstance(item, dict) and item.get("op") in {"units", "frequency_range"}:
            insert_at = index + 1
    commands.insert(insert_at, copy.deepcopy(DEFAULT_BOUNDARY))
    return plan


def normalize_boundary_defaults(commands: list[Any]) -> None:
    for item in commands:
        if not (isinstance(item, dict) and item.get("op") == "boundary"):
            continue
        for key in ("xmin", "xmax", "ymin", "ymax"):
            item.setdefault(key, "unit cell")
        for key in ("zmin", "zmax"):
            value = normalize_boundary_value(item.get(key, ""))
            if value == "" or str(value).strip().lower() in {"open", "expanded open"}:
                item[key] = "expanded open"


def ensure_default_floquet(
    plan: dict[str, Any],
    floquet_modes: str = DEFAULT_FLOQUET_MODES,
) -> dict[str, Any]:
    commands = plan.get("commands")
    if not isinstance(commands, list):
        return plan
    if any(isinstance(item, dict) and item.get("op") == "floquet_port" for item in commands):
        return plan
    insert_at = 0
    for index, item in enumerate(commands):
        if isinstance(item, dict) and item.get("op") == "boundary":
            insert_at = index + 1
    commands.insert(
        insert_at,
        {
            "op": "floquet_port",
            "modes": floquet_modes or DEFAULT_FLOQUET_MODES,
            "ports": ["Zmin", "Zmax"],
            "theta": "0",
            "phi": "0",
        },
    )
    return plan


def solver_kind_from_plan(plan: dict[str, Any]) -> str:
    commands = plan.get("commands", [])
    if isinstance(commands, list):
        for item in commands:
            if isinstance(item, dict) and item.get("op") == "solver_type":
                if "time" in str(item.get("type", "")).lower():
                    return "time"
    return "frequency"


def simulation_readiness_report(plan: dict[str, Any]) -> tuple[list[str], bool]:
    messages: list[str] = []
    commands = plan.get("commands", [])
    params = plan.get("parameters", {})
    if not isinstance(commands, list):
        return ["[error] commands가 list가 아닙니다."], False
    if not isinstance(params, dict):
        return ["[error] parameters가 object가 아닙니다."], False

    ops = [item.get("op") for item in commands if isinstance(item, dict)]
    project = plan.get("project", {})
    project_mode = project.get("mode") if isinstance(project, dict) else "new"
    active_project = project_mode == "active"

    def first_command(op: str) -> dict[str, Any] | None:
        for item in commands:
            if isinstance(item, dict) and item.get("op") == op:
                return item
        return None

    def require_op(op: str, label: str) -> dict[str, Any] | None:
        item = first_command(op)
        if item is None:
            messages.append(f"[error] {label} 명령이 없습니다.")
        else:
            messages.append(f"[ok] {label} 명령 있음")
        return item

    if active_project:
        messages.append("[info] 현재 열려 있는 CST 프로젝트에 붙는 모드라서 Units/geometry brick 검사는 생략합니다.")
    else:
        require_op("units", "Units")
        require_op("frequency_range", "Frequency range")
    solver_type = require_op("solver_type", "Solver type")
    background = require_op("background", "Background")
    boundary = require_op("boundary", "Boundary")
    floquet = require_op("floquet_port", "Floquet port")
    require_op("rebuild", "Rebuild")
    solver_start = require_op("solver_start", "Solver Start")

    append_solver_checks(solver_type, messages)
    append_background_checks(background, messages)
    append_boundary_checks(boundary, messages)
    append_floquet_checks(floquet, messages)
    append_geometry_checks(params, ops, messages, active_project)

    if "export_touchstone" in ops:
        messages.append("[error] 시뮬레이션 시작 플랜에 export_touchstone이 남아 있습니다. 해석 시작 전에는 제거해야 합니다.")
    else:
        messages.append("[ok] Touchstone export 없음")

    if solver_start is not None:
        solver_kind = str(solver_start.get("solver", "")).strip()
        if solver_kind not in {"time", "frequency", "frequency_direct"}:
            messages.append(f"[warn] solver_start.solver 값 확인 필요: {solver_kind}")
        else:
            messages.append(f"[ok] solver_start.solver={solver_kind}")

    return messages, not any(line.startswith("[error]") for line in messages)


def append_solver_checks(solver_type: dict[str, Any] | None, messages: list[str]) -> None:
    if solver_type is None:
        return
    solver_name = str(solver_type.get("type", "")).strip()
    if solver_name not in {"HF Time Domain", "HF Frequency Domain"}:
        messages.append(f"[warn] Solver type이 예상값과 다릅니다: {solver_name}")
    else:
        messages.append(f"[ok] Solver type = {solver_name}")


def append_background_checks(background: dict[str, Any] | None, messages: list[str]) -> None:
    if background is None:
        return
    bg_type = str(background.get("type", "")).strip().lower()
    eps = str(background.get("epsilon", "")).strip()
    mu = str(background.get("mue", "")).strip()
    if bg_type != "normal":
        messages.append(f"[warn] Background type이 Normal이 아닙니다: {background.get('type')}")
    if eps != "1" or mu != "1":
        messages.append(f"[warn] Background epsilon/mue 기본값이 아닙니다: epsilon={eps}, mue={mu}")
    if bg_type == "normal" and eps == "1" and mu == "1":
        messages.append("[ok] Background = Normal, epsilon=1, mue=1")


def append_boundary_checks(boundary: dict[str, Any] | None, messages: list[str]) -> None:
    if boundary is None:
        return
    for key, expected_value in DEFAULT_BOUNDARY.items():
        if key == "op":
            continue
        actual = str(boundary.get(key, "")).strip().lower()
        if actual != expected_value:
            messages.append(f"[error] Boundary {key}={boundary.get(key)!r}, 기대값={expected_value!r}")
        else:
            messages.append(f"[ok] Boundary {key}={expected_value}")


def append_floquet_checks(floquet: dict[str, Any] | None, messages: list[str]) -> None:
    if floquet is None:
        return
    ports = floquet.get("ports")
    modes = str(floquet.get("modes", floquet.get("mode_count", ""))).strip()
    if ports != ["Zmin", "Zmax"]:
        messages.append(f"[warn] Floquet ports가 기본값과 다릅니다: {ports}")
    else:
        messages.append("[ok] Floquet ports = Zmin/Zmax")
    if modes != DEFAULT_FLOQUET_MODES:
        messages.append(f"[warn] Floquet mode number가 2가 아닙니다: {modes}")
    else:
        messages.append("[ok] Floquet mode number = 2")


def append_geometry_checks(params: dict[str, Any], ops: list[Any], messages: list[str], active_project: bool) -> None:
    if active_project:
        return
    brick_count = ops.count("brick")
    if brick_count < 4:
        messages.append(f"[error] 기본 ㅁ자 유닛셀 brick이 부족합니다: {brick_count}개")
    else:
        messages.append(f"[ok] brick_count={brick_count}")

    error_count_before = sum(1 for line in messages if line.startswith("[error]"))
    length = numeric_param(params, "length", messages)
    width = numeric_param(params, "width", messages)
    thickness = numeric_param(params, "thickness", messages)
    fmin = numeric_param(params, "fmin", messages)
    fmax = numeric_param(params, "fmax", messages)
    if length is not None and length <= 0:
        messages.append("[error] length는 0보다 커야 합니다.")
    if width is not None and width <= 0:
        messages.append("[error] width는 0보다 커야 합니다.")
    if thickness is not None and thickness <= 0:
        messages.append("[error] thickness는 0보다 커야 합니다.")
    if length is not None and width is not None and width >= length / 2:
        messages.append("[error] width는 length/2보다 작아야 합니다.")
    if fmin is not None and fmax is not None and fmax <= fmin:
        messages.append("[error] fmax는 fmin보다 커야 합니다.")
    error_count_after = sum(1 for line in messages if line.startswith("[error]"))
    if error_count_after == error_count_before:
        messages.append("[ok] length/width/thickness/fmin/fmax 숫자 검사 통과")


def numeric_param(params: dict[str, Any], key: str, messages: list[str]) -> float | None:
    try:
        return float(params[key])
    except Exception:
        messages.append(f"[error] parameter {key} 숫자값이 없습니다.")
        return None
