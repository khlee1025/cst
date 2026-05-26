#!/usr/bin/env python
"""
CST Vibe Runner GUI

Beginner-first GUI for:
1. Korean request -> JSON through an OpenAI-compatible LLM
2. JSON -> CST 2025 CT automation
3. Standard RF run package generation for later CST/Python comparison
"""

from __future__ import annotations

import json
import os
import queue
import copy
import re
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, BooleanVar, StringVar, Tk, Toplevel
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk


APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "cst_vibe_runner.py"
EXAMPLE_PLAN = APP_DIR / "examples" / "02_mesh_frame_unitcell.json"
PROMPT_FILE = APP_DIR / "prompt_for_local_llm.md"
TEMP_PLAN = APP_DIR / ".cst_vibe_gui_last_plan.json"
LLM_CONFIG = APP_DIR / "cst_llm_config.json"


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(stripped[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM output must be a JSON object.")
    return data


class CSTVibeGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("CST Vibe Runner - Simple Mode")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)

        self.status = StringVar(value="준비됨")
        self.prog_id = StringVar(value="CSTStudio.Application.2025")
        self.visible = BooleanVar(value=True)
        self.plan_source = StringVar(value="example")

        self.wizard_vars = {
            "length": StringVar(value="100"),
            "width": StringVar(value="10"),
            "thickness": StringVar(value="2"),
            "fmin": StringVar(value="1"),
            "fmax": StringVar(value="18"),
        }
        self.include_boundary = BooleanVar(value=False)
        self.sweep_parameter = StringVar(value="width")
        self.sweep_values = StringVar(value="5, 10, 15")

        self.llm_api_key = StringVar(value=os.getenv("LLM_API_KEY", ""))
        self.llm_base_url = StringVar(value=os.getenv("LLM_BASE_URL", "http://10.240.246.158:8000/v1"))
        self.llm_model = StringVar(value=os.getenv("LLM_MODEL", "Qwen3.5-122B"))
        self.llm_max_tokens = StringVar(value=os.getenv("LLM_MAX_TOKENS", "4096"))

        self.running = False
        self.output_queue: queue.Queue[str | None] = queue.Queue()

        self.colors = {
            "bg": "#f5f7fb",
            "panel": "#ffffff",
            "muted": "#667085",
            "text": "#111827",
            "accent": "#2563eb",
            "accent_hover": "#1d4ed8",
            "console": "#0b1020",
            "console_text": "#d1e7ff",
        }

        self.configure_style()
        self.load_llm_config()
        self.build_layout()
        self.load_example_plan()

    def configure_style(self) -> None:
        self.root.configure(bg=self.colors["bg"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("Header.TFrame", background="#0f172a")
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("Panel.TLabel", background=self.colors["panel"], foreground=self.colors["text"])
        style.configure("Muted.TLabel", background=self.colors["panel"], foreground=self.colors["muted"])
        style.configure("Header.TLabel", background="#0f172a", foreground="#f8fafc")
        style.configure("TButton", padding=(12, 7))
        style.configure("Accent.TButton", foreground="#ffffff", background=self.colors["accent"], padding=(14, 8))
        style.map("Accent.TButton", background=[("active", self.colors["accent_hover"])])

    def build_layout(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 14))
        header.pack(fill=X)
        ttk.Label(
            header,
            text="CST Vibe Runner",
            style="Header.TLabel",
            font=("Segoe UI Semibold", 18),
        ).pack(side=LEFT)
        ttk.Label(
            header,
            text="CST 2025 CT 기본값 / 대사 -> JSON -> CST 실행",
            style="Header.TLabel",
            font=("Segoe UI", 10),
        ).pack(side=LEFT, padx=(16, 0))
        ttk.Button(header, text="설정", command=self.open_settings).pack(side=RIGHT)

        body = ttk.Frame(self.root, padding=14)
        body.pack(fill=BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Panel.TFrame", padding=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ttk.Frame(body, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        left.rowconfigure(1, weight=1)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self.build_request_panel(left)
        self.build_result_panel(right)

        status_bar = ttk.Frame(self.root, style="Panel.TFrame")
        status_bar.pack(fill=X, side="bottom")
        ttk.Label(status_bar, textvariable=self.status, style="Muted.TLabel", padding=(12, 7)).pack(fill=X)

    def build_request_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="1. 하고 싶은 작업을 적으세요",
            style="Panel.TLabel",
            font=("Segoe UI Semibold", 13),
        ).grid(row=0, column=0, sticky="w")

        self.request_text = ScrolledText(
            parent,
            wrap="word",
            height=12,
            bg="#f8fafc",
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            font=("Malgun Gothic", 10),
            padx=10,
            pady=10,
            bd=0,
            relief="flat",
        )
        self.request_text.grid(row=1, column=0, sticky="nsew", pady=(8, 12))
        self.request_text.insert(
            "1.0",
            "모기장 구조의 ㅁ자 유닛셀을 만들어줘.\n"
            "length=100, width=10, thickness=2, fmin=1, fmax=18.\n"
            "원점 기준으로 x+ 방향과 y- 방향으로 실을 만들고 대칭 이동해서 ㅁ자를 만들어줘. 단위는 um, GHz.",
        )

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)

        buttons = [
            ("대사 -> JSON 만들기", self.convert_request_with_llm, "Accent.TButton"),
            ("기본 유닛셀 값 입력", self.open_wizard, "TButton"),
            ("실행 전 확인", self.preflight_check, "TButton"),
            ("파라미터 스윕", self.open_sweep_dialog, "TButton"),
            ("CST 2025 연결 테스트", self.run_connection_test, "TButton"),
            ("CST 실행 + 결과폴더", self.run_rf_package_cst, "Accent.TButton"),
            ("문제 진단", self.run_diagnostics, "TButton"),
        ]
        for row, (label, command, style) in enumerate(buttons):
            ttk.Button(actions, text=label, command=command, style=style).grid(
                row=row, column=0, sticky="ew", pady=4
            )

        utility = ttk.Frame(parent, style="Panel.TFrame")
        utility.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        for i in range(3):
            utility.columnconfigure(i, weight=1)
        ttk.Button(utility, text="JSON 보기", command=lambda: self.notebook.select(1)).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(utility, text="리포트 저장", command=self.save_output_report).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(utility, text="출력 복사", command=self.copy_output).grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def build_result_panel(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            top,
            text="2. 실행 상태",
            style="Panel.TLabel",
            font=("Segoe UI Semibold", 13),
        ).pack(side=LEFT)
        ttk.Button(top, text="예제 초기화", command=self.load_example_plan).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(top, text="JSON 정렬", command=self.format_json).pack(side=RIGHT)

        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        output_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        json_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(output_tab, text="실행 출력")
        self.notebook.add(json_tab, text="JSON 명령서")

        self.output_text = ScrolledText(
            output_tab,
            wrap="word",
            bg=self.colors["console"],
            fg=self.colors["console_text"],
            insertbackground="#93c5fd",
            font=("Cascadia Mono", 10),
            padx=12,
            pady=12,
            bd=0,
            relief="flat",
        )
        self.output_text.pack(fill=BOTH, expand=True)

        self.plan_text = ScrolledText(
            json_tab,
            wrap="none",
            bg="#fbfdff",
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            font=("Cascadia Mono", 10),
            padx=12,
            pady=12,
            bd=0,
            relief="flat",
            undo=True,
        )
        self.plan_text.pack(fill=BOTH, expand=True)

    def load_example_plan(self) -> None:
        try:
            text = EXAMPLE_PLAN.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("예제 불러오기 실패", str(exc))
            return
        self.plan_text.delete("1.0", END)
        self.plan_text.insert("1.0", text)
        self.plan_source.set("wizard")
        self.status.set("기본 포트 없는 유닛셀 예제를 불러왔습니다.")

    def open_settings(self) -> None:
        win = Toplevel(self.root)
        win.title("설정")
        win.geometry("560x360")
        win.transient(self.root)
        win.grab_set()
        frm = ttk.Frame(win, padding=16)
        frm.pack(fill=BOTH, expand=True)
        for i in range(2):
            frm.columnconfigure(i, weight=1)

        rows = [
            ("CST ProgID", self.prog_id),
            ("LLM Base URL", self.llm_base_url),
            ("LLM Model", self.llm_model),
            ("LLM API Key", self.llm_api_key),
            ("LLM Max Tokens", self.llm_max_tokens),
        ]
        for row, (label, var) in enumerate(rows):
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(frm, textvariable=var).grid(row=row, column=1, sticky="ew", pady=5)
        ttk.Checkbutton(frm, text="CST UI 보이기", variable=self.visible).grid(
            row=len(rows), column=1, sticky="w", pady=8
        )

        btns = ttk.Frame(frm)
        btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        ttk.Button(btns, text="LLM 연결 테스트", command=self.test_llm_connection).pack(side=LEFT)
        ttk.Button(btns, text="저장", command=lambda: (self.save_llm_config(), win.destroy())).pack(side=RIGHT)

    def open_wizard(self) -> None:
        win = Toplevel(self.root)
        win.title("기본 유닛셀 값 입력")
        win.geometry("460x430")
        win.transient(self.root)
        win.grab_set()
        frm = ttk.Frame(win, padding=16)
        frm.pack(fill=BOTH, expand=True)
        frm.columnconfigure(1, weight=1)

        labels = {
            "length": "length 외곽 길이 um",
            "width": "width 실 폭 um",
            "thickness": "thickness 두께 um",
            "fmin": "fmin GHz",
            "fmax": "fmax GHz",
        }
        for row, (key, var) in enumerate(self.wizard_vars.items()):
            ttk.Label(frm, text=labels[key]).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(frm, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(frm, text="유닛셀 경계조건 포함", variable=self.include_boundary).grid(
            row=len(labels), column=1, sticky="w", pady=8
        )
        ttk.Label(
            frm,
            text="기본값은 포트와 solver를 만들지 않습니다.",
            foreground=self.colors["muted"],
        ).grid(row=len(labels) + 1, column=0, columnspan=2, sticky="w", pady=(4, 10))

        ttk.Button(
            frm,
            text="JSON 만들기",
            style="Accent.TButton",
            command=lambda: self.apply_wizard_from_dialog(win),
        ).grid(row=len(labels) + 2, column=0, columnspan=2, sticky="ew")

    def apply_wizard_from_dialog(self, win: Toplevel) -> None:
        if self.apply_wizard_plan():
            win.destroy()
            self.notebook.select(1)

    def open_sweep_dialog(self) -> None:
        win = Toplevel(self.root)
        win.title("파라미터 스윕")
        win.geometry("520x310")
        win.transient(self.root)
        win.grab_set()
        frm = ttk.Frame(win, padding=16)
        frm.pack(fill=BOTH, expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="스윕 파라미터").grid(row=0, column=0, sticky="w", pady=5)
        param_box = ttk.Combobox(
            frm,
            textvariable=self.sweep_parameter,
            values=("width", "length", "thickness", "fmin", "fmax"),
        )
        param_box.grid(row=0, column=1, sticky="ew", pady=5)

        ttk.Label(frm, text="값 목록").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(frm, textvariable=self.sweep_values).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(
            frm,
            text="쉼표 또는 공백으로 구분하세요. 예: 5, 10, 15",
            foreground=self.colors["muted"],
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Button(
            frm,
            text="스윕 드라이런",
            command=lambda: self.start_sweep_from_dialog(win, dry_run=True),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(
            frm,
            text="스윕 실행 + 결과폴더",
            style="Accent.TButton",
            command=lambda: self.start_sweep_from_dialog(win, dry_run=False),
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)

        ttk.Label(
            frm,
            text="각 값마다 JSON을 새로 만들고 runs 폴더를 따로 생성합니다.",
            foreground=self.colors["muted"],
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def parse_sweep_values(self) -> list[str]:
        raw = self.sweep_values.get().strip()
        values = [item for item in re.split(r"[\s,]+", raw) if item]
        if not values:
            raise ValueError("스윕 값 목록이 비어 있습니다.")
        for value in values:
            float(value)
        return values

    def start_sweep_from_dialog(self, win: Toplevel, dry_run: bool) -> None:
        if self.start_sweep(dry_run=dry_run):
            win.destroy()

    def start_sweep(self, dry_run: bool) -> bool:
        if self.running:
            messagebox.showinfo("실행 중", "이미 실행 중입니다.")
            return False
        if not self.sync_wizard_parameters_if_needed():
            return False
        try:
            base_plan = self.current_plan()
            parameter = self.sweep_parameter.get().strip()
            values = self.parse_sweep_values()
            commands = self.build_sweep_commands(base_plan, parameter, values, dry_run=dry_run)
        except Exception as exc:
            messagebox.showerror("스윕 준비 실패", str(exc))
            return False
        if not commands:
            messagebox.showerror("스윕 준비 실패", "실행할 스윕 값이 없습니다.")
            return False

        self.running = True
        self.clear_output()
        self.notebook.select(0)
        mode = "스윕 드라이런" if dry_run else "스윕 실행 + 결과폴더"
        self.status.set(f"{mode} 중...")
        self.append_output(f"[sweep] parameter={parameter}, values={', '.join(values)}\n\n")
        threading.Thread(target=self.sweep_worker, args=(commands, mode), daemon=True).start()
        self.root.after(80, self.drain_output_queue)
        return True

    def build_sweep_commands(self, base_plan: dict, parameter: str, values: list[str], dry_run: bool) -> list[list[str]]:
        if not parameter:
            raise ValueError("스윕 파라미터 이름이 비어 있습니다.")
        params = base_plan.get("parameters")
        if not isinstance(params, dict):
            raise ValueError("parameters는 object여야 합니다.")
        if parameter not in params:
            raise ValueError(f"현재 JSON parameters에 '{parameter}'가 없습니다.")

        commands: list[list[str]] = []
        for index, value in enumerate(values, start=1):
            plan = copy.deepcopy(base_plan)
            plan_params = plan.setdefault("parameters", {})
            if not isinstance(plan_params, dict):
                raise ValueError("parameters는 object여야 합니다.")
            plan_params[parameter] = value

            base_id = str(plan.get("design_id") or plan.get("name") or "mesh_frame_unitcell")
            value_slug = self.safe_slug(value)
            plan["design_id"] = f"{base_id}_{parameter}{value_slug}"
            project = plan.setdefault("project", {"mode": "new"})
            if not isinstance(project, dict):
                raise ValueError("project는 object여야 합니다.")
            project["save_as"] = f"output/{plan['design_id']}.cst"

            plan_path = APP_DIR / f".cst_vibe_gui_sweep_{index:03d}_{self.safe_slug(parameter)}_{value_slug}.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            cmd = [sys.executable, str(RUNNER), str(plan_path), "--prog-id", self.prog_id.get().strip(), "--package-run"]
            if dry_run:
                cmd.append("--dry-run")
            elif self.visible.get():
                cmd.append("--visible")
            cmd.append("--continue-on-error")
            commands.append(cmd)
        return commands

    def sweep_worker(self, commands: list[list[str]], mode: str) -> None:
        worst_code = 0
        try:
            for index, cmd in enumerate(commands, start=1):
                self.output_queue.put(f"\n[sweep {index}/{len(commands)}]\n$ {' '.join(cmd)}\n\n")
                code = self.run_subprocess_to_queue(cmd)
                worst_code = max(worst_code, code)
                self.output_queue.put(f"\n[sweep {index}/{len(commands)} 종료 코드: {code}]\n")
        except Exception as exc:
            worst_code = max(worst_code, 1)
            self.output_queue.put(f"\n[스윕 실패] {exc}\n")
        finally:
            self.output_queue.put(f"\n[{mode} 전체 종료 코드: {worst_code}]\n")
            self.output_queue.put(None)

    def safe_slug(self, value: str) -> str:
        text = str(value).strip().replace(".", "p").replace("-", "m")
        text = re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")
        return text or "value"

    def wizard_values(self) -> dict[str, str]:
        return {key: var.get().strip() for key, var in self.wizard_vars.items()}

    def validate_wizard_values(self) -> dict[str, str]:
        values = self.wizard_values()
        for key, value in values.items():
            if not value:
                raise ValueError(f"{key} 값이 비어 있습니다.")
        numeric = {key: float(value) for key, value in values.items()}
        if numeric["length"] <= 0:
            raise ValueError("length는 0보다 커야 합니다.")
        if numeric["width"] <= 0:
            raise ValueError("width는 0보다 커야 합니다.")
        if numeric["thickness"] <= 0:
            raise ValueError("thickness는 0보다 커야 합니다.")
        if numeric["width"] >= numeric["length"] / 2:
            raise ValueError("width는 length의 절반보다 작아야 ㅁ자 빈 공간이 생깁니다.")
        if numeric["fmax"] <= numeric["fmin"]:
            raise ValueError("fmax는 fmin보다 커야 합니다.")
        return values

    def build_wizard_plan(self) -> dict:
        values = self.validate_wizard_values()
        commands: list[dict] = [
            {"op": "units", "geometry": "um", "frequency": "GHz", "time": "ns"},
            {"op": "frequency_range", "fmin": "fmin", "fmax": "fmax"},
        ]
        if self.include_boundary.get():
            commands.append(
                {
                    "op": "boundary",
                    "xmin": "unit cell",
                    "xmax": "unit cell",
                    "ymin": "unit cell",
                    "ymax": "unit cell",
                    "zmin": "open",
                    "zmax": "open",
                }
            )
        commands.extend(
            [
                {
                    "op": "brick",
                    "name": "thread_top_x",
                    "component": "unitcell",
                    "material": "Copper (annealed)",
                    "xrange": ["0", "length"],
                    "yrange": ["-width", "0"],
                    "zrange": ["0", "thickness"],
                },
                {
                    "op": "brick",
                    "name": "thread_left_y",
                    "component": "unitcell",
                    "material": "Copper (annealed)",
                    "xrange": ["0", "width"],
                    "yrange": ["-length", "0"],
                    "zrange": ["0", "thickness"],
                },
                {
                    "op": "brick",
                    "name": "thread_bottom_x",
                    "component": "unitcell",
                    "material": "Copper (annealed)",
                    "xrange": ["0", "length"],
                    "yrange": ["-length", "-length+width"],
                    "zrange": ["0", "thickness"],
                },
                {
                    "op": "brick",
                    "name": "thread_right_y",
                    "component": "unitcell",
                    "material": "Copper (annealed)",
                    "xrange": ["length-width", "length"],
                    "yrange": ["-length", "0"],
                    "zrange": ["0", "thickness"],
                },
                {"op": "rebuild"},
                {"op": "save"},
            ]
        )
        return {
            "design_id": "mesh_frame_unitcell",
            "project": {"mode": "new", "save_as": "output/generated_mesh_frame_unitcell.cst"},
            "parameters": values,
            "commands": commands,
        }

    def apply_wizard_plan(self) -> bool:
        try:
            plan = self.build_wizard_plan()
        except ValueError as exc:
            messagebox.showerror("설계값 오류", str(exc))
            return False
        self.set_plan(plan, source="wizard")
        self.status.set("기본 유닛셀 JSON을 만들었습니다.")
        return True

    def set_plan(self, plan: dict, source: str) -> None:
        self.plan_text.delete("1.0", END)
        self.plan_text.insert("1.0", json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        self.plan_source.set(source)

    def current_plan(self) -> dict:
        data = json.loads(self.plan_text.get("1.0", "end-1c"))
        if not isinstance(data, dict):
            raise ValueError("JSON 최상위는 object여야 합니다.")
        return data

    def sync_wizard_parameters_if_needed(self) -> bool:
        if self.plan_source.get() != "wizard":
            return True
        try:
            values = self.validate_wizard_values()
            plan = self.current_plan()
            params = plan.setdefault("parameters", {})
            if not isinstance(params, dict):
                raise ValueError("parameters는 object여야 합니다.")
            params.update(values)
            self.set_plan(plan, source="wizard")
            return True
        except (ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("실행 전 확인 실패", str(exc))
            return False

    def preflight_check(self) -> None:
        if not self.sync_wizard_parameters_if_needed():
            return
        self.rf_check(show_only=False)
        self.run_plan(dry_run=True, mode_label="실행 전 확인")

    def rf_check(self, show_only: bool = True) -> bool:
        try:
            plan = self.current_plan()
        except Exception as exc:
            messagebox.showerror("JSON 오류", str(exc))
            return False
        messages = ["=== RF Check ==="]
        params = plan.get("parameters", {})
        commands = plan.get("commands", [])
        if not isinstance(params, dict):
            messages.append("[error] parameters must be an object.")
            params = {}
        if not isinstance(commands, list):
            messages.append("[error] commands must be a list.")
            commands = []

        def as_float(key: str) -> float | None:
            try:
                return float(params[key])
            except Exception:
                return None

        length = as_float("length")
        width = as_float("width")
        thickness = as_float("thickness")
        fmin = as_float("fmin")
        fmax = as_float("fmax")
        if length is not None and length <= 0:
            messages.append("[error] length must be positive.")
        if width is not None and width <= 0:
            messages.append("[error] width must be positive.")
        if thickness is not None and thickness <= 0:
            messages.append("[error] thickness must be positive.")
        if length is not None and width is not None and width >= length / 2:
            messages.append("[error] width must be smaller than length/2.")
        if fmin is not None and fmax is not None and fmax <= fmin:
            messages.append("[error] fmax must be greater than fmin.")

        ops = [item.get("op") for item in commands if isinstance(item, dict)]
        if "discrete_port" in ops:
            messages.append("[warn] discrete_port가 있습니다. 포트 위치를 CST에서 확인하세요.")
        if "solver_start" in ops:
            messages.append("[warn] solver_start가 있습니다. 형상 확인 후 실행하는 것을 권장합니다.")
        messages.append(f"[info] command_count={len(commands)}, brick_count={ops.count('brick')}")
        has_error = any(line.startswith("[error]") for line in messages)
        if not has_error:
            messages.append("[ok] 기본 RF 치수 검사를 통과했습니다.")

        self.clear_output()
        self.append_output("\n".join(messages) + "\n\n")
        self.notebook.select(0)
        if show_only:
            self.status.set("RF Check 완료")
        return not has_error

    def load_llm_config(self) -> None:
        if not LLM_CONFIG.exists():
            return
        try:
            data = json.loads(LLM_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return
        self.llm_api_key.set(str(data.get("api_key", self.llm_api_key.get())))
        self.llm_base_url.set(str(data.get("base_url", self.llm_base_url.get())))
        self.llm_model.set(str(data.get("model", self.llm_model.get())))
        self.llm_max_tokens.set(str(data.get("max_tokens", self.llm_max_tokens.get())))
        self.prog_id.set(str(data.get("prog_id", self.prog_id.get())))

    def save_llm_config(self) -> None:
        try:
            data = {
                "api_key": self.llm_api_key.get().strip(),
                "base_url": self.llm_base_url.get().strip(),
                "model": self.llm_model.get().strip(),
                "max_tokens": int(self.llm_max_tokens.get().strip()),
                "prog_id": self.prog_id.get().strip(),
            }
            LLM_CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("설정 저장 실패", str(exc))
            return
        self.status.set("설정을 저장했습니다.")

    def llm_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai 패키지가 필요합니다: py -m pip install openai") from exc
        return OpenAI(api_key=self.llm_api_key.get().strip() or "sk-ignored", base_url=self.llm_base_url.get().strip())

    def test_llm_connection(self) -> None:
        if self.running:
            return
        self.save_llm_config()
        self.running = True
        self.clear_output()
        self.notebook.select(0)
        self.append_output("[llm] 연결 테스트 시작\n")
        self.status.set("LLM 연결 테스트 중...")

        def worker() -> None:
            try:
                resp = self.llm_client().chat.completions.create(
                    model=self.llm_model.get().strip(),
                    messages=[{"role": "user", "content": "ok라고만 답하세요."}],
                    max_tokens=50,
                    temperature=0.0,
                )
                answer = (resp.choices[0].message.content or "").strip()
                self.root.after(0, lambda: self.append_output(f"[llm] 연결 성공: {answer}\n"))
                self.root.after(0, lambda: self.status.set("LLM 연결 성공"))
            except Exception as exc:
                self.root.after(0, lambda exc=exc: self.append_output(f"[llm] 연결 실패: {exc}\n"))
                self.root.after(0, lambda: self.status.set("LLM 연결 실패"))
            finally:
                self.root.after(0, self.mark_not_running)

        threading.Thread(target=worker, daemon=True).start()

    def convert_request_with_llm(self) -> None:
        if self.running:
            return
        request = self.request_text.get("1.0", "end-1c").strip()
        if not request:
            messagebox.showerror("요청 없음", "요청 메모에 대사를 입력하세요.")
            return
        try:
            prompt = PROMPT_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("프롬프트 읽기 실패", str(exc))
            return
        self.save_llm_config()
        self.running = True
        self.clear_output()
        self.notebook.select(0)
        self.append_output("[llm] 대사를 JSON으로 변환 중...\n")
        self.status.set("LLM JSON 변환 중...")

        def worker() -> None:
            try:
                resp = self.llm_client().chat.completions.create(
                    model=self.llm_model.get().strip(),
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"아래 요청을 CST Vibe Runner JSON으로 변환하세요. JSON만 출력하세요.\n\n{request}"},
                    ],
                    max_tokens=int(self.llm_max_tokens.get().strip()),
                    temperature=0.1,
                )
                content = resp.choices[0].message.content or ""
                plan = extract_json_object(content)
                self.root.after(0, lambda: self.apply_llm_plan(plan))
            except Exception as exc:
                self.root.after(0, lambda exc=exc: self.append_output(f"[llm] JSON 변환 실패: {exc}\n"))
                self.root.after(0, lambda: self.status.set("LLM JSON 변환 실패"))
            finally:
                self.root.after(0, self.mark_not_running)

        threading.Thread(target=worker, daemon=True).start()

    def apply_llm_plan(self, plan: dict) -> None:
        self.set_plan(plan, source="llm")
        self.append_output("[llm] JSON 변환 완료. 실행 전 확인을 먼저 누르세요.\n")
        self.status.set("LLM JSON 변환 완료")
        self.notebook.select(1)

    def format_json(self) -> None:
        try:
            plan = self.current_plan()
        except Exception as exc:
            messagebox.showerror("JSON 오류", str(exc))
            return
        self.set_plan(plan, source=self.plan_source.get())
        self.status.set("JSON 정렬 완료")

    def run_connection_test(self) -> None:
        plan_text = json.dumps({"project": {"mode": "new"}, "parameters": {}, "commands": []}, indent=2)
        self.run_plan(dry_run=False, plan_text=plan_text, mode_label="CST 2025 연결 테스트")

    def run_diagnostics(self) -> None:
        if not self.sync_wizard_parameters_if_needed():
            return
        self.run_plan(False, mode_label="문제 진단", extra_args=["--continue-on-error"])

    def run_rf_package_cst(self) -> None:
        if not self.sync_wizard_parameters_if_needed():
            return
        if not self.rf_check(show_only=False):
            self.append_output("[stop] RF Check에 error가 있어 실행하지 않았습니다.\n")
            return
        self.run_plan(False, mode_label="CST 실행 + 결과폴더", extra_args=["--package-run", "--continue-on-error"])

    def run_plan(
        self,
        dry_run: bool,
        plan_text: str | None = None,
        mode_label: str | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        if self.running:
            messagebox.showinfo("실행 중", "이미 실행 중입니다.")
            return
        text = self.plan_text.get("1.0", "end-1c") if plan_text is None else plan_text
        try:
            json.loads(text)
            TEMP_PLAN.write_text(text, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("실행 준비 실패", str(exc))
            return

        cmd = [sys.executable, str(RUNNER), str(TEMP_PLAN), "--prog-id", self.prog_id.get().strip()]
        if dry_run:
            cmd.append("--dry-run")
        elif self.visible.get():
            cmd.append("--visible")
        if extra_args:
            cmd.extend(extra_args)

        self.running = True
        self.append_output(f"\n$ {' '.join(cmd)}\n\n")
        self.notebook.select(0)
        self.status.set(f"{mode_label or '실행'} 중...")
        threading.Thread(target=self.worker, args=(cmd, mode_label or "실행"), daemon=True).start()
        self.root.after(80, self.drain_output_queue)

    def worker(self, cmd: list[str], mode: str) -> None:
        try:
            code = self.run_subprocess_to_queue(cmd)
            self.output_queue.put(f"\n[{mode} 종료 코드: {code}]\n")
        except Exception as exc:
            self.output_queue.put(f"\n[실행 실패] {exc}\n")
        finally:
            self.output_queue.put(None)

    def run_subprocess_to_queue(self, cmd: list[str]) -> int:
        proc = subprocess.Popen(
            cmd,
            cwd=str(APP_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            self.output_queue.put(line)
        return proc.wait()

    def drain_output_queue(self) -> None:
        finished = False
        while True:
            try:
                item = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                finished = True
            else:
                self.append_output(item)
        if finished:
            self.mark_not_running()
            self.status.set("완료")
            return
        self.root.after(80, self.drain_output_queue)

    def mark_not_running(self) -> None:
        self.running = False

    def append_output(self, text: str) -> None:
        self.output_text.insert(END, text)
        self.output_text.see(END)

    def clear_output(self) -> None:
        self.output_text.delete("1.0", END)

    def copy_output(self) -> None:
        text = self.output_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("출력을 복사했습니다.")

    def save_output_report(self) -> None:
        text = self.output_text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("저장할 출력 없음", "먼저 실행 또는 진단을 하세요.")
            return
        path = filedialog.asksaveasfilename(
            title="리포트 저장",
            initialdir=str(APP_DIR),
            initialfile="cst_vibe_diagnostic_report.txt",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("저장 실패", str(exc))
            return
        self.status.set(f"리포트 저장됨: {path}")


def main() -> None:
    root = Tk()
    CSTVibeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
