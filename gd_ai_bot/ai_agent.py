"""Simple swappable AI agent for Geometry Dash offline experiments."""

from __future__ import annotations

import logging
import time

from .config import BotConfig
from .input_controller import InputController
from .memory_reader import GameState, MemoryReader


LOGGER = logging.getLogger(__name__)


class HeuristicAgent:
    """Baseline jump/no-jump policy designed to be replaced by a model later."""

    def __init__(self, config: BotConfig) -> None:
        self.jump_every_x_units = float(config.get("ai.heuristic.jump_every_x_units", 130.0))
        self.min_x_for_auto_jump = float(config.get("ai.heuristic.min_x_for_auto_jump", 20.0))
        self.jump_cooldown_seconds = float(config.get("ai.jump_cooldown_seconds", 0.09))
        self._last_jump_time = 0.0
        self._last_jump_bucket = -1

    def decide(self, state: GameState) -> bool:
        """Return True when the bot should tap jump for this state."""
        now = time.perf_counter()
        if not state.on_ground:
            return False
        if state.player_x < self.min_x_for_auto_jump:
            return False
        if now - self._last_jump_time < self.jump_cooldown_seconds:
            return False

        bucket = int(state.player_x // self.jump_every_x_units)
        should_jump = bucket > self._last_jump_bucket
        if should_jump:
            self._last_jump_bucket = bucket
            self._last_jump_time = now
        return should_jump


class AiRunner:
    """Continuously read RAM state, ask the agent, and send jump inputs."""

    def __init__(self, config: BotConfig, memory_reader: MemoryReader, input_controller: InputController) -> None:
        self.config = config
        self.memory_reader = memory_reader
        self.input_controller = input_controller
        self.agent = HeuristicAgent(config)
        self.decision_interval = float(config.get("ai.decision_interval_seconds", 0.01))

    def run(self) -> None:
        LOGGER.info("AI mode started. Press %s to stop.", self.config.emergency_stop_key)
        while not self.input_controller.emergency_stop_requested():
            state = self.memory_reader.read_state()
            LOGGER.info(
                "state x=%.2f y=%.2f speed=%.2f ground=%s percent=%.2f mode=%s",
                state.player_x,
                state.player_y,
                state.speed,
                state.on_ground,
                state.level_percent,
                state.player_mode,
            )
            if self.agent.decide(state):
                LOGGER.info("AI decision: jump")
                self.input_controller.tap_jump(source="ai")
            time.sleep(self.decision_interval)
        self.input_controller.release_jump(source="ai_stop")
        LOGGER.info("AI mode stopped.")
