#!/usr/bin/env python3
"""Local web UI launcher for safe ticket monitor (tkinter-free)."""

from __future__ import annotations

import datetime as dt
import email.utils
import json
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from site_presets import WEB_SITE_PRESETS

HOST = "127.0.0.1"
PORT = 8765

SITE_PRESETS = WEB_SITE_PRESETS


def normalize_path_for_site(site: str, suffix: str) -> str:
    normalized = suffix.strip()
    if not normalized:
        return normalized

    if site == "interpark":
        normalized = normalized.lstrip("/")
        if not normalized.startswith("goods/"):
            normalized = f"goods/{normalized}"
    return normalized


class AppState:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.settings_path = base_dir / "monitor_settings.json"
        self.lock = threading.Lock()
        self.process: Optional[subprocess.Popen[str]] = None
        self.logs: list[str] = []
        self.status = "idle"

    def append_log(self, line: str) -> None:
        with self.lock:
            self.logs.append(line)
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]

    def get_snapshot(self) -> dict:
        with self.lock:
            running = self.process is not None and self.process.poll() is None
            return {
                "running": running,
                "status": self.status,
                "logs": self.logs[-300:],
            }

    def save_settings(self, data: dict) -> None:
        try:
            self.settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def load_settings(self) -> dict:
        if not self.settings_path.exists():
            return {}
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}


