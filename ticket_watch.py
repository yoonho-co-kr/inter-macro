#!/usr/bin/env python3
"""Ticket page monitor (safe mode).

This tool monitors a ticket page and alerts the user when a configurable
availability condition is met. It does not complete payment or bypass anti-bot
mechanisms.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional


DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

AUTO_MODAL_SELECTORS = [
    ".popup-close",
    ".btn-close",
    ".modal .close",
    ".popup .close",
    ".layer-pop .close",
    ".layerPop .close",
    "button[aria-label*='닫기']",
    "button[aria-label*='close' i]",
]

AUTO_MODAL_TEXTS = [
    "닫기",
    "close",
    "오늘 하루 보지 않기",
    "오늘하루보지않기",
]

AUTO_RESERVE_TEXTS = [
    "예매하기",
    "예매",
    "booking",
    "book now",
    "book",
]


@dataclass
class MonitorConfig:
    url: str
    people: int
    selector: str
    modal_close_selectors: list[str]
    date_text: Optional[str]
    date_selector: Optional[str]
    round_text: Optional[str]
    round_selector: Optional[str]
    reserve_text: Optional[str]
    reserve_selector: Optional[str]
    interval: float
    timeout_ms: int
    headless: bool
    open_at: Optional[dt.datetime]
    time_url: Optional[str]


def parse_args() -> MonitorConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Ticket page watcher: checks an element text repeatedly and alerts "
            "when parsed availability >= target people count."
        )
    )
    parser.add_argument("--url", required=True, help="Target ticket page URL")
    parser.add_argument(
        "--people",
        required=True,
        type=int,
        help="Required people count (condition: available >= people)",
    )
    parser.add_argument(
        "--selector",
        required=True,
        help="CSS selector that contains availability text (e.g. '#seatCount')",
    )
    parser.add_argument(
        "--modal-close-selectors",
        help=(
            "Optional comma-separated CSS selectors to click/close popups before "
            "date/round selection"
        ),
    )
    parser.add_argument(
        "--date-text",
        help=(
            "Optional text to select a specific date before reading availability "
            "(e.g. '2026.05.01' or '5/1')"
        ),
    )
    parser.add_argument(
        "--date-selector",
        help=(
            "Optional CSS selector for date items. If set, this selector is "
            "filtered by --date-text before click."
        ),
    )
    parser.add_argument("--round-text", help="Optional text to select a specific round/session")
    parser.add_argument(
        "--round-selector",
        help="Optional CSS selector for round/session item",
    )
    parser.add_argument(
        "--reserve-text",
        help="Optional text to click reservation button when condition is met",
    )
    parser.add_argument(
        "--reserve-selector",
        help="Optional CSS selector for reservation button",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.5,
        help="Polling interval in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=5000,
        help="Per-request timeout in milliseconds (default: 5000)",
    )
    parser.add_argument(
        "--open-at",
        help=(
            "Start monitoring at local time. Format: YYYY-MM-DD HH:MM:SS "
            "(example: 2026-04-21 20:00:00)"
        ),
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (default: headless)",
    )
    parser.add_argument(
        "--time-url",
        help=(
            "Optional URL used to read HTTP Date header and align start time "
            "to server clock"
        ),
    )

    args = parser.parse_args()

    if args.people < 1:
        parser.error("--people must be >= 1")
    if args.interval <= 0:
        parser.error("--interval must be > 0")
    if args.date_selector and not args.date_text:
        parser.error("--date-selector requires --date-text")
    if args.round_selector and not args.round_text:
        parser.error("--round-selector requires --round-text")

    open_at = None
    if args.open_at:
        try:
            open_at = dt.datetime.strptime(args.open_at, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            parser.error(f"invalid --open-at value: {exc}")

    return MonitorConfig(
        url=args.url,
        people=args.people,
        selector=args.selector,
        modal_close_selectors=parse_csv_list(args.modal_close_selectors),
        date_text=args.date_text.strip() if args.date_text else None,
        date_selector=args.date_selector.strip() if args.date_selector else None,
        round_text=args.round_text.strip() if args.round_text else None,
        round_selector=args.round_selector.strip() if args.round_selector else None,
        reserve_text=args.reserve_text.strip() if args.reserve_text else None,
        reserve_selector=args.reserve_selector.strip() if args.reserve_selector else None,
        interval=args.interval,
        timeout_ms=args.timeout_ms,
        headless=not args.headed,
        open_at=open_at,
        time_url=args.time_url,
    )


def parse_csv_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def apply_interpark_defaults(config: MonitorConfig) -> None:
    if "tickets.interpark.com" not in config.url:
        return
    if not config.modal_close_selectors:
        config.modal_close_selectors = [".popupCloseBtn"]
    if not config.reserve_text and not config.reserve_selector:
        config.reserve_selector = ".sideBtn"


def fetch_server_clock_offset_seconds(url: str, timeout_ms: int) -> float:
    """Return (server_utc_now - local_utc_now) in seconds from HTTP Date header."""
    timeout_sec = max(timeout_ms / 1000.0, 0.1)
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": DEFAULT_UA})

    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            date_header = response.headers.get("Date")
    except Exception:
        # Some servers reject HEAD. Fallback to GET.
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": DEFAULT_UA})
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            date_header = response.headers.get("Date")

    if not date_header:
        raise ValueError("Date header is missing from response")

    parsed = email.utils.parsedate_to_datetime(date_header)
    if parsed is None:
        raise ValueError(f"Failed to parse Date header: {date_header!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)

    server_utc_now = parsed.astimezone(dt.timezone.utc)
    local_utc_now = dt.datetime.now(dt.timezone.utc)
    return (server_utc_now - local_utc_now).total_seconds()


def wait_until(start_at: dt.datetime, clock_offset_sec: float = 0.0) -> None:
    while True:
        now = dt.datetime.now()
        adjusted_now = now + dt.timedelta(seconds=clock_offset_sec)
        delta = (start_at - adjusted_now).total_seconds()
        if delta <= 0:
            print(f"[{now:%H:%M:%S}] Monitoring started.")
            return

        # Log once per second near launch to avoid noisy output.
        sleep_for = 1.0 if delta < 10 else min(5.0, delta)
        print(f"[{now:%H:%M:%S}] Waiting {delta:.1f}s until start time...")
        time.sleep(sleep_for)


def parse_available_count(text: str) -> int:
    """Extract the largest integer from text, e.g. '잔여 12석' -> 12."""
    numbers = [int(match) for match in re.findall(r"\d+", text)]
    if not numbers:
        raise ValueError(f"No number found in selector text: {text!r}")
    return max(numbers)


def alert(now: dt.datetime, available: int, people: int) -> None:
    print("\n" + "=" * 60)
    print(f"[{now:%Y-%m-%d %H:%M:%S}] CONDITION MET")
    print(f"Available: {available}, Required: {people}")
    print("Manual checkout only: complete reservation/payment yourself.")
    print("=" * 60 + "\n")
    # Terminal bell. Some terminals may ignore this.
    print("\a", end="")


def select_target_date(
    *,
    page,
    date_text: str,
    date_selector: Optional[str],
    timeout_ms: int,
) -> str:
    if date_selector:
        locator = page.locator(date_selector).filter(has_text=date_text).first
        locator.click(timeout=timeout_ms)
        page.wait_for_timeout(120)
        return f"selector={date_selector!r} text~={date_text!r}"

    locator = page.get_by_text(date_text, exact=False).first
    locator.click(timeout=timeout_ms)
    page.wait_for_timeout(120)
    return f"text~={date_text!r}"


def select_target_round(
    *,
    page,
    round_text: str,
    round_selector: Optional[str],
    timeout_ms: int,
) -> str:
    if round_selector:
        locator = page.locator(round_selector).filter(has_text=round_text).first
        locator.click(timeout=timeout_ms)
        page.wait_for_timeout(120)
        return f"selector={round_selector!r} text~={round_text!r}"

    locator = page.get_by_text(round_text, exact=False).first
    locator.click(timeout=timeout_ms)
    page.wait_for_timeout(120)
    return f"text~={round_text!r}"


def click_modal_closers(*, page, selectors: list[str], timeout_ms: int) -> str:
    clicked: list[str] = []
    for sel in selectors:
        frame_url = click_selector_across_frames(page=page, selector=sel, timeout_ms=timeout_ms)
        if frame_url:
            clicked.append(f"{sel}@{frame_url}")
            page.wait_for_timeout(80)
    if not clicked:
        return "none"
    return ",".join(clicked)


def auto_close_modal_closers(*, page, timeout_ms: int) -> str:
    clicked: list[str] = []

    for sel in AUTO_MODAL_SELECTORS:
        frame_url = click_selector_across_frames(page=page, selector=sel, timeout_ms=timeout_ms)
        if frame_url:
            clicked.append(f"{sel}@{frame_url}")
            page.wait_for_timeout(80)

    for text in AUTO_MODAL_TEXTS:
        frame_url = click_text_across_frames(page=page, text=text, timeout_ms=timeout_ms)
        if frame_url:
            clicked.append(f"text:{text}@{frame_url}")
            page.wait_for_timeout(80)

    if not clicked:
        return "none"
    return ",".join(clicked)


def click_reserve_button(
    *,
    page,
    reserve_text: Optional[str],
    reserve_selector: Optional[str],
    timeout_ms: int,
) -> str:
    if reserve_selector:
        locator = page.locator(reserve_selector)
        if reserve_text:
            locator = locator.filter(has_text=reserve_text)
        locator = locator.first
        locator.click(timeout=timeout_ms)
        if reserve_text:
            return f"selector={reserve_selector!r} text~={reserve_text!r}"
        return f"selector={reserve_selector!r}"

    if not reserve_text:
        raise ValueError("reserve click requires reserve_text or reserve_selector")
    locator = page.get_by_text(reserve_text, exact=False).first
    locator.click(timeout=timeout_ms)
    return f"text~={reserve_text!r}"


def auto_click_reserve_button(*, page, timeout_ms: int) -> str:
    selector_candidates = [
        "button[type='button']",
        "button",
        "a[role='button']",
        "a",
        "[class*='booking']",
        "[class*='reserve']",
    ]
    for sel in selector_candidates:
        try:
            items = page.locator(sel)
            count = min(items.count(), 40)
            for idx in range(count):
                candidate = items.nth(idx)
                if not candidate.is_visible():
                    continue
                text = candidate.inner_text(timeout=200).strip().lower()
                if any(keyword in text for keyword in AUTO_RESERVE_TEXTS):
                    candidate.click(timeout=max(500, min(timeout_ms, 1500)))
                    return f"auto:{sel} text={text!r}"
        except Exception:
            continue
    return "none"


def click_selector_across_frames(*, page, selector: str, timeout_ms: int) -> Optional[str]:
    for frame in page.frames:
        try:
            targets = frame.locator(selector)
            count = min(targets.count(), 10)
            for idx in range(count):
                candidate = targets.nth(idx)
                if _try_click_candidate(candidate, timeout_ms):
                    return _short_frame_url(frame.url)
        except Exception:
            continue
    return None


def click_text_across_frames(*, page, text: str, timeout_ms: int) -> Optional[str]:
    for frame in page.frames:
        try:
            targets = frame.get_by_text(text, exact=False)
            count = min(targets.count(), 10)
            for idx in range(count):
                candidate = targets.nth(idx)
                if _try_click_candidate(candidate, timeout_ms):
                    return _short_frame_url(frame.url)
        except Exception:
            continue
    return None


def _try_click_candidate(candidate, timeout_ms: int) -> bool:
    click_timeout = max(300, min(timeout_ms, 1500))
    try:
        candidate.click(timeout=click_timeout, force=True)
        return True
    except Exception:
        pass
    try:
        candidate.evaluate(
            """
            el => {
              if (!el) return false;
              if (typeof el.click === "function") {
                el.click();
                return true;
              }
              return false;
            }
            """
        )
        return True
    except Exception:
        return False


def _short_frame_url(url: str) -> str:
    if not url:
        return "main"
    return url[:80]


def monitor(config: MonitorConfig) -> int:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Missing dependency: playwright")
        print("Run: pip install -r requirements.txt && playwright install chromium")
        return 2

    apply_interpark_defaults(config)

    clock_offset_sec = 0.0
    if config.time_url:
        try:
            clock_offset_sec = fetch_server_clock_offset_seconds(config.time_url, config.timeout_ms)
            print(
                f"Clock sync from {config.time_url}: offset={clock_offset_sec:+.3f}s "
                "(server - local)"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Clock sync warning: {exc}")

    if config.open_at:
        wait_until(config.open_at, clock_offset_sec=clock_offset_sec)

    print(
        f"Watching URL={config.url} selector={config.selector!r} "
        f"target_people={config.people} interval={config.interval}s"
    )
    if config.date_text:
        print(
            "Date selection enabled: "
            f"date_text={config.date_text!r} date_selector={config.date_selector!r}"
        )
    if config.round_text:
        print(
            "Round selection enabled: "
            f"round_text={config.round_text!r} round_selector={config.round_selector!r}"
        )
    if config.reserve_text or config.reserve_selector:
        print(
            "Reserve click enabled: "
            f"reserve_text={config.reserve_text!r} reserve_selector={config.reserve_selector!r}"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.headless)
        context = browser.new_context(user_agent=DEFAULT_UA)
        page = context.new_page()

        try:
            page.goto(config.url, wait_until="domcontentloaded", timeout=config.timeout_ms)

            while True:
                now = dt.datetime.now()
                try:
                    page.reload(wait_until="domcontentloaded", timeout=config.timeout_ms)
                    page.wait_for_timeout(180)
                    if config.modal_close_selectors:
                        closed = click_modal_closers(
                            page=page,
                            selectors=config.modal_close_selectors,
                            timeout_ms=config.timeout_ms,
                        )
                        print(f"[{now:%H:%M:%S}] modal_close={closed}")
                    else:
                        auto_closed = auto_close_modal_closers(page=page, timeout_ms=config.timeout_ms)
                        if auto_closed != "none":
                            print(f"[{now:%H:%M:%S}] modal_auto_close={auto_closed}")
                    if config.date_text:
                        selected = select_target_date(
                            page=page,
                            date_text=config.date_text,
                            date_selector=config.date_selector,
                            timeout_ms=config.timeout_ms,
                        )
                        print(f"[{now:%H:%M:%S}] date_selected={selected}")
                    if config.round_text:
                        selected_round = select_target_round(
                            page=page,
                            round_text=config.round_text,
                            round_selector=config.round_selector,
                            timeout_ms=config.timeout_ms,
                        )
                        print(f"[{now:%H:%M:%S}] round_selected={selected_round}")
                    locator = page.locator(config.selector)
                    raw_text = locator.first.inner_text(timeout=config.timeout_ms).strip()
                    available = parse_available_count(raw_text)

                    print(
                        f"[{now:%H:%M:%S}] selector_text={raw_text!r} "
                        f"parsed_available={available}"
                    )

                    if available >= config.people:
                        if config.reserve_text or config.reserve_selector:
                            reserve_action = click_reserve_button(
                                page=page,
                                reserve_text=config.reserve_text,
                                reserve_selector=config.reserve_selector,
                                timeout_ms=config.timeout_ms,
                            )
                            print(f"[{now:%H:%M:%S}] reserve_clicked={reserve_action}")
                        else:
                            reserve_action = auto_click_reserve_button(page=page, timeout_ms=config.timeout_ms)
                            print(f"[{now:%H:%M:%S}] reserve_auto_click={reserve_action}")
                        alert(now, available, config.people)
                        if config.headless:
                            browser.close()
                        else:
                            print("Browser stays open for manual action. Press Ctrl+C to exit.")
                            while True:
                                time.sleep(1)
                        return 0

                except PlaywrightTimeoutError:
                    print(f"[{now:%H:%M:%S}] Timeout while loading/extracting. Retrying...")
                except ValueError as parse_err:
                    print(f"[{now:%H:%M:%S}] Parse warning: {parse_err}")
                except KeyboardInterrupt:
                    print("\nInterrupted by user.")
                    return 130
                except Exception as exc:  # noqa: BLE001
                    print(f"[{now:%H:%M:%S}] Unexpected error: {exc}")

                time.sleep(config.interval)
        finally:
            try:
                context.close()
            finally:
                browser.close()


def main() -> int:
    config = parse_args()
    return monitor(config)


if __name__ == "__main__":
    sys.exit(main())
