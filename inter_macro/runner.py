from __future__ import annotations

import logging
import threading
import time

import pyautogui
from pynput import keyboard

from inter_macro.config import Profile
from inter_macro.engine import detect_target

LOGGER = logging.getLogger(__name__)


class MacroRunner:
    def __init__(self, profile: Profile, dry_run: bool = False) -> None:
        self.profile = profile
        self.dry_run = dry_run

        self._run_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_trigger_at = 0.0
        self._last_run_at = 0.0

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.0

    def stop(self) -> None:
        self._stop_event.set()

    def run_once(self) -> bool:
        if self._stop_event.is_set():
            return False
        if not self._active_window_valid():
            return False

        start = time.monotonic()
        deadline = start + self.profile.timeout_seconds
        attempt = 0

        while attempt < self.profile.max_attempts and time.monotonic() < deadline:
            attempt += 1
            result = detect_target(profile=self.profile, save_debug=False)
            if result.found and result.click_x is not None and result.click_y is not None:
                LOGGER.info(
                    "Target detected at (%d, %d), pixels=%d (attempt=%d)",
                    result.click_x,
                    result.click_y,
                    result.pixel_count,
                    attempt,
                )
                self._perform_click(result.click_x, result.click_y)
                self._last_run_at = time.monotonic()
                return True
            time.sleep(self.profile.scan_interval_seconds)

        miss_result = detect_target(profile=self.profile, save_debug=True)
        LOGGER.warning(
            "Target not found within timeout. pixels=%d, debug=%s",
            miss_result.pixel_count,
            miss_result.screenshot_path,
        )
        self._last_run_at = time.monotonic()
        return False

    def trigger(self) -> None:
        now = time.monotonic()
        if now - self._last_trigger_at < self.profile.debounce_seconds:
            return
        if now - self._last_run_at < self.profile.cooldown_seconds:
            return
        self._last_trigger_at = now

        if not self._run_lock.acquire(blocking=False):
            LOGGER.info("Ignored trigger: previous execution still running.")
            return
        try:
            self.run_once()
        finally:
            self._run_lock.release()

    def listen(self) -> None:
        LOGGER.info("Listening hotkey %s (press ESC to stop).", self.profile.hotkey)

        def _on_stop() -> None:
            LOGGER.info("Stop key pressed. Exiting listener.")
            self.stop()
            listener.stop()

        bindings = {
            self.profile.hotkey: self.trigger,
            "<esc>": _on_stop,
        }
        with keyboard.GlobalHotKeys(bindings) as listener:
            listener.join()

    def _perform_click(self, detected_x: int, detected_y: int) -> None:
        if self.dry_run:
            LOGGER.info(
                "Dry-run enabled. Skipping click (mode=%s, detected=(%d, %d), confirm=%s).",
                self.profile.click_mode,
                detected_x,
                detected_y,
                self.profile.confirm_button,
            )
            return

        if self.profile.click_mode == "detected_point":
            click_x, click_y = detected_x, detected_y
        else:
            click_x, click_y = self.profile.confirm_button

        if self.profile.click_delay_seconds > 0:
            time.sleep(self.profile.click_delay_seconds)
        pyautogui.click(click_x, click_y)
        LOGGER.info("Clicked at (%d, %d)", click_x, click_y)

    def _active_window_valid(self) -> bool:
        required = self.profile.required_window_title
        if not required:
            return True
        try:
            window = pyautogui.getActiveWindow()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Active window check failed: %s", exc)
            return True
        if window is None:
            LOGGER.warning("No active window found; skipping this trigger.")
            return False
        title = (window.title or "").strip()
        if required.lower() not in title.lower():
            LOGGER.info("Ignored trigger: active window '%s' does not match '%s'.", title, required)
            return False
        return True

