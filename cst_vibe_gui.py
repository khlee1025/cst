#!/usr/bin/env python
"""
Modern-ish desktop GUI for CST Vibe Runner.

This intentionally uses only tkinter from the Python standard library so the
first version can run on a CST workstation without extra GUI packages.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BOTH, END, HORIZONTAL, LEFT, RIGHT, VERTICAL, X, Y, BooleanVar, StringVar, Tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk


APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "cst_vibe_runner.py"
EXAMPLE_PLAN = APP_DIR / "examples" / "02_patch_unitcell_no_ports.json"
PROMPT_FILE = APP_DIR / "prompt_for_local_llm.md"
TEMP_PLAN = APP_DIR / ".cst_vibe_gui_last_plan.json"


class CSTVibeGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("CST Vibe Runner")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)

        self.plan_path = StringVar(value=str(EXAMPLE_PLAN))
        self.status = StringVar(value="준비됨")
        self.prog_id = StringVar(value="CSTStudio.Application")
        self.visible = BooleanVar(value=True)
        self.running = False
        self.output_queue: queue.Queue[str | None] = queue.Queue()

        self.colors = {
            "bg": "#f5f7fb",
            "panel": "#ffffff",
            "panel2": "#eef2f7",
            "text": "#111827",
            "muted": "#667085",
            "border": "#d8dee9",
            "accent": "#2563eb",
            "accent_hover": "#1d4ed8",
            "danger": "#b42318",
            "console": "#0b1020",
            "console_text": "#d1e7ff",
        }

        self.configure_style()
        self.build_layout()
        self.load_example()

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
        style.configure("Status.TLabel", background=self.colors["panel2"], foreground=self.colors["muted"])
        style.configure("TButton", padding=(12, 7), borderwidth=0)
        style.map("TButton", background=[("active", self.colors["panel2"])])
        style.configure(
            "Accent.TButton",
            foreground="#ffffff",
            background=self.colors["accent"],
            padding=(14, 8),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", self.colors["accent_hover"]), ("disabled", "#9ca3af")],
            foreground=[("disabled", "#eef2f7")],
        )
        style.configure("Danger.TButton", foreground="#ffffff", background=self.colors["danger"])
        style.configure("TCheckbutton", background=self.colors["panel"], foreground=self.colors["text"])
        style.configure("TEntry", fieldbackground="#ffffff", bordercolor=self.colors["border"])
        style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8), background=self.colors["panel2"])
        style.map("TNotebook.Tab", background=[("selected", self.colors["panel"])])

    def build_layout(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(22, 16))
        header.pack(fill=X)

        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.pack(side=LEFT, fill=X, expand=True)
        ttk.Label(
            title_box,
            text="CST Vibe Runner",
            style="Header.TLabel",
            font=("Segoe UI Semibold", 18),
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text="로컬 LLM이 만든 JSON 명령서를 CST 자동화로 실행",
            style="Header.TLabel",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 0))

        ttk.Button(header, text="LLM 프롬프트 복사", command=self.copy_prompt).pack(side=RIGHT)

        main = ttk.PanedWindow(self.root, orient=HORIZONTAL)
        main.pack(fill=BOTH, expand=True, padx=14, pady=14)

        left = ttk.Frame(main, style="Panel.TFrame", padding=16)
        right = ttk.Frame(main, style="Panel.TFrame", padding=12)
        main.add(left, weight=1)
        main.add(right, weight=3)

        self.build_left_panel(left)
        self.build_right_panel(right)

        status_bar = ttk.Frame(self.root, style="Panel.TFrame")
        status_bar.pack(fill=X, side="bottom")
        ttk.Label(status_bar, textvariable=self.status, style="Status.TLabel", padding=(12, 7)).pack(
            fill=X
        )

    def build_left_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="요청 메모",
            style="Panel.TLabel",
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w")
        ttk.Label(
            parent,
            text="여기에 네가 하고 싶은 CST 작업을 적고, 로컬 LLM에 보낸 뒤 JSON을 오른쪽에 붙여넣으면 됩니다.",
            style="Muted.TLabel",
            wraplength=300,
            justify=LEFT,
        ).pack(anchor="w", pady=(4, 10))

        self.request_text = ScrolledText(
            parent,
            height=12,
            wrap="word",
            bd=0,
            relief="flat",
            bg="#f8fafc",
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            font=("Malgun Gothic", 10),
            padx=10,
            pady=10,
        )
        self.request_text.pack(fill=BOTH, expand=False)
        self.request_text.insert(
            "1.0",
            "예: 주기 10 mm, FR4 두께 0.8 mm, 구리 패치 폭 7.2 mm인 차폐 유닛셀을 만들고 1-18 GHz로 설정해줘.",
        )

        ttk.Separator(parent).pack(fill=X, pady=16)

        ttk.Label(
            parent,
            text="CST 연결",
            style="Panel.TLabel",
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w")

        ttk.Label(parent, text="COM ProgID", style="Muted.TLabel").pack(anchor="w", pady=(8, 2))
        ttk.Entry(parent, textvariable=self.prog_id).pack(fill=X)
        ttk.Checkbutton(parent, text="CST UI 보이기", variable=self.visible).pack(anchor="w", pady=(10, 2))

        ttk.Separator(parent).pack(fill=X, pady=16)

        ttk.Label(
            parent,
            text="빠른 작업",
            style="Panel.TLabel",
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w")
        ttk.Button(parent, text="예제 불러오기", command=self.load_example).pack(fill=X, pady=(8, 4))
        ttk.Button(parent, text="JSON 정렬", command=self.format_json).pack(fill=X, pady=4)
        ttk.Button(parent, text="출력 복사", command=self.copy_output).pack(fill=X, pady=4)
        ttk.Button(parent, text="출력 지우기", command=self.clear_output).pack(fill=X, pady=4)

    def build_right_panel(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent, style="Panel.TFrame")
        toolbar.pack(fill=X, pady=(0, 10))

        ttk.Button(toolbar, text="열기", command=self.open_plan).pack(side=LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="저장", command=self.save_plan).pack(side=LEFT, padx=6)
        ttk.Button(toolbar, text="다른 이름 저장", command=self.save_plan_as).pack(side=LEFT, padx=6)
        ttk.Button(toolbar, text="CST 연동 테스트", command=self.run_connection_test).pack(
            side=LEFT, padx=6
        )

        ttk.Button(toolbar, text="CST 실행", style="Accent.TButton", command=self.run_cst).pack(
            side=RIGHT, padx=(6, 0)
        )
        ttk.Button(toolbar, text="드라이런", style="Accent.TButton", command=self.run_dry).pack(
            side=RIGHT, padx=6
        )

        path_row = ttk.Frame(parent, style="Panel.TFrame")
        path_row.pack(fill=X, pady=(0, 8))
        ttk.Label(path_row, text="파일", style="Muted.TLabel").pack(side=LEFT)
        ttk.Entry(path_row, textvariable=self.plan_path).pack(side=LEFT, fill=X, expand=True, padx=(8, 0))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=BOTH, expand=True)

        plan_tab = ttk.Frame(self.notebook, style="Panel.TFrame", padding=0)
        output_tab = ttk.Frame(self.notebook, style="Panel.TFrame", padding=0)
        self.notebook.add(plan_tab, text="JSON 명령서")
        self.notebook.add(output_tab, text="실행 출력")

        self.plan_text = ScrolledText(
            plan_tab,
            wrap="none",
            bd=0,
            relief="flat",
            bg="#fbfdff",
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            selectbackground="#bfdbfe",
            font=("Cascadia Mono", 10),
            padx=12,
            pady=12,
            undo=True,
        )
        self.plan_text.pack(fill=BOTH, expand=True)

        self.output_text = ScrolledText(
            output_tab,
            wrap="word",
            bd=0,
            relief="flat",
            bg=self.colors["console"],
            fg=self.colors["console_text"],
            insertbackground="#93c5fd",
            font=("Cascadia Mono", 10),
            padx=12,
            pady=12,
        )
        self.output_text.pack(fill=BOTH, expand=True)

    def copy_prompt(self) -> None:
        try:
            text = PROMPT_FILE.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("프롬프트 복사 실패", str(exc))
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status("로컬 LLM 프롬프트를 클립보드에 복사했습니다.")

    def load_example(self) -> None:
        try:
            text = EXAMPLE_PLAN.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("예제 불러오기 실패", str(exc))
            return
        self.plan_text.delete("1.0", END)
        self.plan_text.insert("1.0", text)
        self.plan_path.set(str(EXAMPLE_PLAN))
        self.set_status("예제 명령서를 불러왔습니다.")

    def open_plan(self) -> None:
        path = filedialog.askopenfilename(
            title="CST 명령서 열기",
            initialdir=str(APP_DIR),
            filetypes=[("Plan files", "*.json *.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("파일 열기 실패", str(exc))
            return
        self.plan_text.delete("1.0", END)
        self.plan_text.insert("1.0", text)
        self.plan_path.set(path)
        self.set_status(f"열림: {path}")

    def save_plan(self) -> None:
        path = Path(self.plan_path.get().strip())
        if not path:
            self.save_plan_as()
            return
        self.write_plan(path)

    def save_plan_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="CST 명령서 저장",
            initialdir=str(APP_DIR),
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("YAML", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not path:
            return
        self.plan_path.set(path)
        self.write_plan(Path(path))

    def write_plan(self, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.current_plan_text(), encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("저장 실패", str(exc))
            return False
        self.set_status(f"저장됨: {path}")
        return True

    def format_json(self) -> None:
        try:
            data = json.loads(self.current_plan_text())
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON 오류", f"{exc.msg}\nline {exc.lineno}, column {exc.colno}")
            return
        formatted = json.dumps(data, ensure_ascii=False, indent=2)
        self.plan_text.delete("1.0", END)
        self.plan_text.insert("1.0", formatted + "\n")
        self.set_status("JSON을 보기 좋게 정렬했습니다.")

    def run_dry(self) -> None:
        self.run_plan(dry_run=True)

    def run_cst(self) -> None:
        self.run_plan(dry_run=False)

    def run_connection_test(self) -> None:
        plan_text = json.dumps(
            {
                "project": {"mode": "new"},
                "parameters": {},
                "commands": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        self.run_plan(dry_run=False, plan_text=plan_text, mode_label="CST 연동 테스트")

    def run_plan(
        self,
        dry_run: bool,
        plan_text: str | None = None,
        mode_label: str | None = None,
    ) -> None:
        if self.running:
            messagebox.showinfo("실행 중", "이미 실행 중입니다.")
            return

        text = self.current_plan_text() if plan_text is None else plan_text
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            messagebox.showerror("JSON 오류", f"{exc.msg}\nline {exc.lineno}, column {exc.colno}")
            return

        try:
            TEMP_PLAN.write_text(text, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("임시 파일 저장 실패", str(exc))
            return

        cmd = [sys.executable, str(RUNNER), str(TEMP_PLAN), "--prog-id", self.prog_id.get().strip()]
        if dry_run:
            cmd.append("--dry-run")
        elif self.visible.get():
            cmd.append("--visible")

        self.running = True
        self.clear_output()
        mode = mode_label or ("드라이런" if dry_run else "CST 실행")
        self.append_output(f"$ {' '.join(cmd)}\n\n")
        self.set_status(f"{mode} 중...")
        self.notebook.select(1)

        thread = threading.Thread(target=self.worker, args=(cmd, mode), daemon=True)
        thread.start()
        self.root.after(80, self.drain_output_queue)

    def worker(self, cmd: list[str], mode: str) -> None:
        try:
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
            code = proc.wait()
            self.output_queue.put(f"\n[{mode} 종료 코드: {code}]\n")
        except Exception as exc:
            self.output_queue.put(f"\n[실행 실패] {exc}\n")
        finally:
            self.output_queue.put(None)

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
            self.running = False
            self.set_status("완료")
            return
        self.root.after(80, self.drain_output_queue)

    def current_plan_text(self) -> str:
        return self.plan_text.get("1.0", "end-1c")

    def append_output(self, text: str) -> None:
        self.output_text.insert(END, text)
        self.output_text.see(END)

    def clear_output(self) -> None:
        self.output_text.delete("1.0", END)

    def copy_output(self) -> None:
        text = self.output_text.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status("실행 출력을 클립보드에 복사했습니다.")

    def set_status(self, text: str) -> None:
        self.status.set(text)


def main() -> None:
    root = Tk()
    CSTVibeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