HTML_PAGE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Inter Macro - Safe Monitor</title>
  <style>
    :root { --bg:#f4f5f8; --fg:#14171f; --muted:#666; --line:#d6dae3; --card:#fff; --accent:#1769ff; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--fg); }
    .wrap { max-width: 980px; margin: 24px auto; padding: 0 16px; }
    .card { background: var(--card); border:1px solid var(--line); border-radius: 12px; padding: 16px; margin-bottom: 14px; }
    h1 { font-size: 20px; margin: 0 0 12px; }
    .grid { display:grid; grid-template-columns: 170px 1fr; gap:10px; align-items:center; }
    input, select, button { padding: 8px 10px; border:1px solid var(--line); border-radius:8px; font-size:14px; }
    button { background:#fff; cursor:pointer; }
    .primary { background:var(--accent); color:#fff; border-color:var(--accent); }
    .row { display:flex; gap:8px; }
    .hint { color:var(--muted); font-size: 12px; }
    #logs { width:100%; min-height:300px; border:1px solid var(--line); border-radius:10px; padding:10px; background:#0f1116; color:#dcf3db; font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; overflow:auto; white-space:pre-wrap; }
    .status { font-weight:600; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Inter Macro - Safe Ticket Watch</h1>
      <div class="grid">
        <label>사이트</label>
        <select id="site" onchange="toggleMode()">
          <option value="custom">직접 URL 입력</option>
          <option value="interpark">인터파크</option>
          <option value="yes24">예스24</option>
          <option value="melon">멜론티켓</option>
          <option value="ticketlink">티켓링크</option>
        </select>

        <label>전체 URL</label>
        <input id="full_url" placeholder="https://...">

        <label>뒤 경로(Path)</label>
        <input id="path" placeholder="/goods/12345">

        <label>시간 확인 URL</label>
        <div class="row">
          <input id="time_url" placeholder="https://...">
          <button type="button" onclick="checkTime()">시간 확인</button>
        </div>

        <label>인원수</label>
        <input id="people" value="2">

        <label>자동 실행</label>
        <select id="start_mode">
          <option value="now">바로 시작</option>
          <option value="scheduled">예약 시작</option>
        </select>

        <label>시작 시간</label>
        <input id="start_time" placeholder="YYYY-MM-DD HH:MM:SS">

        <label>일자 텍스트</label>
        <input id="date_text" placeholder="예: 2026.05.01 또는 5/1">

        <label>일자 선택자(선택)</label>
        <input id="date_selector" placeholder="예: button[data-date], .dateItem">

        <label>모달 닫기 선택자(선택)</label>
        <input id="modal_close_selectors" value=".popupCloseBtn" placeholder="예: .popup-close, .btn-close">

        <label>회차 텍스트(선택)</label>
        <input id="round_text" placeholder="예: 19:00, 2회">

        <label>회차 선택자(선택)</label>
        <input id="round_selector" placeholder="예: .timeItem button">

        <label>예매 버튼 텍스트(선택)</label>
        <input id="reserve_text" placeholder="예: 예매하기">

        <label>예매 버튼 선택자(선택)</label>
        <input id="reserve_selector" value=".sideBtn" placeholder="예: .btn-booking">

        <label>CSS 선택자</label>
        <input id="selector" value="#remainSeatCount">

        <label>재시도 간격(초)</label>
        <input id="interval" value="1.5">

        <label>타임아웃(ms)</label>
        <input id="timeout_ms" value="5000">

        <label>브라우저 창 띄우기</label>
        <select id="headed"><option value="true">예</option><option value="false">아니오</option></select>
      </div>
      <p class="hint">결제 자동화/우회 기능은 제공하지 않으며, 최종 예매/결제는 직접 진행해야 합니다.</p>
      <div class="row">
        <button class="primary" onclick="startMonitor()">시작</button>
        <button onclick="stopMonitor()">중지</button>
        <div class="status" id="status">상태: idle</div>
      </div>
    </div>

    <div class="card">
      <div id="logs"></div>
    </div>
  </div>

<script>
async function post(path, body){
  const res = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  return await res.json();
}

function currentPayload(){
  return {
    site: document.getElementById('site').value,
    full_url: document.getElementById('full_url').value.trim(),
    path: document.getElementById('path').value.trim(),
    time_url: document.getElementById('time_url').value.trim(),
    people: document.getElementById('people').value.trim(),
    start_mode: document.getElementById('start_mode').value,
    start_time: document.getElementById('start_time').value.trim(),
    date_text: document.getElementById('date_text').value.trim(),
    date_selector: document.getElementById('date_selector').value.trim(),
    modal_close_selectors: document.getElementById('modal_close_selectors').value.trim(),
    round_text: document.getElementById('round_text').value.trim(),
    round_selector: document.getElementById('round_selector').value.trim(),
    reserve_text: document.getElementById('reserve_text').value.trim(),
    reserve_selector: document.getElementById('reserve_selector').value.trim(),
    selector: document.getElementById('selector').value.trim(),
    interval: document.getElementById('interval').value.trim(),
    timeout_ms: document.getElementById('timeout_ms').value.trim(),
    headed: document.getElementById('headed').value === 'true'
  }
}

function toggleMode(){
  const site = document.getElementById('site').value;
  document.getElementById('full_url').disabled = site !== 'custom';
  document.getElementById('path').disabled = site === 'custom';
}

async function startMonitor(){
  const result = await post('/start', currentPayload());
  if(!result.ok){ alert(result.error || 'start failed'); }
}

async function stopMonitor(){
  const result = await post('/stop', {});
  if(!result.ok){ alert(result.error || 'stop failed'); }
}

async function checkTime(){
  const url = document.getElementById('time_url').value.trim();
  const result = await post('/timecheck', {url});
  if(!result.ok){ alert(result.error || 'time check failed'); return; }
  alert(`서버 시간: ${result.server_local}\n로컬 시간: ${result.local_now}\n오프셋: ${result.offset}`);
}

async function refresh(){
  const res = await fetch('/state');
  const s = await res.json();
  document.getElementById('status').innerText = `상태: ${s.status} (${s.running ? 'running' : 'stopped'})`;
  const logs = document.getElementById('logs');
  logs.textContent = s.logs.join('');
  logs.scrollTop = logs.scrollHeight;
}

function applySettings(settings){
  for(const [k,v] of Object.entries(settings)){
    const el = document.getElementById(k);
    if(!el) continue;
    if(el.tagName === 'SELECT' && el.id === 'headed'){
      el.value = v ? 'true' : 'false';
      continue;
    }
    if(typeof v === 'boolean'){
      el.value = v ? 'true' : 'false';
    } else {
      el.value = `${v ?? ''}`;
    }
  }
  toggleMode();
}

async function init(){
  const settingsRes = await fetch('/settings');
  const settings = await settingsRes.json();
  applySettings(settings);
  await refresh();
  setInterval(refresh, 1200);
}

init();
</script>
</body>
</html>
"""


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    return json.loads(raw.decode("utf-8"))


def fetch_server_time_utc(url: str, timeout_sec: float = 5.0) -> tuple[dt.datetime, str]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            date_header = response.headers.get("Date")
    except Exception:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            date_header = response.headers.get("Date")

    if not date_header:
        raise ValueError("Response has no Date header")

    parsed = email.utils.parsedate_to_datetime(date_header)
    if parsed is None:
        raise ValueError(f"Could not parse Date header: {date_header!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)

    return parsed.astimezone(dt.timezone.utc), date_header


def build_url(payload: dict) -> str:
    site = str(payload.get("site", "custom"))
    if site == "custom":
        url = str(payload.get("full_url", "")).strip()
    else:
        base = SITE_PRESETS.get(site, "")
        suffix = str(payload.get("path", "")).strip()
        if suffix.startswith("http://") or suffix.startswith("https://"):
            url = suffix
        elif suffix:
            site_suffix = normalize_path_for_site(site, suffix)
            url = f"{base.rstrip('/')}/{site_suffix.lstrip('/')}"
        else:
            url = base

    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")
    return url


def build_command(base_dir: Path, payload: dict) -> list[str]:
    site = str(payload.get("site", "custom"))
    url = build_url(payload)

    people = int(str(payload.get("people", "")).strip())
    if people < 1:
        raise ValueError("people must be >= 1")

    selector = str(payload.get("selector", "")).strip()
    if not selector:
        raise ValueError("selector is required")

    interval = float(str(payload.get("interval", "")).strip())
    if interval <= 0:
        raise ValueError("interval must be > 0")

    timeout_ms = int(str(payload.get("timeout_ms", "")).strip())
    if timeout_ms < 100:
        raise ValueError("timeout_ms must be >= 100")

    cmd = [
        sys.executable,
        "-u",
        str(base_dir / "ticket_watch.py"),
        "--url",
        url,
        "--people",
        str(people),
        "--selector",
        selector,
        "--interval",
        str(interval),
        "--timeout-ms",
        str(timeout_ms),
    ]

    date_text = str(payload.get("date_text", "")).strip()
    date_selector = str(payload.get("date_selector", "")).strip()
    modal_close_selectors = str(payload.get("modal_close_selectors", "")).strip()
    round_text = str(payload.get("round_text", "")).strip()
    round_selector = str(payload.get("round_selector", "")).strip()
    reserve_text = str(payload.get("reserve_text", "")).strip()
    reserve_selector = str(payload.get("reserve_selector", "")).strip()

    if site == "interpark":
        if not modal_close_selectors:
            modal_close_selectors = ".popupCloseBtn"
        if not reserve_text and not reserve_selector:
            reserve_selector = ".sideBtn"

    if date_selector and not date_text:
        raise ValueError("date_selector requires date_text")
    if round_selector and not round_text:
        raise ValueError("round_selector requires round_text")

    if modal_close_selectors:
        cmd.extend(["--modal-close-selectors", modal_close_selectors])
    if date_text:
        cmd.extend(["--date-text", date_text])
        if date_selector:
            cmd.extend(["--date-selector", date_selector])
    if round_text:
        cmd.extend(["--round-text", round_text])
        if round_selector:
            cmd.extend(["--round-selector", round_selector])
    if reserve_text:
        cmd.extend(["--reserve-text", reserve_text])
    if reserve_selector:
        cmd.extend(["--reserve-selector", reserve_selector])

    start_mode = str(payload.get("start_mode", "now"))
    start_time = str(payload.get("start_time", "")).strip()
    if start_mode == "scheduled":
        if not start_time:
            raise ValueError("start_time is required for scheduled mode")
        dt.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        cmd.extend(["--open-at", start_time])

    time_url = str(payload.get("time_url", "")).strip()
    if time_url:
        if not (time_url.startswith("http://") or time_url.startswith("https://")):
            raise ValueError("time_url must start with http:// or https://")
        cmd.extend(["--time-url", time_url])

    headed = bool(payload.get("headed", True))
    if headed:
        cmd.append("--headed")

    return cmd


def launch_reader(state: AppState, process: subprocess.Popen[str]) -> None:
    def _reader() -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            state.append_log(line)

        code = process.wait()
        with state.lock:
            state.status = f"stopped(code={code})"
            if state.process is process:
                state.process = None
        state.append_log(f"[INFO] process exited with code {code}\n")

    threading.Thread(target=_reader, daemon=True).start()


def make_handler(state: AppState):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, html: str, status: int = 200) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/":
                self._html(HTML_PAGE)
                return
            if self.path == "/state":
                self._json(state.get_snapshot())
                return
            if self.path == "/settings":
                self._json(state.load_settings())
                return
            self._json({"ok": False, "error": "not found"}, status=404)

        def do_POST(self) -> None:
            if self.path == "/start":
                payload = parse_json_body(self)
                try:
                    cmd = build_command(state.base_dir, payload)
                except Exception as exc:  # noqa: BLE001
                    self._json({"ok": False, "error": str(exc)}, status=400)
                    return

                with state.lock:
                    if state.process is not None and state.process.poll() is None:
                        self._json({"ok": False, "error": "already running"}, status=409)
                        return

                state.save_settings(payload)
                state.append_log("\n" + "=" * 70 + "\n")
                state.append_log("[INFO] starting monitor\n")
                state.append_log(f"[INFO] cmd: {' '.join(cmd)}\n")

                process = subprocess.Popen(
                    cmd,
                    cwd=state.base_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                with state.lock:
                    state.process = process
                    state.status = "running"
                launch_reader(state, process)

                self._json({"ok": True})
                return

            if self.path == "/stop":
                with state.lock:
                    process = state.process
                if process is None or process.poll() is not None:
                    with state.lock:
                        state.status = "idle"
                        state.process = None
                    self._json({"ok": True, "message": "not running"})
                    return

                process.terminate()
                with state.lock:
                    state.status = "stopping"
                state.append_log("[INFO] terminate signal sent\n")
                self._json({"ok": True})
                return

            if self.path == "/timecheck":
                payload = parse_json_body(self)
                url = str(payload.get("url", "")).strip()
                if not (url.startswith("http://") or url.startswith("https://")):
                    self._json({"ok": False, "error": "url must start with http:// or https://"}, status=400)
                    return
                try:
                    server_utc, _header = fetch_server_time_utc(url)
                except Exception as exc:  # noqa: BLE001
                    self._json({"ok": False, "error": str(exc)}, status=400)
                    return

                local_utc = dt.datetime.now(dt.timezone.utc)
                offset_sec = (server_utc - local_utc).total_seconds()
                self._json(
                    {
                        "ok": True,
                        "server_local": server_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                        "local_now": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "offset": f"{offset_sec:+.3f}s",
                    }
                )
                return

            self._json({"ok": False, "error": "not found"}, status=404)

    return Handler


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    state = AppState(base_dir)
    handler_cls = make_handler(state)
    server = ThreadingHTTPServer((HOST, PORT), handler_cls)

    url = f"http://{HOST}:{PORT}"
    print(f"Web UI started: {url}")
    print("Open the URL in your browser. Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web UI...")
    finally:
        with state.lock:
            process = state.process
        if process is not None and process.poll() is None:
            process.terminate()
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
