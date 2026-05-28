"""Input control for offline Geometry Dash experiments.

The controller supports WinAPI on Windows and optional pyautogui/keyboard
fallbacks. It never hides itself and exposes an emergency stop key.
"""

from __future__ import annotations

import ctypes
import importlib
import importlib.util
import logging
import sys
import time
from dataclasses import dataclass

from .config import BotConfig


LOGGER = logging.getLogger(__name__)


@dataclass
class InputAction:
    pressed: bool
    timestamp: float
    source: str


class InputController:
    """Press/release jump using the configured backend."""

    VK_SPACE = 0x20
    KEYEVENTF_KEYUP = 0x0002
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    def __init__(self, config: BotConfig) -> None:
        self.backend = str(config.get("input.backend", "winapi")).lower()
        self.jump_button = str(config.get("input.jump_button", "space")).lower()
        self.minimum_press_seconds = float(config.get("input.minimum_press_seconds", 0.025))
        self.minimum_gap_seconds = float(config.get("input.minimum_gap_seconds", 0.015))
        self.emergency_stop_key = config.emergency_stop_key
        self._pressed = False
        self._last_change = 0.0

    @property
    def pressed(self) -> bool:
        return self._pressed

    def emergency_stop_requested(self) -> bool:
        """Return True when the configured emergency key is currently pressed."""
        if importlib.util.find_spec("keyboard") is not None:
            keyboard = importlib.import_module("keyboard")
            return bool(keyboard.is_pressed(self.emergency_stop_key))
        if sys.platform == "win32" and self.emergency_stop_key.lower() == "esc":
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000)
        return False

    def tap_jump(self, source: str = "bot") -> None:
        """Press and release jump respecting the configured minimum duration."""
        self.press_jump(source=source)
        time.sleep(self.minimum_press_seconds)
        self.release_jump(source=source)

    def press_jump(self, source: str = "bot") -> None:
        now = time.perf_counter()
        if self._pressed or now - self._last_change < self.minimum_gap_seconds:
            return
        self._send_down()
        self._pressed = True
        self._last_change = now
        LOGGER.info("jump_down source=%s", source)

    def release_jump(self, source: str = "bot") -> None:
        now = time.perf_counter()
        if not self._pressed:
            return
        if now - self._last_change < self.minimum_press_seconds:
            time.sleep(self.minimum_press_seconds - (now - self._last_change))
        self._send_up()
        self._pressed = False
        self._last_change = time.perf_counter()
        LOGGER.info("jump_up source=%s", source)

    def _send_down(self) -> None:
        if self.backend == "pyautogui" and importlib.util.find_spec("pyautogui") is not None:
            pyautogui = importlib.import_module("pyautogui")
            if self._uses_mouse_button():
                pyautogui.mouseDown(button="left")
            else:
                pyautogui.keyDown(self.jump_button)
            return
        if self.backend == "keyboard" and importlib.util.find_spec("keyboard") is not None and not self._uses_mouse_button():
            importlib.import_module("keyboard").press(self.jump_button)
            return
        self._winapi_key_event(is_down=True)

    def _send_up(self) -> None:
        if self.backend == "pyautogui" and importlib.util.find_spec("pyautogui") is not None:
            pyautogui = importlib.import_module("pyautogui")
            if self._uses_mouse_button():
                pyautogui.mouseUp(button="left")
            else:
                pyautogui.keyUp(self.jump_button)
            return
        if self.backend == "keyboard" and importlib.util.find_spec("keyboard") is not None and not self._uses_mouse_button():
            importlib.import_module("keyboard").release(self.jump_button)
            return
        self._winapi_key_event(is_down=False)

    def _winapi_key_event(self, is_down: bool) -> None:
        if sys.platform != "win32":
            LOGGER.warning("WinAPI input is only available on Windows; input skipped.")
            return
        if self._uses_mouse_button():
            flag = self.MOUSEEVENTF_LEFTDOWN if is_down else self.MOUSEEVENTF_LEFTUP
            ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)
            return
        flags = 0 if is_down else self.KEYEVENTF_KEYUP
        ctypes.windll.user32.keybd_event(self.VK_SPACE, 0, flags, 0)

    def _uses_mouse_button(self) -> bool:
        return self.jump_button in {"left_mouse", "mouse", "lmb"}
