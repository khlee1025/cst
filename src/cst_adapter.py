from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CstAdapter:
    """Thin CST Studio Suite automation layer.

    The exact CST Python API surface can vary by CST version and company setup.
    Keep version-specific code in this file so the sweep logic stays stable.
    """

    def __init__(self, cst_config: dict[str, Any]) -> None:
        self.config = cst_config
        self.mode = cst_config.get("mode", "local_gui")

    def run_point(self, cst_path: Path, run_dir: Path, parameters: dict[str, float]) -> None:
        if self.mode == "local_gui":
            self._run_local_gui(cst_path=cst_path, run_dir=run_dir, parameters=parameters)
            return

        if self.mode == "server_queue":
            self._write_server_queue_payload(cst_path=cst_path, run_dir=run_dir, parameters=parameters)
            return

        raise ValueError(f"Unsupported CST mode: {self.mode}")

    def _run_local_gui(self, cst_path: Path, run_dir: Path, parameters: dict[str, float]) -> None:
        try:
            from cst.interface import DesignEnvironment
        except ImportError as exc:
            raise RuntimeError(
                "Could not import cst.interface. Run this with CST's bundled Python, "
                "or add CST's Python library path to PYTHONPATH."
            ) from exc

        connect_address = self.config.get("connect_address")
        if connect_address:
            if not hasattr(DesignEnvironment, "connect"):
                raise RuntimeError("This CST Python library does not expose DesignEnvironment.connect.")
            design_environment = DesignEnvironment.connect(connect_address)
        else:
            design_environment = DesignEnvironment()
        project = self._open_project(design_environment, cst_path)
        self._store_parameters(project, parameters)
        self._rebuild(project)

        if self.config.get("save_after_parameter_update", True):
            self._save(project)

        if self.config.get("run_solver", True):
            self._run_solver(project)
            self._save(project)

        self._write_result_placeholder(run_dir)

    def _open_project(self, design_environment: Any, cst_path: Path) -> Any:
        if not cst_path.exists():
            raise FileNotFoundError(f"CST project does not exist: {cst_path}")

        for method_name in ("open_project", "open"):
            method = getattr(design_environment, method_name, None)
            if method is not None:
                return method(str(cst_path))

        raise RuntimeError("Could not find a project-open method on CST DesignEnvironment.")

    def _store_parameters(self, project: Any, parameters: dict[str, float]) -> None:
        history = "\n".join(
            f'StoreParameter("{name}", "{value}")'
            for name, value in parameters.items()
        )
        self._add_to_history(project, "Python sweep: store parameters", history)

    def _rebuild(self, project: Any) -> None:
        rebuild_macro = "RebuildOnParametricChange(False, False)"
        self._add_to_history(project, "Python sweep: rebuild", rebuild_macro)

    def _add_to_history(self, project: Any, title: str, macro: str) -> None:
        model3d = getattr(project, "model3d", None)
        if model3d is None or not hasattr(model3d, "add_to_history"):
            raise RuntimeError("CST project does not expose model3d.add_to_history.")
        model3d.add_to_history(title, macro)

    def _run_solver(self, project: Any) -> None:
        modeler = getattr(project, "modeler", None)
        if modeler is not None and hasattr(modeler, "run_solver"):
            modeler.run_solver()
            return

        if hasattr(project, "run_solver"):
            project.run_solver()
            return

        raise RuntimeError("Could not find CST solver-run method.")

    def _save(self, project: Any) -> None:
        for method_name in ("save", "Save"):
            method = getattr(project, method_name, None)
            if method is not None:
                method()
                return

    def _write_result_placeholder(self, run_dir: Path) -> None:
        payload = {
            "message": "Solver run finished. Add project-specific S-parameter/farfield export in CstAdapter after confirming CST result tree names.",
            "configured_exports": self.config.get("result_exports", []),
        }
        with (run_dir / "result_export.todo.json").open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def _write_server_queue_payload(self, cst_path: Path, run_dir: Path, parameters: dict[str, float]) -> None:
        payload = {
            "mode": "server_queue",
            "cst_path": str(cst_path),
            "parameters": parameters,
            "next_step": "Submit this run folder to the company CST batch/HPC queue adapter.",
        }
        with (run_dir / "server_queue_payload.json").open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
