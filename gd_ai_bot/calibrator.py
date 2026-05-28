"""Manual RAM-address calibration helper for offline Geometry Dash testing.

This module intentionally does not scan memory. It only reads fields already
configured in config.json or a single address supplied by --test-address.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Any

from .config import BotConfig
from .memory_reader import GameState, MemoryReader


LOGGER = logging.getLogger(__name__)
CALIBRATION_FIELDS = ("player_x", "player_y", "speed", "on_ground", "level_percent", "player_mode")


@dataclass(frozen=True)
class TestAddress:
    """One temporary field/address/type override used without editing config.json."""

    field: str
    address: str
    value_type: str


class Calibrator:
    """Print configured RAM values repeatedly so users can verify addresses."""

    def __init__(
        self,
        config: BotConfig,
        memory_reader: MemoryReader,
        watch_field: str | None = None,
        test_address: TestAddress | None = None,
        interval_seconds: float = 0.1,
    ) -> None:
        self.config = config
        self.memory_reader = memory_reader
        self.watch_field = watch_field
        self.test_address = test_address
        self.interval_seconds = interval_seconds
        self._validate_args()
        if self.test_address is not None:
            self._apply_test_address(self.test_address)

    def run(self) -> None:
        """Continuously print state until Ctrl+C is pressed."""
        self._print_header()
        try:
            while True:
                state = self.memory_reader.read_state()
                print(self._format_state_line(state), flush=True)
                time.sleep(self.interval_seconds)
        except KeyboardInterrupt:
            print("\nCalibration stopped by Ctrl+C.")

    def _validate_args(self) -> None:
        if self.watch_field is not None and self.watch_field not in CALIBRATION_FIELDS:
            raise ValueError(f"Unknown --watch field {self.watch_field!r}. Choose one of: {', '.join(CALIBRATION_FIELDS)}")
        if self.test_address is None:
            return
        if self.test_address.field not in CALIBRATION_FIELDS:
            raise ValueError(
                f"Unknown --test-address field {self.test_address.field!r}. "
                f"Choose one of: {', '.join(CALIBRATION_FIELDS)}"
            )
        if self.test_address.value_type not in MemoryReader.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported --test-address type {self.test_address.value_type!r}. "
                f"Choose one of: {', '.join(sorted(MemoryReader.SUPPORTED_TYPES))}"
            )

    def _apply_test_address(self, test_address: TestAddress) -> None:
        self.memory_reader.address_specs[test_address.field] = {
            "base": test_address.address,
            "offsets": [],
            "type": test_address.value_type,
            "description": "Temporary calibrate override; not saved to config.json.",
        }
        LOGGER.info(
            "Temporarily testing %s at %s as %s; config.json is not modified.",
            test_address.field,
            test_address.address,
            test_address.value_type,
        )

    def _print_header(self) -> None:
        print("Geometry Dash RAM calibration (offline/local testing only)")
        print("No memory scanner is used. Only configured addresses or --test-address are read.")
        print(f"Process: {self.config.process_name} | Connected: {self.memory_reader.is_connected}")
        if self.watch_field:
            print(f"Watching field: {self.watch_field}")
        if self.test_address:
            print(
                "Temporary address: "
                f"{self.test_address.field}={self.test_address.address} ({self.test_address.value_type}); "
                "not saved to config.json"
            )
        print(self._format_configuration_status())
        print("Press Ctrl+C to stop. Output refreshes every 0.1 seconds.\n")

    def _format_configuration_status(self) -> str:
        parts: list[str] = []
        for field in CALIBRATION_FIELDS:
            spec = self.memory_reader.address_specs.get(field, {})
            base = spec.get("base")
            value_type = spec.get("type", "?")
            marker = "*" if field == self.watch_field else " "
            if base in (None, "", 0):
                parts.append(f"{marker}{field}=UNSET")
            else:
                parts.append(f"{marker}{field}={base}<{value_type}>")
        return "Configured fields: " + " | ".join(parts)

    def _format_state_line(self, state: GameState) -> str:
        values: dict[str, Any] = {
            "player_x": state.player_x,
            "player_y": state.player_y,
            "speed": state.speed,
            "on_ground": state.on_ground,
            "level_percent": state.level_percent,
            "player_mode": state.player_mode,
        }
        parts: list[str] = []
        for field in CALIBRATION_FIELDS:
            spec = self.memory_reader.address_specs.get(field, {})
            value = values[field]
            label = f"*{field}" if field == self.watch_field else field
            if spec.get("base") in (None, "", 0):
                parts.append(f"{label}=UNSET")
            else:
                parts.append(f"{label}={self._format_value(value)}")
        return " | ".join(parts)

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, float):
            return f"{value:9.3f}"
        return str(value)
