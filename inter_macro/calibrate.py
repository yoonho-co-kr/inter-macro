from __future__ import annotations

from pathlib import Path
import json
import time
from typing import Optional

import pyautogui


def _ask_int(prompt: str, default: Optional[int] = None) -> int:
    while True:
        raw = input(f"{prompt}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Enter an integer.")


def _capture_mouse_position(label: str) -> tuple[int, int]:
    print(f"\nMove mouse to '{label}' in 3 seconds...")
    for remaining in (3, 2, 1):
        print(f"  {remaining}...")
        time.sleep(1)
    pos = pyautogui.position()
    print(f"Captured: ({pos.x}, {pos.y})")
    return int(pos.x), int(pos.y)


def _capture_pixel_color() -> tuple[int, int, int]:
    x, y = _capture_mouse_position("target color pixel")
    pixel = pyautogui.screenshot().getpixel((x, y))
    rgb = tuple(int(v) for v in pixel[:3])
    print(f"Captured color at ({x}, {y}): {rgb}")
    return rgb


def run_calibration(output_path: str) -> Path:
    print("\n== Inter Macro Calibration ==")

    print("\n[1/4] Capture region")
    print("Input explicit region, or press Enter to capture top-left and bottom-right by mouse.")
    use_manual = input("Use manual numbers? [y/N]: ").strip().lower() == "y"
    if use_manual:
        left = _ask_int("left")
        top = _ask_int("top")
        width = _ask_int("width")
        height = _ask_int("height")
    else:
        left, top = _capture_mouse_position("capture region TOP-LEFT")
        right, bottom = _capture_mouse_position("capture region BOTTOM-RIGHT")
        width = max(1, right - left)
        height = max(1, bottom - top)

    print("\n[2/4] Confirm button coordinate")
    confirm_x, confirm_y = _capture_mouse_position("confirm button")

    print("\n[3/4] Target colors")
    color_count = _ask_int("number of target colors", 1)
    targets: list[dict[str, object]] = []
    for idx in range(color_count):
        print(f"\nTarget color #{idx + 1}")
        sample = input("Capture from screen? [Y/n]: ").strip().lower() != "n"
        if sample:
            rgb = _capture_pixel_color()
        else:
            r = _ask_int("r")
            g = _ask_int("g")
            b = _ask_int("b")
            rgb = (r, g, b)
        tolerance = _ask_int("tolerance (0-255)", 12)
        targets.append({"rgb": list(rgb), "tolerance": tolerance})

    print("\n[4/4] Runtime options")
    profile_name = input("profile name [default]: ").strip() or "default"
    hotkey = input("hotkey [<alt>+q]: ").strip() or "<alt>+q"
    click_mode = input("click_mode (confirm_button/detected_point) [confirm_button]: ").strip() or "confirm_button"
    min_pixels = _ask_int("min_pixels", 8)
    timeout_seconds = float(input("timeout_seconds [1.2]: ").strip() or "1.2")
    scan_interval_seconds = float(input("scan_interval_seconds [0.03]: ").strip() or "0.03")
    max_attempts = _ask_int("max_attempts", 45)
    debounce_seconds = float(input("debounce_seconds [0.2]: ").strip() or "0.2")
    cooldown_seconds = float(input("cooldown_seconds [0.8]: ").strip() or "0.8")
    required_window_title = input("required_window_title (optional): ").strip() or None

    profile = {
        "name": profile_name,
        "capture_region": [left, top, width, height],
        "confirm_button": [confirm_x, confirm_y],
        "target_colors": targets,
        "min_pixels": min_pixels,
        "scan_interval_seconds": scan_interval_seconds,
        "timeout_seconds": timeout_seconds,
        "max_attempts": max_attempts,
        "click_delay_seconds": 0.0,
        "cooldown_seconds": cooldown_seconds,
        "debounce_seconds": debounce_seconds,
        "required_window_title": required_window_title,
        "hotkey": hotkey,
        "click_mode": click_mode,
        "debug_dir": "debug",
    }

    out_path = Path(output_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    print(f"\nSaved profile: {out_path}")
    return out_path
