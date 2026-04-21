#!/usr/bin/env python3
"""Desktop GUI launcher for safe ticket monitor."""

from __future__ import annotations

import datetime as dt
import email.utils
import json
import queue
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from site_presets import GUI_SITE_PRESETS

SITE_PRESETS = GUI_SITE_PRESETS


def normalize_path_for_site(site_name: str, suffix: str) -> str:
    normalized = suffix.strip()
    if not normalized:
        return normalized

    if site_name == "인터파크":
        normalized = normalized.lstrip("/")
        if not normalized.startswith("goods/"):
            normalized = f"goods/{normalized}"
    return normalized


class TicketGuiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Inter Macro - Safe Ticket Watch")
        self.root.geometry("900x680")

        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.base_dir = Path(__file__).resolve().parent
        self.settings_path = self.base_dir / "monitor_settings.json"

        self._build_vars()
        self._build_ui()
        self._load_settings()

        self.root.after(120, self._poll_logs)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_vars(self) -> None:
        self.site_var = tk.StringVar(value="직접 URL 입력")
        self.full_url_var = tk.StringVar(value="")
        self.path_var = tk.StringVar(value="")
        self.time_url_var = tk.StringVar(value="")
        self.people_var = tk.StringVar(value="2")
        self.start_mode_var = tk.StringVar(value="바로 시작")
        self.time_var = tk.StringVar(value="")
        self.date_text_var = tk.StringVar(value="")
        self.date_selector_var = tk.StringVar(value="")
        self.modal_close_selectors_var = tk.StringVar(value=".popupCloseBtn")
        self.round_text_var = tk.StringVar(value="")
        self.round_selector_var = tk.StringVar(value="")
        self.reserve_text_var = tk.StringVar(value="")
        self.reserve_selector_var = tk.StringVar(value=".sideBtn")
        self.selector_var = tk.StringVar(value="#remainSeatCount")
        self.interval_var = tk.StringVar(value="1.5")
        self.timeout_var = tk.StringVar(value="5000")
        self.headed_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="대기")

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill="both", expand=True)

        form = ttk.LabelFrame(container, text="실행 조건", padding=12)
        form.pack(fill="x")

        self._row_label(form, 0, "사이트")
        site_combo = ttk.Combobox(
            form,
            textvariable=self.site_var,
            values=list(SITE_PRESETS.keys()),
            state="readonly",
            width=20,
        )
        site_combo.grid(row=0, column=1, sticky="w")
        site_combo.bind("<<ComboboxSelected>>", lambda _e: self._toggle_url_mode())

        self._row_label(form, 1, "전체 URL")
        self.full_url_entry = ttk.Entry(form, textvariable=self.full_url_var, width=80)
        self.full_url_entry.grid(row=1, column=1, columnspan=4, sticky="ew", padx=(0, 6))

        self._row_label(form, 2, "뒤 경로(Path)")
        self.path_entry = ttk.Entry(form, textvariable=self.path_var, width=80)
        self.path_entry.grid(row=2, column=1, columnspan=4, sticky="ew", padx=(0, 6))

        ttk.Label(
            form,
            text="예: /goods/12345 또는 /Perf/98765",
            foreground="#666666",
        ).grid(row=3, column=1, columnspan=4, sticky="w", pady=(0, 8))

        self._row_label(form, 4, "인원수")
        ttk.Entry(form, textvariable=self.people_var, width=10).grid(row=4, column=1, sticky="w")

        self._row_label(form, 5, "시간 확인 URL")
        ttk.Entry(form, textvariable=self.time_url_var, width=60).grid(
            row=5, column=1, columnspan=3, sticky="ew"
        )
        ttk.Button(form, text="시간 확인", command=self.check_time_url).grid(row=5, column=4, sticky="e")

        self._row_label(form, 6, "자동 실행")
        ttk.Combobox(
            form,
            textvariable=self.start_mode_var,
            values=["바로 시작", "예약 시작"],
            state="readonly",
            width=12,
        ).grid(row=6, column=1, sticky="w")

        self._row_label(form, 7, "시작 시간")
        ttk.Entry(form, textvariable=self.time_var, width=24).grid(row=7, column=1, sticky="w")
        ttk.Label(form, text="형식: YYYY-MM-DD HH:MM:SS (예약 시작일 때 사용)").grid(
            row=7, column=2, columnspan=3, sticky="w"
        )

        self._row_label(form, 8, "일자 텍스트")
        ttk.Entry(form, textvariable=self.date_text_var, width=40).grid(row=8, column=1, sticky="w")

        self._row_label(form, 9, "일자 선택자(선택)")
        ttk.Entry(form, textvariable=self.date_selector_var, width=40).grid(row=9, column=1, sticky="w")

        self._row_label(form, 10, "모달 닫기 선택자")
        ttk.Entry(form, textvariable=self.modal_close_selectors_var, width=40).grid(
            row=10, column=1, sticky="w"
        )

        self._row_label(form, 11, "회차 텍스트")
        ttk.Entry(form, textvariable=self.round_text_var, width=40).grid(row=11, column=1, sticky="w")

        self._row_label(form, 12, "회차 선택자(선택)")
        ttk.Entry(form, textvariable=self.round_selector_var, width=40).grid(row=12, column=1, sticky="w")

        self._row_label(form, 13, "예매 버튼 텍스트")
        ttk.Entry(form, textvariable=self.reserve_text_var, width=40).grid(row=13, column=1, sticky="w")

        self._row_label(form, 14, "예매 버튼 선택자(선택)")
        ttk.Entry(form, textvariable=self.reserve_selector_var, width=40).grid(
            row=14, column=1, sticky="w"
        )

        self._row_label(form, 15, "CSS 선택자")
        ttk.Entry(form, textvariable=self.selector_var, width=40).grid(row=15, column=1, sticky="w")

        self._row_label(form, 16, "재시도 간격(초)")
        ttk.Entry(form, textvariable=self.interval_var, width=10).grid(row=16, column=1, sticky="w")

        self._row_label(form, 17, "타임아웃(ms)")
        ttk.Entry(form, textvariable=self.timeout_var, width=10).grid(row=17, column=1, sticky="w")

        ttk.Checkbutton(form, text="브라우저 창 띄우기(Headed)", variable=self.headed_var).grid(
            row=17, column=2, sticky="w"
        )

        for i in range(1, 5):
            form.columnconfigure(i, weight=1)

        controls = ttk.Frame(container, padding=(0, 10, 0, 10))
        controls.pack(fill="x")

        ttk.Button(controls, text="시작", command=self.start_monitor).pack(side="left")
        ttk.Button(controls, text="중지", command=self.stop_monitor).pack(side="left", padx=(8, 0))
        ttk.Label(controls, textvariable=self.status_var).pack(side="left", padx=(16, 0))

        log_box = ttk.LabelFrame(container, text="실행 로그", padding=10)
        log_box.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_box, height=22, wrap="word")
        self.log_text.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(log_box, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(fill="y", side="right")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.configure(state="disabled")

        self._toggle_url_mode()

    def _row_label(self, parent: ttk.Frame, row: int, text: str) -> None:
        ttk.Label(parent, text=text, width=14).grid(row=row, column=0, sticky="w", pady=4)

    def _toggle_url_mode(self) -> None:
        site_name = self.site_var.get()
        is_custom = site_name == "직접 URL 입력"
        self.full_url_entry.configure(state="normal" if is_custom else "disabled")
        self.path_entry.configure(state="disabled" if is_custom else "normal")

    def _build_url(self) -> str:
        site_name = self.site_var.get().strip()
        base_url = SITE_PRESETS.get(site_name, "")

        if site_name == "직접 URL 입력":
            url = self.full_url_var.get().strip()
        else:
            suffix = self.path_var.get().strip()
            if suffix.startswith("http://") or suffix.startswith("https://"):
                url = suffix
            elif suffix:
                site_suffix = normalize_path_for_site(site_name, suffix)
                url = f"{base_url.rstrip('/')}/{site_suffix.lstrip('/')}"
            else:
                url = base_url

        if not url.startswith("http://") and not url.startswith("https://"):
            raise ValueError("URL은 http:// 또는 https:// 로 시작해야 합니다.")
        return url

    def _validate(self) -> list[str]:
        cmd: list[str] = [
            sys.executable,
            "-u",
            str(self.base_dir / "ticket_watch.py"),
            "--url",
            self._build_url(),
            "--people",
            self._parse_people(),
            "--selector",
            self._parse_selector(),
            "--interval",
            self._parse_interval(),
            "--timeout-ms",
            self._parse_timeout(),
        ]

        date_text = self.date_text_var.get().strip()
        date_selector = self.date_selector_var.get().strip()
        if date_selector and not date_text:
            raise ValueError("일자 선택자를 입력했다면 일자 텍스트도 입력해야 합니다.")
        if date_text:
            cmd.extend(["--date-text", date_text])
            if date_selector:
                cmd.extend(["--date-selector", date_selector])

        modal_close_selectors = self.modal_close_selectors_var.get().strip()
        if self.site_var.get().strip() == "인터파크" and not modal_close_selectors:
            modal_close_selectors = ".popupCloseBtn"
        if modal_close_selectors:
            cmd.extend(["--modal-close-selectors", modal_close_selectors])

        round_text = self.round_text_var.get().strip()
        round_selector = self.round_selector_var.get().strip()
        if round_selector and not round_text:
            raise ValueError("회차 선택자를 입력했다면 회차 텍스트도 입력해야 합니다.")
        if round_text:
            cmd.extend(["--round-text", round_text])
            if round_selector:
                cmd.extend(["--round-selector", round_selector])

        reserve_text = self.reserve_text_var.get().strip()
        reserve_selector = self.reserve_selector_var.get().strip()
        if self.site_var.get().strip() == "인터파크" and not reserve_text and not reserve_selector:
            reserve_selector = ".sideBtn"
        if reserve_text:
            cmd.extend(["--reserve-text", reserve_text])
        if reserve_selector:
            cmd.extend(["--reserve-selector", reserve_selector])

        time_url = self.time_url_var.get().strip()
        if time_url:
            if not (time_url.startswith("http://") or time_url.startswith("https://")):
                raise ValueError("시간 확인 URL은 http:// 또는 https:// 로 시작해야 합니다.")
            cmd.extend(["--time-url", time_url])

        open_at = self.time_var.get().strip()
        if self.start_mode_var.get() == "예약 시작":
            if not open_at:
                raise ValueError("예약 시작 모드에서는 시작 시간을 입력해야 합니다.")
            try:
                dt.datetime.strptime(open_at, "%Y-%m-%d %H:%M:%S")
            except ValueError as exc:
                raise ValueError(f"시작 시간 형식 오류: {exc}") from exc
            cmd.extend(["--open-at", open_at])

        if self.headed_var.get():
            cmd.append("--headed")

        return cmd

    def _parse_people(self) -> str:
        raw = self.people_var.get().strip()
        people = int(raw)
        if people < 1:
            raise ValueError("인원수는 1 이상이어야 합니다.")
        return str(people)

    def _parse_selector(self) -> str:
        selector = self.selector_var.get().strip()
        if not selector:
            raise ValueError("CSS 선택자를 입력해주세요.")
        return selector

    def _parse_interval(self) -> str:
        raw = self.interval_var.get().strip()
        interval = float(raw)
        if interval <= 0:
            raise ValueError("재시도 간격은 0보다 커야 합니다.")
        return str(interval)

    def _parse_timeout(self) -> str:
        raw = self.timeout_var.get().strip()
        timeout = int(raw)
        if timeout < 100:
            raise ValueError("타임아웃은 100ms 이상이어야 합니다.")
        return str(timeout)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def check_time_url(self) -> None:
        time_url = self.time_url_var.get().strip()
        if not time_url:
            messagebox.showerror("입력 오류", "시간 확인 URL을 입력해주세요.")
            return
        if not (time_url.startswith("http://") or time_url.startswith("https://")):
            messagebox.showerror("입력 오류", "시간 확인 URL은 http:// 또는 https:// 로 시작해야 합니다.")
            return

        try:
            server_utc, date_header = self._fetch_server_time_utc(time_url)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("시간 확인 실패", str(exc))
            return

        local_utc = dt.datetime.now(dt.timezone.utc)
        offset = (server_utc - local_utc).total_seconds()
        local_now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        server_local = server_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S")

        self._append_log(
            f"[TIME] local={local_now} server={server_local} "
            f"offset(server-local)={offset:+.3f}s header={date_header}\n"
        )
        messagebox.showinfo(
            "시간 확인",
            f"서버 시간: {server_local}\n로컬 시간: {local_now}\n오프셋: {offset:+.3f}s",
        )

    def _fetch_server_time_utc(self, url: str) -> tuple[dt.datetime, str]:
        req = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                date_header = response.headers.get("Date")
        except Exception:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                date_header = response.headers.get("Date")

        if not date_header:
            raise ValueError("응답 헤더에서 Date 값을 찾지 못했습니다.")

        parsed = email.utils.parsedate_to_datetime(date_header)
        if parsed is None:
            raise ValueError(f"Date 헤더 파싱 실패: {date_header}")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc), date_header

    def _save_settings(self) -> None:
        data = {
            "site": self.site_var.get(),
            "full_url": self.full_url_var.get(),
            "path": self.path_var.get(),
            "time_url": self.time_url_var.get(),
            "people": self.people_var.get(),
            "start_mode": self.start_mode_var.get(),
            "time": self.time_var.get(),
            "date_text": self.date_text_var.get(),
            "date_selector": self.date_selector_var.get(),
            "modal_close_selectors": self.modal_close_selectors_var.get(),
            "round_text": self.round_text_var.get(),
            "round_selector": self.round_selector_var.get(),
            "reserve_text": self.reserve_text_var.get(),
            "reserve_selector": self.reserve_selector_var.get(),
            "selector": self.selector_var.get(),
            "interval": self.interval_var.get(),
            "timeout": self.timeout_var.get(),
            "headed": self.headed_var.get(),
        }
        try:
            self.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_settings(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        self.site_var.set(data.get("site", self.site_var.get()))
        self.full_url_var.set(data.get("full_url", ""))
        self.path_var.set(data.get("path", ""))
        self.time_url_var.set(data.get("time_url", ""))
        self.people_var.set(data.get("people", "2"))
        self.start_mode_var.set(data.get("start_mode", "바로 시작"))
        self.time_var.set(data.get("time", ""))
        self.date_text_var.set(data.get("date_text", ""))
        self.date_selector_var.set(data.get("date_selector", ""))
        self.modal_close_selectors_var.set(data.get("modal_close_selectors", ""))
        self.round_text_var.set(data.get("round_text", ""))
        self.round_selector_var.set(data.get("round_selector", ""))
        self.reserve_text_var.set(data.get("reserve_text", ""))
        self.reserve_selector_var.set(data.get("reserve_selector", ""))
        self.selector_var.set(data.get("selector", "#remainSeatCount"))
        self.interval_var.set(data.get("interval", "1.5"))
        self.timeout_var.set(data.get("timeout", "5000"))
        self.headed_var.set(bool(data.get("headed", True)))
        self._toggle_url_mode()

    def start_monitor(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("실행 중", "이미 실행 중입니다. 먼저 중지하세요.")
            return

        try:
            cmd = self._validate()
        except ValueError as exc:
            messagebox.showerror("입력 오류", str(exc))
            return

        self._save_settings()
        self._append_log("\n" + "=" * 72 + "\n")
        self._append_log("[INFO] 모니터링 시작\n")
        self._append_log(f"[INFO] command: {' '.join(cmd)}\n")

        self.process = subprocess.Popen(
            cmd,
            cwd=self.base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        reader = threading.Thread(target=self._read_process_output, daemon=True)
        reader.start()

        self.status_var.set("실행 중")

    def stop_monitor(self) -> None:
        if not self.process or self.process.poll() is not None:
            self.status_var.set("대기")
            return

        self.process.terminate()
        self.status_var.set("중지 요청")
        self._append_log("[INFO] 중지 요청 전송\n")

    def _read_process_output(self) -> None:
        if not self.process or not self.process.stdout:
            return

        for line in self.process.stdout:
            self.log_queue.put(line)

        return_code = self.process.wait()
        self.log_queue.put(f"[INFO] 프로세스 종료(code={return_code})\n")
        self.log_queue.put("__PROCESS_FINISHED__")

    def _poll_logs(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__PROCESS_FINISHED__":
                    self.status_var.set("대기")
                    continue

                self._append_log(item)
                if "CONDITION MET" in item:
                    self.root.bell()
                    messagebox.showinfo(
                        "조건 충족",
                        "설정한 인원수 조건을 만족했습니다.\n최종 예매/결제는 직접 진행하세요.",
                    )
        except queue.Empty:
            pass

        self.root.after(120, self._poll_logs)

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("종료", "실행 중입니다. 종료할까요?"):
                return
            self.process.terminate()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    TicketGuiApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
