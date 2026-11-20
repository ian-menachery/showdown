"""Poker Now screenshots on a hotkey, for spike S1's reader (DECISIONS 30).

F9 saves the window in front, and only when its title says Poker Now, to the
gitignored data/live/screens/. Nothing else on the screen is saved, and other
windows' titles are never printed or kept.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

SCREENS_DIR = Path("data/live/screens")
Rect = tuple[int, int, int, int]
"""left, top, width, height, in screen pixels."""

_VK_F9, _MOD_NOREPEAT, _WM_HOTKEY, _PM_REMOVE = 0x78, 0x4000, 0x0312, 0x0001


def is_poker_now(title: str) -> bool:
    title = title.lower()
    return "poker now" in title or "pokernow" in title


def shot_path(folder: Path, when: datetime) -> Path:
    """Names sort in capture order, which S1's dev and test split relies on."""
    return folder / f"{when:%Y%m%d-%H%M%S-%f}.png"


def save_shot(
    title: str, rect: Rect, grab: Callable[[Rect], bytes], folder: Path, when: datetime
) -> Path | None:
    """Save the window's PNG and return its path, or None when it isn't Poker Now or has
    no area (minimised)."""
    if not is_poker_now(title) or rect[2] <= 0 or rect[3] <= 0:
        return None
    path = shot_path(folder, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(grab(rect))
    return path


def foreground() -> tuple[str, Rect]:  # pragma: no cover - needs a Windows desktop
    """The title and visible frame of the window in front."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    buffer = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    if user32.IsIconic(hwnd):
        return buffer.value, (0, 0, 0, 0)
    r = wintypes.RECT()
    # DWMWA_EXTENDED_FRAME_BOUNDS: the visible frame, without the invisible resize borders
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r))
    return buffer.value, (r.left, r.top, r.right - r.left, r.bottom - r.top)


def grab_png(rect: Rect) -> bytes:  # pragma: no cover - needs a Windows desktop
    import mss
    import mss.tools

    left, top, width, height = rect
    with mss.mss() as screen:
        shot = screen.grab({"left": left, "top": top, "width": width, "height": height})
    return mss.tools.to_png(shot.rgb, shot.size)


def run(folder: Path, report: Callable[[Path | None], None]) -> None:  # pragma: no cover
    """Wait for F9 until Ctrl+C, saving the Poker Now window at each press."""
    import ctypes
    import time
    from ctypes import wintypes

    try:
        import mss  # noqa: F401
    except ImportError:
        raise SystemExit("needs the live extra: pip install -e .[live]") from None
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # window coordinates in real pixels
    user32 = ctypes.windll.user32
    msg = wintypes.MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # make this thread's queue
    if not user32.RegisterHotKey(None, 1, _MOD_NOREPEAT, _VK_F9):
        raise SystemExit("F9 is already taken by another program")
    try:
        while True:  # polled, so Ctrl+C gets through
            while user32.PeekMessageW(ctypes.byref(msg), None, _WM_HOTKEY, _WM_HOTKEY, _PM_REMOVE):
                title, rect = foreground()
                report(save_shot(title, rect, grab_png, folder, datetime.now()))
            time.sleep(0.05)
    finally:
        user32.UnregisterHotKey(None, 1)
