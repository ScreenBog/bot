"""Replay recorded Geometry Dash jump routes."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import Any

from .config import BotConfig
from .input_controller import InputController
from .memory_reader import GameState, MemoryReader


LOGGER = logging.getLogger(__name__)


class RouteReplay:
    """Replays routes by elapsed time or configured RAM coordinate."""

    def __init__(self, config: BotConfig, memory_reader: MemoryReader, input_controller: InputController) -> None:
        self.config = config
        self.memory_reader = memory_reader
        self.input_controller = input_controller
        self.coordinate_tolerance = float(config.get("replay.coordinate_tolerance", 0.15))

    def run(self, route_path: str | Path, use_time: bool = False) -> None:
        route = self.load(route_path)
        events = route.get("events", [])
        coordinate_source = str(route.get("coordinate_source", "percent"))
        start = time.perf_counter()
        index = 0
        LOGGER.info("Replaying %d events from %s", len(events), route_path)

        while index < len(events):
            if self.input_controller.emergency_stop_requested():
                LOGGER.warning("Emergency stop requested; replay interrupted.")
                self.input_controller.release_jump(source="replay_stop")
                break

            event = events[index]
            should_fire = self._time_reached(event, start) if use_time else self._coordinate_reached(event, coordinate_source)
            if should_fire:
                self._apply_event(event)
                index += 1
            else:
                time.sleep(0.001)

    @staticmethod
    def load(route_path: str | Path) -> dict[str, Any]:
        with Path(route_path).open("r", encoding="utf-8") as file_obj:
            return json.load(file_obj)

    def _time_reached(self, event: dict[str, Any], start: float) -> bool:
        return time.perf_counter() - start >= float(event.get("time_seconds", 0.0))

    def _coordinate_reached(self, event: dict[str, Any], coordinate_source: str) -> bool:
        state = self.memory_reader.read_state()
        current = self._coordinate_from_state(state, coordinate_source)
        target = float(event.get("coordinate", 0.0))
        return current + self.coordinate_tolerance >= target

    @staticmethod
    def _coordinate_from_state(state: GameState, coordinate_source: str) -> float:
        if coordinate_source == "x":
            return float(state.player_x)
        return float(state.level_percent)

    def _apply_event(self, event: dict[str, Any]) -> None:
        action = str(event.get("action", ""))
        if action == "press":
            self.input_controller.press_jump(source="replay")
        elif action == "release":
            self.input_controller.release_jump(source="replay")
        LOGGER.info("replay %s at coordinate=%s", action, event.get("coordinate"))
