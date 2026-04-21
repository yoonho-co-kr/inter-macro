from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging
from typing import Optional

import numpy as np
import pyautogui

from inter_macro.config import Profile

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DetectionResult:
    found: bool
    pixel_count: int
    click_x: Optional[int] = None
    click_y: Optional[int] = None
    screenshot_path: Optional[str] = None


def _build_mask(image_rgb: np.ndarray, profile: Profile) -> np.ndarray:
    mask = np.zeros(image_rgb.shape[:2], dtype=bool)
    image_i16 = image_rgb.astype(np.int16)
    for target in profile.target_colors:
        target_vec = np.asarray(target.rgb, dtype=np.int16).reshape(1, 1, 3)
        within = np.abs(image_i16 - target_vec) <= target.tolerance
        mask |= np.all(within, axis=2)
    return mask


def detect_target(profile: Profile, save_debug: bool = False) -> DetectionResult:
    left, top, width, height = profile.capture_region
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    image_rgb = np.asarray(screenshot.convert("RGB"))
    mask = _build_mask(image_rgb, profile)

    pixel_count = int(mask.sum())
    if pixel_count < profile.min_pixels:
        screenshot_path = _save_debug_image(screenshot, profile) if save_debug else None
        return DetectionResult(found=False, pixel_count=pixel_count, screenshot_path=screenshot_path)

    ys, xs = np.where(mask)
    click_x = int(np.mean(xs)) + left
    click_y = int(np.mean(ys)) + top
    return DetectionResult(found=True, pixel_count=pixel_count, click_x=click_x, click_y=click_y)


def _save_debug_image(image, profile: Profile) -> str:
    out_dir = Path(profile.debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out_path = out_dir / f"{profile.name}-miss-{stamp}.png"
    image.save(out_path)
    LOGGER.info("Saved debug image to %s", out_path)
    return str(out_path.resolve())
