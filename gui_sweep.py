from __future__ import annotations

import json
import queue
import threading
import traceback
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from typing import Any

from src.results import analyze_runs, write_analysis_csv
from src.sweep import load_config, run_sweep


DEFAULT_CONFIG = Path("configs/sweep.shield_mesh_3x3.example.json")


class SweepGui(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CST 3x3 Shield Mesh Sweep")
        self.geometry("980x720")
        self.minsize(900, 640)

        self.config_path = StringVar(value=str(DEFAULT_CONFIG))
        self.template_cst = StringVar()
        self.runs_dir = StringVar(value="runs_shield_mesh_3x3")
        self.mode = StringVar(value="local_gui")
        self.connect_address = StringVar()
        self.max_runs = StringVar(value="25")
        self.dry_run = BooleanVar(value=True)
        self.save_after_update = BooleanVar(value=True)
        self.run_solver_enabled = BooleanVar(value=True)
        self.target_frequency = StringVar(value="10.0")
        self.s11_goal = StringVar(value="-10.0")

        self.param_name = StringVar()
        self.param_unit = StringVar(value="mm")
        self.param_values = StringVar()
        self.param_start = StringVar()
        self.param_stop = StringVar()
        self.param_step = StringVar()

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build()
        self._load_default_config()
        self.after(100, self._drain_log_queue)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)
        root.rowconfigure(5, weight=1)

        self._build_config_section(root)
        self._build_project_section(root)
        self._build_parameter_section(root)
        self._build_run_section(root)
        self._build_log_section(root)

    def _build_config_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Config", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Config file").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.config_path).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(frame, text="Open", command=self.open_config).grid(row=0, column=2, padx=(0, 4))
        ttk.Button(frame, text="Save", command=self.save_config).grid(row=0, column=3)

    def _build_project_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Project / CST", padding=10)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(4, weight=1)

        ttk.Label(frame, text="Template .cst").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.template_cst).grid(row=0, column=1, columnspan=3, sticky="ew", padx=8)
        ttk.Button(frame, text="Browse", command=self.browse_cst).grid(row=0, column=4, sticky="ew")

        ttk.Label(frame, text="Runs dir").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.runs_dir).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Label(frame, text="Mode").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Combobox(
            frame,
            textvariable=self.mode,
            values=("local_gui", "server_queue"),
            state="readonly",
            width=14,
        ).grid(row=1, column=3, sticky="w", padx=8, pady=(8, 0))

        ttk.Label(frame, text="Connect address").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.connect_address).grid(
            row=2, column=1, columnspan=4, sticky="ew", padx=8, pady=(8, 0)
        )

        checks = ttk.Frame(frame)
        checks.grid(row=3, column=1, columnspan=4, sticky="w", padx=4, pady=(8, 0))
        ttk.Checkbutton(checks, text="Dry run", variable=self.dry_run).pack(side="left", padx=4)
        ttk.Checkbutton(checks, text="Save after parameter update", variable=self.save_after_update).pack(
            side="left", padx=12
        )
        ttk.Checkbutton(checks, text="Run solver", variable=self.run_solver_enabled).pack(side="left", padx=12)

    def _build_parameter_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Sweep Parameters", padding=10)
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for col in range(10):
            frame.columnconfigure(col, weight=1)

        labels = ("Name", "Unit", "Values", "Start", "Stop", "Step")
        variables = (
            self.param_name,
            self.param_unit,
            self.param_values,
            self.param_start,
            self.param_stop,
            self.param_step,
        )
        widths = (14, 8, 28, 10, 10, 10)
        for col, (label, variable, width) in enumerate(zip(labels, variables, widths)):
            ttk.Label(frame, text=label).grid(row=0, column=col, sticky="w")
            ttk.Entry(frame, textvariable=variable, width=width).grid(row=1, column=col, sticky="ew", padx=(0, 6))

        ttk.Button(frame, text="Add / Update", command=self.add_or_update_parameter).grid(
            row=1, column=6, sticky="ew", padx=4
        )
        ttk.Button(frame, text="Delete", command=self.delete_parameter).grid(row=1, column=7, sticky="ew", padx=4)
        ttk.Button(frame, text="Clear", command=self.clear_parameter_form).grid(row=1, column=8, sticky="ew", padx=4)

        self.parameters = ttk.Treeview(
            parent,
            columns=("name", "unit", "values", "start", "stop", "step"),
            show="headings",
            height=8,
        )
        self.parameters.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        for col, width in (
            ("name", 160),
            ("unit", 80),
            ("values", 280),
            ("start", 100),
            ("stop", 100),
            ("step", 100),
        ):
            self.parameters.heading(col, text=col)
            self.parameters.column(col, width=width, anchor="w")
        self.parameters.bind("<<TreeviewSelect>>", self.on_parameter_select)

    def _build_run_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Run", padding=10)
        frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(5, weight=1)

        ttk.Label(frame, text="Max runs").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.max_runs, width=10).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(frame, text="Target GHz").grid(row=0, column=2, sticky="w")
        ttk.Entry(frame, textvariable=self.target_frequency, width=10).grid(row=0, column=3, sticky="w", padx=8)
        ttk.Label(frame, text="S-param goal dB").grid(row=0, column=4, sticky="w")
        ttk.Entry(frame, textvariable=self.s11_goal, width=10).grid(row=0, column=5, sticky="w", padx=8)

        ttk.Button(frame, text="Save Config", command=self.save_config).grid(row=0, column=6, sticky="ew", padx=4)
        ttk.Button(frame, text="Run Sweep", command=self.start_sweep).grid(row=0, column=7, sticky="ew", padx=4)
        ttk.Button(frame, text="Analyze Results", command=self.start_analysis).grid(
            row=0, column=8, sticky="ew", padx=4
        )

    def _build_log_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Log", padding=10)
        frame.grid(row=5, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log = ttk.Treeview(frame, columns=("message",), show="headings")
        self.log.heading("message", text="message")
        self.log.column("message", anchor="w", width=880)
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

    def open_config(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        self.config_path.set(path)
        self.load_config_from_path(Path(path))

    def browse_cst(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CST project", "*.cst"), ("All files", "*.*")])
        if path:
            self.template_cst.set(path)

    def save_config(self) -> None:
        path = Path(self.config_path.get())
        path.parent.mkdir(parents=True, exist_ok=True)
        config = self.build_config()
        with path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
        self.add_log(f"Saved config: {path}")

    def start_sweep(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Running", "A sweep is already running.")
            return

        self.save_config()
        config_path = Path(self.config_path.get())
        dry_run = self.dry_run.get()
        self.worker = threading.Thread(
            target=self._run_sweep_worker,
            args=(config_path, dry_run),
            daemon=True,
        )
        self.worker.start()

    def _run_sweep_worker(self, config_path: Path, dry_run: bool) -> None:
        try:
            self.log_queue.put(f"Starting sweep: {config_path}")
            config = load_config(config_path)
            run_sweep(config=config, config_path=config_path, dry_run=dry_run)
            self.log_queue.put("Sweep finished.")
        except Exception:
            self.log_queue.put(traceback.format_exc())

    def start_analysis(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Running", "A sweep or analysis is already running.")
            return

        self.save_config()
        config_path = Path(self.config_path.get())
        self.worker = threading.Thread(
            target=self._analyze_worker,
            args=(config_path,),
            daemon=True,
        )
        self.worker.start()

    def _analyze_worker(self, config_path: Path) -> None:
        try:
            self.log_queue.put(f"Analyzing results: {config_path}")
            config = load_config(config_path)
            scoring = config.get("scoring", {})
            runs_dir = Path(config.get("project", {}).get("runs_dir", "runs"))
            patterns = config.get("results", {}).get("s11_file_patterns")
            s21_patterns = config.get("results", {}).get("s21_file_patterns")
            rows = analyze_runs(
                runs_dir=runs_dir,
                target_frequency_ghz=scoring.get("target_frequency_ghz"),
                s11_goal_db=scoring.get("s11_goal_db", -10.0),
                patterns=patterns if patterns else None,
                s21_patterns=s21_patterns if s21_patterns else None,
            )
            output_path = runs_dir / "analysis_results.csv"
            write_analysis_csv(output_path, rows)
            self.log_queue.put(f"Analyzed {len(rows)} run folders. Wrote {output_path}")
            analyzed_rows = [row for row in rows if row.get("result_status") == "analyzed"]
            if analyzed_rows:
                best = analyzed_rows[0]
                self.log_queue.put(
                    "Best run: "
                    f"{best.get('run')} | "
                    f"S21@target={best.get('s21_at_target_db')} dB | "
                    f"SE@target={best.get('shielding_effectiveness_at_target_db')} dB | "
                    f"S11@target={best.get('s11_at_target_db')} dB | "
                    f"min={best.get('s11_min_db')} dB | "
                    f"BW={best.get('bandwidth_10db_ghz')} GHz"
                )
            elif rows:
                self.log_queue.put("No S-parameter files found yet. Export S21 or S11 into each run folder.")
        except Exception:
            self.log_queue.put(traceback.format_exc())

    def add_or_update_parameter(self) -> None:
        name = self.param_name.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Parameter name is required.")
            return

        values = (
            name,
            self.param_unit.get().strip(),
            self.param_values.get().strip(),
            self.param_start.get().strip(),
            self.param_stop.get().strip(),
            self.param_step.get().strip(),
        )

        selected = self.parameters.selection()
        if selected:
            self.parameters.item(selected[0], values=values)
        else:
            self.parameters.insert("", "end", values=values)
        self.clear_parameter_form()

    def delete_parameter(self) -> None:
        for item in self.parameters.selection():
            self.parameters.delete(item)
        self.clear_parameter_form()

    def clear_parameter_form(self) -> None:
        self.param_name.set("")
        self.param_unit.set("mm")
        self.param_values.set("")
        self.param_start.set("")
        self.param_stop.set("")
        self.param_step.set("")
        self.parameters.selection_remove(self.parameters.selection())

    def on_parameter_select(self, _event: object) -> None:
        selected = self.parameters.selection()
        if not selected:
            return
        values = self.parameters.item(selected[0], "values")
        self.param_name.set(values[0])
        self.param_unit.set(values[1])
        self.param_values.set(values[2])
        self.param_start.set(values[3])
        self.param_stop.set(values[4])
        self.param_step.set(values[5])

    def build_config(self) -> dict[str, Any]:
        return {
            "project": {
                "template_cst": self.template_cst.get().strip(),
                "runs_dir": self.runs_dir.get().strip() or "runs",
                "copy_template_per_run": True,
            },
            "cst": {
                "mode": self.mode.get(),
                "connect_address": self.connect_address.get().strip() or None,
                "save_after_parameter_update": self.save_after_update.get(),
                "run_solver": self.run_solver_enabled.get(),
                "result_exports": [
                    {
                        "name": "s11",
                        "type": "todo",
                        "note": "Add CST result-tree export path after confirming your model result names.",
                    }
                ],
            },
            "sweep": {
                "max_runs": self._optional_int(self.max_runs.get()),
                "parameters": self._read_parameter_specs(),
            },
            "results": {
                "s11_file_patterns": [
                    "s11.csv",
                    "result_s11.csv",
                    "s11.txt",
                    "result_s11.txt",
                    "*s11*.csv",
                    "*S11*.csv",
                    "*s11*.txt",
                    "*S11*.txt",
                ],
                "s21_file_patterns": [
                    "s21.csv",
                    "result_s21.csv",
                    "s21.txt",
                    "result_s21.txt",
                    "*s21*.csv",
                    "*S21*.csv",
                    "*s21*.txt",
                    "*S21*.txt",
                ],
            },
            "scoring": {
                "target_frequency_ghz": self._optional_float(self.target_frequency.get()),
                "s11_goal_db": self._optional_float(self.s11_goal.get()),
                "primary_metric": "min_s11_near_target",
            },
        }

    def _read_parameter_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for item in self.parameters.get_children():
            name, unit, values, start, stop, step = self.parameters.item(item, "values")
            spec: dict[str, Any] = {"name": name}
            if unit:
                spec["unit"] = unit
            if values:
                spec["values"] = [float(part.strip()) for part in values.split(",") if part.strip()]
            else:
                spec["start"] = float(start)
                spec["stop"] = float(stop)
                spec["step"] = float(step)
            specs.append(spec)
        if not specs:
            raise ValueError("At least one sweep parameter is required.")
        return specs

    def load_config_from_path(self, path: Path) -> None:
        config = load_config(path)
        self.template_cst.set(config.get("project", {}).get("template_cst", ""))
        self.runs_dir.set(config.get("project", {}).get("runs_dir", "runs"))

        cst_config = config.get("cst", {})
        self.mode.set(cst_config.get("mode", "local_gui"))
        self.connect_address.set(cst_config.get("connect_address") or "")
        self.save_after_update.set(bool(cst_config.get("save_after_parameter_update", True)))
        self.run_solver_enabled.set(bool(cst_config.get("run_solver", True)))

        sweep_config = config.get("sweep", {})
        self.max_runs.set(str(sweep_config.get("max_runs", "")))
        for item in self.parameters.get_children():
            self.parameters.delete(item)
        for spec in sweep_config.get("parameters", []):
            self.parameters.insert(
                "",
                "end",
                values=(
                    spec.get("name", ""),
                    spec.get("unit", ""),
                    ", ".join(str(value) for value in spec.get("values", [])),
                    str(spec.get("start", "")),
                    str(spec.get("stop", "")),
                    str(spec.get("step", "")),
                ),
            )

        scoring = config.get("scoring", {})
        self.target_frequency.set(str(scoring.get("target_frequency_ghz", "")))
        self.s11_goal.set(str(scoring.get("s11_goal_db", "")))
        self.add_log(f"Loaded config: {path}")

    def _load_default_config(self) -> None:
        if DEFAULT_CONFIG.exists():
            self.load_config_from_path(DEFAULT_CONFIG)

    def add_log(self, message: str) -> None:
        self.log.insert("", "end", values=(message,))
        self.log.yview_moveto(1.0)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.add_log(message)
        self.after(100, self._drain_log_queue)

    @staticmethod
    def _optional_int(value: str) -> int | None:
        value = value.strip()
        return int(value) if value else None

    @staticmethod
    def _optional_float(value: str) -> float | None:
        value = value.strip()
        return float(value) if value else None


def main() -> int:
    app = SweepGui()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
