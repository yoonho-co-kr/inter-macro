from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional, Union


@dataclass(frozen=True)
class ColorTarget:
    rgb: tuple[int, int, int]
    tolerance: int = 12


@dataclass(frozen=True)
class Profile:
    name: str
    capture_region: tuple[int, int, int, int]
    confirm_button: tuple[int, int]
    target_colors: tuple[ColorTarget, ...]
    min_pixels: int = 8
    scan_interval_seconds: float = 0.03
    timeout_seconds: float = 1.2
    max_attempts: int = 45
    click_delay_seconds: float = 0.0
    cooldown_seconds: float = 0.8
    debounce_seconds: float = 0.2
    required_window_title: Optional[str] = None
    hotkey: str = "<alt>+q"
    click_mode: str = "confirm_button"
    debug_dir: str = "debug"


def _to_int_tuple(values: object, length: int, key: str) -> tuple:
    if not isinstance(values, list) or len(values) != length:
        raise ValueError(f"'{key}' must be a list of {length} integers.")
    if not all(isinstance(v, int) for v in values):
        raise ValueError(f"'{key}' must contain only integers.")
    return tuple(values)


def _to_color_target(item: object) -> ColorTarget:
    if not isinstance(item, dict):
        raise ValueError("'target_colors' entries must be objects.")
    rgb = _to_int_tuple(item.get("rgb"), 3, "target_colors[].rgb")
    tolerance = item.get("tolerance", 12)
    if not isinstance(tolerance, int) or tolerance < 0 or tolerance > 255:
        raise ValueError("'target_colors[].tolerance' must be an integer in [0, 255].")
    return ColorTarget(rgb=rgb, tolerance=tolerance)


def load_profile(path: Union[str, Path]) -> Profile:
    profile_path = Path(path).expanduser().resolve()
    raw = json.loads(profile_path.read_text(encoding="utf-8"))

    capture_region = _to_int_tuple(raw.get("capture_region"), 4, "capture_region")
    confirm_button = _to_int_tuple(raw.get("confirm_button"), 2, "confirm_button")

    target_colors_raw = raw.get("target_colors", [])
    if not isinstance(target_colors_raw, list) or not target_colors_raw:
        raise ValueError("'target_colors' must be a non-empty list.")
    target_colors = tuple(_to_color_target(item) for item in target_colors_raw)

    required_window_title = raw.get("required_window_title")
    if required_window_title is not None and not isinstance(required_window_title, str):
        raise ValueError("'required_window_title' must be a string or null.")

    hotkey = raw.get("hotkey", "<alt>+q")
    if not isinstance(hotkey, str) or not hotkey:
        raise ValueError("'hotkey' must be a non-empty string.")

    click_mode = raw.get("click_mode", "confirm_button")
    if click_mode not in {"confirm_button", "detected_point"}:
        raise ValueError("'click_mode' must be one of: confirm_button, detected_point.")

    return Profile(
        name=str(raw.get("name", profile_path.stem)),
        capture_region=tuple(capture_region),
        confirm_button=tuple(confirm_button),
        target_colors=target_colors,
        min_pixels=int(raw.get("min_pixels", 8)),
        scan_interval_seconds=float(raw.get("scan_interval_seconds", 0.03)),
        timeout_seconds=float(raw.get("timeout_seconds", 1.2)),
        max_attempts=int(raw.get("max_attempts", 45)),
        click_delay_seconds=float(raw.get("click_delay_seconds", 0.0)),
        cooldown_seconds=float(raw.get("cooldown_seconds", 0.8)),
        debounce_seconds=float(raw.get("debounce_seconds", 0.2)),
        required_window_title=required_window_title,
        hotkey=hotkey,
        click_mode=click_mode,
        debug_dir=str(raw.get("debug_dir", "debug")),
    )
