"""Record human jump input against level progress or X coordinate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib
import importlib.util
import ctypes
import json
import logging
from pathlib import Path
import sys
import time
from typing import Iterable

from .config import BotConfig
from .memory_reader import GameState, MemoryReader


LOGGER = logging.getLogger(__name__)


@dataclass
class RecordedEvent:
    action: str
    coordinate: float
    time_seconds: float
    state: dict[str, float | int | bool | None]


class RouteRecorder:
    """Poll keyboard/mouse state and save edge events to a JSON route."""

    def __init__(self, config: BotConfig, memory_reader: MemoryReader) -> None:
        self.config = config
        self.memory_reader = memory_reader
        self.coordinate_source = str(config.get("recording.coordinate_source", "percent"))
        self.events: list[RecordedEvent] = []

    def record(self, output_path: str | Path, duration_seconds: float | None = None) -> Path:
        """Record until Esc/emergency key or optional duration expires."""
        if importlib.util.find_spec("keyboard") is None:
            raise RuntimeError("Recording requires the optional 'keyboard' package on Windows.")

        keyboard = importlib.import_module("keyboard")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        last_pressed = False
        LOGGER.info("Recording route to %s. Press %s to stop.", output, self.config.emergency_stop_key)

        while True:
            now = time.perf_counter()
            if duration_seconds is not None and now - start >= duration_seconds:
                break
            if keyboard.is_pressed(self.config.emergency_stop_key):
                break

            state = self.memory_reader.read_state()
            pressed = self._jump_is_pressed(keyboard)
            if pressed != last_pressed:
                action = "press" if pressed else "release"
                event = self._make_event(action, state, now - start)
                self.events.append(event)
                LOGGER.info("record %s at %.3f", action, event.coordinate)
                last_pressed = pressed
            time.sleep(0.002)

        return self.save(output)

    def save(self, output_path: str | Path) -> Path:
        output = Path(output_path)
        payload = {
            "version": 1,
            "coordinate_source": self.coordinate_source,
            "created_at_unix": time.time(),
            "events": [asdict(event) for event in self.events],
        }
        with output.open("w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, indent=2, ensure_ascii=False)
        return output

    def _make_event(self, action: str, state: GameState, elapsed: float) -> RecordedEvent:
        return RecordedEvent(
            action=action,
            coordinate=self._coordinate_from_state(state),
            time_seconds=elapsed,
            state={
                "player_x": state.player_x,
                "player_y": state.player_y,
                "speed": state.speed,
                "on_ground": state.on_ground,
                "level_percent": state.level_percent,
                "player_mode": state.player_mode,
            },
        )

    def _coordinate_from_state(self, state: GameState) -> float:
        if self.coordinate_source == "x":
            return float(state.player_x)
        return float(state.level_percent)

    @staticmethod
    def _jump_is_pressed(keyboard_module: object) -> bool:
        checks: Iterable[str] = ("space",)
        keyboard_pressed = any(bool(keyboard_module.is_pressed(key)) for key in checks)
        if keyboard_pressed:
            return True
        if sys.platform == "win32":
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        return False
