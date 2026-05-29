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
import datetime as dt
import re
import subprocess
import sys
import tempfile
import threading
from itertools import product
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, BooleanVar, StringVar, Tk, Toplevel
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk

import collect_sparams
import cst_plan_defaults as plan_defaults


APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "cst_vibe_runner.py"
COLLECTOR = APP_DIR / "collect_sparams.py"
EXAMPLE_PLAN = APP_DIR / "examples" / "02_mesh_frame_unitcell.json"
PROMPT_FILE = APP_DIR / "prompt_for_local_llm.md"
RUNTIME_TMP = Path(tempfile.gettempdir()) / "cst_vibe_runner"
LLM_CONFIG = APP_DIR / "cst_llm_config.json"
SWEEP_ALL = "전체 변수 조합"


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
        self.include_boundary = BooleanVar(value=True)
        self.floquet_modes = StringVar(value="2")
        self.solver_type = StringVar(value="HF Time Domain")
        self.sweep_parameter = StringVar(value="width")
        self.sweep_values = StringVar(value="5, 10, 15")
        self.param_summary = StringVar(value="")

        self.llm_api_key = StringVar(value=os.getenv("LLM_API_KEY", ""))
        self.llm_base_url = StringVar(value=os.getenv("LLM_BASE_URL", "http://10.240.246.158:8000/v1"))
        self.llm_model = StringVar(value=os.getenv("LLM_MODEL", "Qwen3.5-122B"))
        self.llm_max_tokens = StringVar(value=os.getenv("LLM_MAX_TOKENS", "4096"))

        self.running = False
        self.output_queue: queue.Queue[str | None] = queue.Queue()
        self.after_run_action: str | None = None
        self.pending_result_dir: Path | None = None
        self.last_exit_code: int | None = None

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
            text="CST 2025 CT / 대사 적용 -> 설정 검증 -> 시뮬레이션",
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

        ttk.Label(parent, textvariable=self.param_summary, style="Muted.TLabel").grid(
            row=2, column=0, sticky="ew", pady=(0, 8)
        )

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)

        buttons = [
            ("1. 대사 적용", self.apply_request_to_wizard, "Accent.TButton"),
            ("2. 실행 전 확인", self.preflight_check, "TButton"),
            ("3. 시뮬레이션 시작", self.run_simulation, "Accent.TButton"),
        ]
        for row, (label, command, style) in enumerate(buttons):
            ttk.Button(actions, text=label, command=command, style=style).grid(
                row=row, column=0, sticky="ew", pady=4
            )

        utility = ttk.Frame(parent, style="Panel.TFrame")
        utility.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        for i in range(3):
            utility.columnconfigure(i, weight=1)
        ttk.Button(utility, text="숫자 직접 입력", command=self.open_wizard).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(utility, text="현재 CST 시뮬레이션", command=self.run_active_simulation).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(utility, text="결과 불러오기", command=self.collect_sparams_dialog).grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def build_result_panel(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            top,
            text="2. 실행 상태",
            style="Panel.TLabel",
            font=("Segoe UI Semibold", 13),
        ).pack(side=LEFT)
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        output_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        result_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        sweep_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        json_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.result_tab = result_tab
        self.sweep_tab = sweep_tab
        self.json_tab = json_tab
        self.notebook.add(output_tab, text="시뮬레이션 로그")
        self.notebook.add(result_tab, text="해석 후 S11/S21")
        self.notebook.add(sweep_tab, text="스윕 설정")
        self.notebook.add(json_tab, text="CST 실행 JSON")

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

        self.result_text = ScrolledText(
            result_tab,
            wrap="none",
            bg="#fbfdff",
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            font=("Cascadia Mono", 10),
            padx=12,
            pady=12,
            bd=0,
            relief="flat",
        )
        self.result_text.pack(fill=BOTH, expand=True)
        self.result_text.insert("1.0", "CST 해석이 끝난 뒤 결과 불러오기를 누르면 S11/S21 요약이 표시됩니다.\n")

        json_header = ttk.Frame(json_tab, style="Panel.TFrame", padding=(12, 10))
        json_header.pack(fill=X)
        ttk.Label(
            json_header,
            text="CST 실행 명령서",
            style="Panel.TLabel",
            font=("Segoe UI Semibold", 11),
        ).pack(side=LEFT)
        ttk.Label(
            json_header,
            text="parameters는 입력값이고, commands의 op 순서대로 CST에 전달됩니다. solver_start가 있어야 해석 시작까지 갑니다.",
            style="Muted.TLabel",
        ).pack(side=LEFT, padx=(12, 0))

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

        self.build_sweep_tab(sweep_tab)

    def build_sweep_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(5, weight=1)

        ttk.Label(parent, text="스윕 방식", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=12, pady=(14, 6))
        param_box = ttk.Combobox(
            parent,
            textvariable=self.sweep_parameter,
            values=("width", "length", "thickness", "fmin", "fmax", SWEEP_ALL),
            state="readonly",
        )
        param_box.grid(row=0, column=1, sticky="ew", padx=12, pady=(14, 6))

        ttk.Label(parent, text="값 목록", style="Panel.TLabel").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        ttk.Entry(parent, textvariable=self.sweep_values).grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        ttk.Label(
            parent,
            text="단일 변수 스윕에 사용합니다. 예: 5, 10, 15",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 8))

        ttk.Label(parent, text="전체 변수 값표", style="Panel.TLabel").grid(row=3, column=0, sticky="nw", padx=12, pady=6)
        self.sweep_matrix_text = ScrolledText(parent, height=6, wrap="word", font=("Cascadia Mono", 9), bg="#fbfdff", bd=0)
        self.sweep_matrix_text.grid(row=3, column=1, sticky="nsew", padx=12, pady=6)
        self.sweep_matrix_text.insert("1.0", self.default_sweep_matrix_text())

        button_row = ttk.Frame(parent, style="Panel.TFrame")
        button_row.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)
        button_row.columnconfigure(2, weight=1)
        ttk.Button(button_row, text="미리보기", command=self.refresh_sweep_preview).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            button_row,
            text="스윕 확인",
            command=lambda: self.start_sweep(dry_run=True, matrix_text=self.sweep_matrix_text.get("1.0", "end-1c")),
        ).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(
            button_row,
            text="스윕 시작",
            style="Accent.TButton",
            command=lambda: self.start_sweep(dry_run=False, matrix_text=self.sweep_matrix_text.get("1.0", "end-1c")),
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.sweep_preview_text = ScrolledText(parent, height=8, wrap="word", font=("Malgun Gothic", 9), bg="#f8fafc", bd=0)
        self.sweep_preview_text.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 12))
        self.refresh_sweep_preview()

    def refresh_sweep_preview(self) -> None:
        if not hasattr(self, "sweep_preview_text"):
            return
        self.sweep_preview_text.delete("1.0", END)
        try:
            parameter = self.sweep_parameter.get().strip()
            plan = self.current_plan()
            params = plan.get("parameters", {}) if isinstance(plan, dict) else {}
            values = [] if parameter == SWEEP_ALL else self.parse_sweep_values()
            matrix_text = self.sweep_matrix_text.get("1.0", "end-1c") if hasattr(self, "sweep_matrix_text") else ""
            cases = self.build_sweep_cases(plan, parameter, values, matrix_text)
            current = params.get(parameter, "여러 변수") if isinstance(params, dict) else "없음"
            lines = [
                f"현재 {parameter} = {current}",
                f"실행될 케이스: {len(cases)}개",
                "한 CST 프로젝트 안에서 StoreParameter -> Rebuild -> Solver Start를 케이스별로 반복합니다.",
                "가능하면 각 케이스의 Touchstone을 exports 폴더에 저장하고 마지막에 S11/S21을 한 표로 합칩니다.",
                "",
            ]
            for case in cases[:30]:
                lines.append("- " + ", ".join(f"{key}={value}" for key, value in case.items()))
            if len(cases) > 30:
                lines.append(f"... 외 {len(cases) - 30}개")
            self.sweep_preview_text.insert("1.0", "\n".join(lines))
        except Exception as exc:
            self.sweep_preview_text.insert("1.0", f"미리보기 오류: {exc}")

    def load_example_plan(self) -> None:
        try:
            text = EXAMPLE_PLAN.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("예제 불러오기 실패", str(exc))
            return
        self.plan_text.delete("1.0", END)
        self.plan_text.insert("1.0", text)
        self.plan_source.set("wizard")
        try:
            self.sync_wizard_from_plan(json.loads(text))
        except Exception:
            pass
        self.update_param_summary()
        self.refresh_sweep_preview()
        self.status.set("기본 모기장 유닛셀 예제를 불러왔습니다.")

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
        win.title("숫자 직접 입력")
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
        ttk.Label(frm, text="Floquet mode number").grid(row=len(labels), column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=self.floquet_modes).grid(row=len(labels), column=1, sticky="ew", pady=4)
        ttk.Label(frm, text="Solver").grid(row=len(labels) + 1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frm,
            textvariable=self.solver_type,
            values=("HF Time Domain", "HF Frequency Domain"),
            state="readonly",
        ).grid(row=len(labels) + 1, column=1, sticky="ew", pady=4)
        ttk.Checkbutton(frm, text="x/y 유닛셀 경계조건 포함", variable=self.include_boundary).grid(
            row=len(labels) + 2, column=1, sticky="w", pady=8
        )
        ttk.Label(
            frm,
            text="기본값은 Background Normal, x/y unit cell, z open add space, Floquet modes=2, Time Domain solver입니다.",
            foreground=self.colors["muted"],
        ).grid(row=len(labels) + 3, column=0, columnspan=2, sticky="w", pady=(4, 10))

        ttk.Button(
            frm,
            text="JSON 만들기",
            style="Accent.TButton",
            command=lambda: self.apply_wizard_from_dialog(win),
        ).grid(row=len(labels) + 4, column=0, columnspan=2, sticky="ew")

    def apply_wizard_from_dialog(self, win: Toplevel) -> None:
        if self.apply_wizard_plan():
            win.destroy()
            self.notebook.select(1)

    def apply_request_to_wizard(self) -> None:
        request = self.request_text.get("1.0", "end-1c")
        found = self.extract_request_values(request)
        for key, value in found.items():
            if key in self.wizard_vars:
                self.wizard_vars[key].set(value)
        self.include_boundary.set(True)
        if self.apply_wizard_plan():
            self.rf_check(show_only=False)
            self.notebook.select(0)
            changed = ", ".join(f"{key}={value}" for key, value in found.items()) or "기본값 유지"
            self.append_output(f"[flow] 대사를 기본 유닛셀 값에 반영했습니다: {changed}\n")
            self.append_output("[flow] 다음은 '2. 실행 전 확인' 또는 바로 '3. 시뮬레이션 시작'을 누르면 됩니다.\n\n")
            self.status.set("대사 적용 완료")

    def extract_request_values(self, text: str) -> dict[str, str]:
        found: dict[str, str] = {}
        aliases = {
            "length": ["length", "len", "길이", "외곽", "space", "스페이스"],
            "width": ["width", "w", "폭", "선폭", "실폭"],
            "thickness": ["thickness", "t", "두께"],
            "fmin": ["fmin", "시작 주파수", "최소 주파수"],
            "fmax": ["fmax", "끝 주파수", "최대 주파수"],
        }
        for key, names in aliases.items():
            value = self.find_named_number(text, names)
            if value is not None:
                found[key] = value

        ghz_range = re.search(
            r"([-+]?\d+(?:\.\d+)?)\s*(?:GHz)?\s*(?:부터|에서|~|-|to)\s*([-+]?\d+(?:\.\d+)?)\s*GHz",
            text,
            flags=re.IGNORECASE,
        )
        if ghz_range:
            found.setdefault("fmin", ghz_range.group(1))
            found.setdefault("fmax", ghz_range.group(2))
        return found

    def find_named_number(self, text: str, names: list[str]) -> str | None:
        for name in names:
            pattern = rf"{re.escape(name)}[^\d+\-]{{0,12}}([-+]?\d+(?:\.\d+)?)"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def open_sweep_dialog(self) -> None:
        self.seed_sweep_defaults()
        if hasattr(self, "sweep_matrix_text"):
            self.sweep_matrix_text.delete("1.0", END)
            self.sweep_matrix_text.insert("1.0", self.default_sweep_matrix_text())
        self.refresh_sweep_preview()
        self.notebook.select(self.sweep_tab)

    def seed_sweep_defaults(self) -> None:
        try:
            plan = self.current_plan()
            params = plan.get("parameters", {}) if isinstance(plan, dict) else {}
        except Exception:
            params = {}
        if isinstance(params, dict):
            for key in ("width", "length", "thickness", "fmin", "fmax"):
                if key in params:
                    self.sweep_parameter.set(key)
                    break
            current = params.get(self.sweep_parameter.get())
            if current is not None:
                try:
                    number = float(current)
                    if self.sweep_parameter.get() == "width":
                        values = [max(number * 0.5, 0.001), number, number * 1.5]
                    else:
                        values = [number * 0.8, number, number * 1.2]
                    self.sweep_values.set(", ".join(f"{value:.12g}" for value in values))
                except Exception:
                    if not self.sweep_values.get().strip():
                        self.sweep_values.set("5, 10, 15")

    def default_sweep_matrix_text(self) -> str:
        try:
            plan = self.current_plan()
            params = plan.get("parameters", {}) if isinstance(plan, dict) else {}
        except Exception:
            params = {}

        def values_for(key: str) -> str:
            raw = params.get(key) if isinstance(params, dict) else None
            try:
                value = float(raw)
            except Exception:
                defaults = {
                    "length": "80, 100, 120",
                    "width": "5, 10, 15",
                    "thickness": "1, 2, 3",
                    "fmin": "1",
                    "fmax": "18",
                }
                return defaults[key]
            if key == "width":
                values = [max(value * 0.5, 0.001), value, value * 1.5]
            elif key in {"length", "thickness"}:
                values = [max(value * 0.8, 0.001), value, value * 1.2]
            else:
                values = [value]
            return ", ".join(f"{item:.12g}" for item in values)

        return "\n".join(
            f"{key}={values_for(key)}" for key in ("length", "width", "thickness", "fmin", "fmax")
        )

    def parse_sweep_values(self) -> list[str]:
        raw = self.sweep_values.get().strip()
        values = [item for item in re.split(r"[\s,]+", raw) if item]
        if not values:
            raise ValueError("스윕 값 목록이 비어 있습니다.")
        for value in values:
            float(value)
        return values

    def start_sweep(self, dry_run: bool, matrix_text: str = "") -> bool:
        if self.running:
            messagebox.showinfo("실행 중", "이미 실행 중입니다.")
            return False
        if not self.sync_wizard_parameters_if_needed():
            return False
        try:
            base_plan = self.current_plan()
            parameter = self.sweep_parameter.get().strip()
            values = [] if parameter == SWEEP_ALL else self.parse_sweep_values()
            cases = self.build_sweep_cases(base_plan, parameter, values, matrix_text)
            sweep_root = self.make_run_dir(f"sweep_{parameter}")
            commands, cleanup_files = self.build_sweep_commands(base_plan, cases, dry_run=dry_run, sweep_root=sweep_root)
        except Exception as exc:
            messagebox.showerror("스윕 준비 실패", str(exc))
            return False
        if not commands:
            messagebox.showerror("스윕 준비 실패", "실행할 스윕 값이 없습니다.")
            return False

        self.running = True
        self.pending_result_dir = None if dry_run else sweep_root
        self.after_run_action = None if dry_run else "collect_results"
        self.last_exit_code = None
        self.clear_output()
        self.notebook.select(0)
        mode = "스윕 확인" if dry_run else "스윕 시작"
        self.status.set(f"{mode} 중...")
        self.append_output(f"[sweep] parameter_mode={parameter}, cases={len(cases)}\n")
        self.append_output("[sweep] flow=StoreParameter -> Rebuild -> Solver Start -> optional Touchstone export\n")
        if not dry_run:
            self.append_output(f"[sweep] result_root={sweep_root}\n")
        for case in cases[:30]:
            self.append_output("[sweep] " + ", ".join(f"{key}={value}" for key, value in case.items()) + "\n")
        if len(cases) > 30:
            self.append_output(f"[sweep] ... 외 {len(cases) - 30}개\n")
        self.append_output("\n")
        threading.Thread(target=self.sweep_worker, args=(commands, mode, cleanup_files), daemon=True).start()
        self.root.after(80, self.drain_output_queue)
        return True

    def build_sweep_cases(self, base_plan: dict, parameter: str, values: list[str], matrix_text: str) -> list[dict[str, str]]:
        if parameter == SWEEP_ALL:
            return self.parse_sweep_matrix(base_plan, matrix_text)
        if not parameter:
            raise ValueError("스윕 파라미터 이름이 비어 있습니다.")
        params = base_plan.get("parameters")
        if not isinstance(params, dict):
            raise ValueError("parameters는 object여야 합니다.")
        if parameter not in params:
            raise ValueError(f"현재 JSON parameters에 '{parameter}'가 없습니다.")
        return [{parameter: value} for value in values]

    def parse_sweep_matrix(self, base_plan: dict, matrix_text: str) -> list[dict[str, str]]:
        params = base_plan.get("parameters")
        if not isinstance(params, dict):
            raise ValueError("parameters는 object여야 합니다.")
        series: dict[str, list[str]] = {}
        for line in matrix_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key, raw_values = stripped.split("=", 1)
            elif ":" in stripped:
                key, raw_values = stripped.split(":", 1)
            else:
                raise ValueError(f"값표 형식이 잘못되었습니다: {line}")
            key = key.strip()
            if key not in params:
                raise ValueError(f"현재 JSON parameters에 '{key}'가 없습니다.")
            values = [item for item in re.split(r"[\s,]+", raw_values.strip()) if item]
            if not values:
                raise ValueError(f"{key} 값 목록이 비어 있습니다.")
            for value in values:
                float(value)
            series[key] = values
        if not series:
            raise ValueError("전체 변수 값표가 비어 있습니다.")
        keys = list(series)
        cases = [{key: value for key, value in zip(keys, combo)} for combo in product(*(series[key] for key in keys))]
        if len(cases) > 500:
            raise ValueError(f"스윕 케이스가 {len(cases)}개입니다. 500개 이하로 줄여 주세요.")
        return cases

    def build_sweep_commands(
        self,
        base_plan: dict,
        cases: list[dict[str, str]],
        dry_run: bool,
        sweep_root: Path,
    ) -> tuple[list[list[str]], list[Path]]:
        params = base_plan.get("parameters")
        if not isinstance(params, dict):
            raise ValueError("parameters는 object여야 합니다.")

        for updates in cases:
            for key in updates:
                if key not in params:
                    raise ValueError(f"현재 JSON parameters에 '{key}'가 없습니다.")

        plan = copy.deepcopy(base_plan)
        plan = self.prepare_solver_plan(plan, None)
        plan["design_id"] = f"{plan.get('design_id') or 'mesh_frame_unitcell'}_sweep"
        plan_commands = plan.get("commands")
        if not isinstance(plan_commands, list):
            raise ValueError("commands는 list여야 합니다.")
        base_commands = [
            item
            for item in plan_commands
            if not (isinstance(item, dict) and item.get("op") in {"solver_start", "export_touchstone"})
        ]
        export_template = str(sweep_root / "exports" / "case_{case_index}_{case_slug}.s2p")
        base_commands.append(
            {
                "op": "case_sweep",
                "cases": cases,
                "commands": [
                    {"op": "solver_start", "solver": self.solver_kind_from_plan(plan)},
                    {"op": "export_touchstone", "path": export_template, "impedance": 50, "optional": True},
                ],
            }
        )
        plan["commands"] = base_commands

        plan_path = self.write_runtime_plan(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            f"sweep_{self.safe_slug(plan['design_id'])}",
        )
        cmd = [sys.executable, str(RUNNER), str(plan_path), "--prog-id", self.prog_id.get().strip(), "--store-parameters", "--keep-expressions"]
        if dry_run:
            cmd.extend(["--dry-run", "--no-project-save"])
        elif self.visible.get():
            cmd.append("--visible")
        if not dry_run:
            cmd.extend(["--run-dir", str(sweep_root)])
        return [cmd], [plan_path]

    def sweep_worker(self, commands: list[list[str]], mode: str, cleanup_files: list[Path]) -> None:
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
            self.cleanup_temp_files(cleanup_files)
            self.last_exit_code = worst_code
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
        try:
            modes = int(self.floquet_modes.get().strip())
        except ValueError as exc:
            raise ValueError("Floquet mode number는 정수여야 합니다.") from exc
        if modes <= 0:
            raise ValueError("Floquet mode number는 1 이상이어야 합니다.")
        return values

    def build_wizard_plan(self) -> dict:
        values = self.validate_wizard_values()
        commands: list[dict] = [
            {"op": "units", "geometry": "um", "frequency": "GHz", "time": "ns"},
            {"op": "solver_type", "type": self.solver_type.get().strip() or "HF Time Domain"},
            {"op": "background", "type": "Normal", "epsilon": "1", "mue": "1"},
            {"op": "frequency_range", "fmin": "fmin", "fmax": "fmax"},
        ]
        commands.extend(
            [
                {
                    "op": "brick",
                    "name": "thread_top_x",
                    "component": "unitcell",
                    "material": "PEC",
                    "xrange": ["0", "length"],
                    "yrange": ["-width", "0"],
                    "zrange": ["0", "thickness"],
                },
                {
                    "op": "brick",
                    "name": "thread_left_y",
                    "component": "unitcell",
                    "material": "PEC",
                    "xrange": ["0", "width"],
                    "yrange": ["-length", "0"],
                    "zrange": ["0", "thickness"],
                },
                {
                    "op": "brick",
                    "name": "thread_bottom_x",
                    "component": "unitcell",
                    "material": "PEC",
                    "xrange": ["0", "length"],
                    "yrange": ["-length", "-length+width"],
                    "zrange": ["0", "thickness"],
                },
                {
                    "op": "brick",
                    "name": "thread_right_y",
                    "component": "unitcell",
                    "material": "PEC",
                    "xrange": ["length-width", "length"],
                    "yrange": ["-length", "0"],
                    "zrange": ["0", "thickness"],
                },
                {"op": "rebuild"},
            ]
        )
        if self.include_boundary.get():
            commands.append(
                {
                    "op": "boundary",
                    "xmin": "unit cell",
                    "xmax": "unit cell",
                    "ymin": "unit cell",
                    "ymax": "unit cell",
                    "zmin": "expanded open",
                    "zmax": "expanded open",
                }
            )
        commands.extend(
            [
                {
                    "op": "floquet_port",
                    "modes": self.floquet_modes.get().strip() or "2",
                    "ports": ["Zmin", "Zmax"],
                    "theta": "0",
                    "phi": "0",
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
        self.update_param_summary()
        self.refresh_sweep_preview()

    def sync_wizard_from_plan(self, plan: dict) -> None:
        params = plan.get("parameters", {})
        if isinstance(params, dict):
            for key, var in self.wizard_vars.items():
                if key in params:
                    var.set(str(params[key]))
        commands = plan.get("commands", [])
        if isinstance(commands, list):
            self.include_boundary.set(
                any(isinstance(item, dict) and item.get("op") == "boundary" for item in commands)
            )
            for item in commands:
                if isinstance(item, dict) and item.get("op") == "solver_type":
                    self.solver_type.set(str(item.get("type", "HF Time Domain")))
                if isinstance(item, dict) and item.get("op") == "floquet_port":
                    self.floquet_modes.set(str(item.get("modes", item.get("mode_count", "2"))))
        self.update_param_summary()

    def update_param_summary(self) -> None:
        values = self.wizard_values()
        boundary = "x/y unit cell" if self.include_boundary.get() else "경계조건 없음"
        self.param_summary.set(
            "현재 기본값: "
            f"length={values.get('length')} um, "
            f"width={values.get('width')} um, "
            f"thickness={values.get('thickness')} um, "
            f"{values.get('fmin')}~{values.get('fmax')} GHz, {boundary}, "
            f"Background Normal, {self.solver_type.get().strip() or 'HF Time Domain'}, "
            f"Floquet modes={self.floquet_modes.get().strip() or '2'}"
        )

    def current_plan(self) -> dict:
        data = json.loads(self.plan_text.get("1.0", "end-1c"))
        if not isinstance(data, dict):
            raise ValueError("JSON 최상위는 object여야 합니다.")
        return data

    def make_run_dir(self, prefix: str) -> Path:
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        return APP_DIR / "runs" / f"{timestamp}_{self.safe_slug(prefix)}"

    def prepare_solver_plan(self, base_plan: dict, export_path: Path | None, include_solver: bool = True) -> dict:
        return plan_defaults.prepare_solver_plan(
            base_plan,
            export_path,
            include_solver=include_solver,
            solver_type=self.solver_type.get().strip() or plan_defaults.DEFAULT_SOLVER_TYPE,
            floquet_modes=self.floquet_modes.get().strip() or plan_defaults.DEFAULT_FLOQUET_MODES,
        )

    def normalize_simulation_setup(self, base_plan: dict) -> dict:
        return plan_defaults.normalize_simulation_setup(
            base_plan,
            solver_type=self.solver_type.get().strip() or plan_defaults.DEFAULT_SOLVER_TYPE,
            floquet_modes=self.floquet_modes.get().strip() or plan_defaults.DEFAULT_FLOQUET_MODES,
        )

    def solver_kind_from_plan(self, plan: dict) -> str:
        return plan_defaults.solver_kind_from_plan(plan)

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
        try:
            plan = self.prepare_solver_plan(self.current_plan(), None, include_solver=True)
            self.set_plan(plan, source=self.plan_source.get())
        except Exception as exc:
            messagebox.showerror("실행 전 확인 실패", str(exc))
            return
        self.rf_check(show_only=False)
        self.run_plan(
            dry_run=True,
            plan_text=json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            mode_label="실행 전 확인",
        )

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
        if "background" in ops:
            messages.append("[ok] Background 설정이 있습니다. 기본은 Normal, epsilon=1, mue=1입니다.")
        else:
            messages.append("[warn] Background 설정이 없습니다. 실행 시 기본 Normal 배경을 자동 추가합니다.")
        if "boundary" in ops:
            messages.append("[ok] Boundary 설정이 있습니다. 기본은 x/y unit cell, z open add space입니다.")
        else:
            messages.append("[warn] Boundary 설정이 없습니다. 실행 시 기본 unit cell/open add space 경계를 자동 추가합니다.")
        if "solver_type" in ops:
            solver_types = [
                str(item.get("type", ""))
                for item in commands
                if isinstance(item, dict) and item.get("op") == "solver_type"
            ]
            messages.append(f"[ok] Solver type: {solver_types[-1] if solver_types else '설정됨'}")
        else:
            messages.append("[warn] Solver type이 없습니다. 실행 시 HF Time Domain을 자동 추가합니다.")
        if "floquet_port" in ops:
            messages.append("[ok] Floquet port 설정이 있습니다. 기본 mode number는 2입니다.")
        elif "discrete_port" not in ops:
            messages.append("[warn] 현재 JSON에는 S-parameter용 포트/Floquet 설정이 없습니다. CST가 S11/S21을 만들지 못할 수 있습니다.")
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

    def debug_plan_before_start(self, plan: dict) -> bool:
        messages, ok = plan_defaults.simulation_readiness_report(plan)
        self.clear_output()
        self.append_output("=== 시작 전 설정 디버그 ===\n")
        self.append_output("\n".join(messages) + "\n\n")
        if not ok:
            self.append_output("[stop] 설정 디버그에서 error가 있어 CST 시뮬레이션을 시작하지 않았습니다.\n\n")
            self.notebook.select(0)
            return False

        try:
            output = self.run_dry_debug(plan)
        except Exception as exc:
            self.append_output(f"[stop] dry-run 매크로 생성 실패: {exc}\n\n")
            self.notebook.select(0)
            return False
        self.append_output("=== dry-run 매크로 생성 확인 ===\n")
        self.append_output(output)
        if output and not output.endswith("\n"):
            self.append_output("\n")
        self.append_output("[ok] 시작 전 디버그 통과. 이제 CST 시뮬레이션을 시작합니다.\n\n")
        self.notebook.select(0)
        return True

    def run_dry_debug(self, plan: dict) -> str:
        text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
        temp_plan = self.write_runtime_plan(text, "debug_start")
        cmd = [
            sys.executable,
            str(RUNNER),
            str(temp_plan),
            "--prog-id",
            self.prog_id.get().strip(),
            "--dry-run",
            "--no-project-save",
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(APP_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            output = proc.stdout or ""
            if proc.returncode != 0:
                raise RuntimeError(f"dry-run 종료코드 {proc.returncode}\n{output}")
            return output
        finally:
            self.cleanup_temp_files([temp_plan])

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
        plan = self.normalize_simulation_setup(plan)
        self.sync_wizard_from_plan(plan)
        self.set_plan(plan, source="llm")
        self.append_output("[llm] JSON 변환 완료. 누락된 Background/Boundary/Solver/Floquet 기본값도 자동 보정했습니다.\n")
        self.append_output("[flow] 실행 전 확인에서 CST에 들어갈 전체 설정을 검토할 수 있습니다.\n")
        self.status.set("LLM JSON 변환 완료")
        self.notebook.select(self.json_tab)

    def run_simulation(self) -> None:
        if not self.sync_wizard_parameters_if_needed():
            return
        try:
            base_plan = self.current_plan()
            run_dir = self.make_run_dir(str(base_plan.get("design_id") or "mesh_frame_unitcell"))
            plan = self.prepare_solver_plan(base_plan, None, include_solver=True)
            project = plan.setdefault("project", {"mode": "new"})
            if isinstance(project, dict):
                project["save_as"] = str(run_dir / "cst_project.cst")
        except Exception as exc:
            messagebox.showerror("실행 준비 실패", str(exc))
            return

        self.set_plan(plan, source=self.plan_source.get())
        if not self.debug_plan_before_start(plan):
            return
        self.pending_result_dir = None
        self.after_run_action = None
        self.append_output("[flow] CST에서 Background/Boundary/Floquet을 설정하고 Solver Start를 실행합니다.\n")
        self.append_output("[flow] Touchstone export는 자동으로 붙이지 않습니다. CST 해석 완료 후 결과 불러오기를 사용하세요.\n\n")
        self.run_plan(
            False,
            plan_text=json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            mode_label="CST 시뮬레이션 시작",
            extra_args=["--run-dir", str(run_dir)],
        )

    def run_active_simulation(self) -> None:
        try:
            run_dir = self.make_run_dir("active_cst_solver")
            plan = {
                "design_id": "active_cst_solver",
                "project": {"mode": "active"},
                "parameters": {},
                "commands": [
                    {"op": "solver_type", "type": self.solver_type.get().strip() or "HF Time Domain"},
                    {"op": "background", "type": "Normal", "epsilon": "1", "mue": "1"},
                    {
                        "op": "boundary",
                        "xmin": "unit cell",
                        "xmax": "unit cell",
                        "ymin": "unit cell",
                        "ymax": "unit cell",
                        "zmin": "expanded open",
                        "zmax": "expanded open",
                    },
                    {
                        "op": "floquet_port",
                        "modes": self.floquet_modes.get().strip() or "2",
                        "ports": ["Zmin", "Zmax"],
                        "theta": "0",
                        "phi": "0",
                    },
                    {"op": "rebuild"},
                    {
                        "op": "solver_start",
                        "solver": "time" if "time" in self.solver_type.get().lower() else "frequency",
                    },
                ],
            }
        except Exception as exc:
            messagebox.showerror("시뮬레이션 준비 실패", str(exc))
            return

        self.pending_result_dir = None
        self.after_run_action = None
        if not self.debug_plan_before_start(plan):
            return
        self.append_output("[flow] 현재 열려 있는 CST 프로젝트에 붙어서 Solver Start를 실행합니다.\n")
        self.append_output("[flow] Touchstone export는 자동으로 붙이지 않습니다. CST 해석 완료 후 결과 불러오기를 사용하세요.\n\n")
        self.run_plan(
            False,
            plan_text=json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            mode_label="현재 CST 시뮬레이션",
            extra_args=["--run-dir", str(run_dir), "--visible"],
        )

    def collect_sparams_dialog(self) -> None:
        if self.running:
            messagebox.showinfo("실행 중", "이미 실행 중입니다.")
            return
        folder = filedialog.askdirectory(
            title="S11/S21 결과가 있는 폴더 선택",
            initialdir=str(APP_DIR),
        )
        if not folder:
            return
        root = Path(folder)
        self.collect_and_show_results(root)

    def collect_and_show_results(self, root: Path) -> None:
        try:
            candidate_files = self.find_result_candidates(root)
            rows = collect_sparams.collect(root)
            output = root / "s11_s21_summary.csv"
            collect_sparams.write_summary(output, rows)
        except Exception as exc:
            messagebox.showerror("S11/S21 정리 실패", str(exc))
            return
        self.show_result_rows(rows, output, root, candidate_files)
        self.append_output(f"[collect] rows={len(rows)}\n")
        self.append_output(f"[collect] output={output}\n\n")
        if not rows:
            self.append_output("[collect] S11/S21 데이터가 없습니다. 결과 탭의 안내를 확인하세요.\n\n")
        self.status.set(f"S11/S21 정리 완료: {len(rows)} rows")

    def find_result_candidates(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        suffixes = {".s2p", ".csv", ".txt"}
        return [
            path
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix.lower() in suffixes and path.name.lower() != "s11_s21_summary.csv"
        ]

    def show_result_rows(self, rows: list[dict[str, str]], output: Path, root: Path, candidate_files: list[Path]) -> None:
        self.result_text.delete("1.0", END)
        lines = [f"summary: {output}", f"rows: {len(rows)}", ""]
        numeric_rows = []
        for row in rows:
            try:
                numeric_rows.append((float(row["freq_ghz"]), float(row["s11_db"]), float(row["s21_db"])))
            except Exception:
                pass
        if numeric_rows:
            min_s11 = min(item[1] for item in numeric_rows)
            min_s21 = min(item[2] for item in numeric_rows)
            max_s21 = max(item[2] for item in numeric_rows)
            lines.extend(
                [
                    f"min S11: {min_s11:.3f} dB",
                    f"min S21: {min_s21:.3f} dB",
                    f"max S21: {max_s21:.3f} dB",
                    "",
                ]
            )
        if rows:
            lines.append(f"{'freq_ghz':>12} {'s11_db':>12} {'s21_db':>12}  source")
            lines.append("-" * 78)
            for row in rows[:300]:
                source = Path(row.get("source", "")).name
                lines.append(
                    f"{row.get('freq_ghz', ''):>12} {row.get('s11_db', ''):>12} {row.get('s21_db', ''):>12}  {source}"
                )
            if len(rows) > 300:
                lines.append(f"... 외 {len(rows) - 300} rows")
        else:
            expected = root / "exports" / "sparameters.s2p"
            lines.extend(
                [
                    "S11/S21 데이터를 찾지 못했습니다.",
                    "",
                    "확인할 것:",
                    f"- 자동 export 예상 파일: {expected}",
                    f"- 파일 존재 여부: {'있음' if expected.exists() else '없음'}",
                    f"- 읽을 수 있는 후보 파일 수: {len(candidate_files)}",
                    "",
                    "가능성이 큰 원인:",
                    "- CST solver가 끝나기 전에 export가 시도됐거나 solver가 실패했습니다.",
                    "- Floquet port 설정은 들어갔지만 CST에서 해당 모델/solver 조건을 거부했을 수 있습니다.",
                    "- CST 결과 트리에 S-Parameters가 생기지 않으면 Touchstone export도 비어 있을 수 있습니다.",
                    "",
                    "지금 할 수 있는 확인:",
                    "- CST 화면에서 해석 결과 트리에 S-Parameters가 생겼는지 확인",
                    "- CST에서 Touchstone .s2p를 직접 export한 뒤 `결과 불러오기`로 그 폴더 선택",
                ]
            )
            if candidate_files:
                lines.extend(["", "발견된 후보 파일:"])
                for path in candidate_files[:20]:
                    lines.append(f"- {path}")
                if len(candidate_files) > 20:
                    lines.append(f"... 외 {len(candidate_files) - 20}개")
        self.result_text.insert("1.0", "\n".join(lines) + "\n")
        self.notebook.select(self.result_tab)

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
            temp_plan = self.write_runtime_plan(text, "single_run")
        except Exception as exc:
            messagebox.showerror("실행 준비 실패", str(exc))
            return

        cmd = [sys.executable, str(RUNNER), str(temp_plan), "--prog-id", self.prog_id.get().strip()]
        if dry_run:
            cmd.append("--dry-run")
        elif self.visible.get():
            cmd.append("--visible")
        if extra_args:
            cmd.extend(extra_args)

        self.running = True
        self.last_exit_code = None
        self.append_output(f"\n$ {' '.join(cmd)}\n\n")
        self.notebook.select(0)
        self.status.set(f"{mode_label or '실행'} 중...")
        threading.Thread(target=self.worker, args=(cmd, mode_label or "실행", [temp_plan]), daemon=True).start()
        self.root.after(80, self.drain_output_queue)

    def worker(self, cmd: list[str], mode: str, cleanup_files: list[Path]) -> None:
        try:
            code = self.run_subprocess_to_queue(cmd)
            self.last_exit_code = code
            self.output_queue.put(f"\n[{mode} 종료 코드: {code}]\n")
        except Exception as exc:
            self.last_exit_code = 1
            self.output_queue.put(f"\n[실행 실패] {exc}\n")
        finally:
            self.cleanup_temp_files(cleanup_files)
            self.output_queue.put(None)

    def write_runtime_plan(self, text: str, prefix: str) -> Path:
        RUNTIME_TMP.mkdir(parents=True, exist_ok=True)
        fd, path_text = tempfile.mkstemp(prefix=f"{prefix}_", suffix=".json", dir=str(RUNTIME_TMP))
        path = Path(path_text)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def cleanup_temp_files(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            RUNTIME_TMP.rmdir()
        except Exception:
            pass

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
            if self.after_run_action == "collect_results":
                self.after_run_action = None
                result_dir = self.pending_result_dir
                self.pending_result_dir = None
                if result_dir is not None:
                    if self.last_exit_code not in (0, None):
                        self.append_output("[collect] 실행 중 에러가 있었지만 생성된 결과가 있는지 확인합니다.\n")
                    self.root.after(100, lambda: self.collect_and_show_results(result_dir))
                return
            return
        self.root.after(80, self.drain_output_queue)

    def mark_not_running(self) -> None:
        self.running = False

    def append_output(self, text: str) -> None:
        self.output_text.insert(END, text)
        self.output_text.see(END)

    def clear_output(self) -> None:
        self.output_text.delete("1.0", END)


def main() -> None:
    root = Tk()
    CSTVibeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
