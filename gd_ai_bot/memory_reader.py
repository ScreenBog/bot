"""Read Geometry Dash state from configured process memory addresses.

The project ships with placeholder addresses. Add addresses and offsets in
config.json after finding them for your exact game build. This module only reads
explicitly configured values; it does not scan memory or bypass protections.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import logging
import struct
import time
from typing import Any

from .config import BotConfig


LOGGER = logging.getLogger(__name__)


@dataclass
class GameState:
    """Snapshot of the game values used by record/replay and AI modes."""

    player_x: float = 0.0
    player_y: float = 0.0
    speed: float = 0.0
    on_ground: bool = False
    level_percent: float = 0.0
    player_mode: int | None = None
    timestamp: float = 0.0
    connected: bool = False


class MemoryReader:
    """Pymem-based memory reader with JSON-configurable pointer chains."""

    SUPPORTED_TYPES = {"float", "double", "int", "uint", "bool", "byte"}

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.process_name = config.process_name
        self.module_name = str(config.get("memory.module_name", self.process_name))
        self.pointer_size = int(config.get("memory.pointer_size", 4))
        self.address_specs: dict[str, dict[str, Any]] = config.get("memory.addresses", {}) or {}
        self.pm: Any | None = None
        self.module_base: int | None = None

    @property
    def is_connected(self) -> bool:
        return self.pm is not None

    def connect(self) -> bool:
        """Attach to GeometryDash.exe if pymem is installed and the process runs."""
        if importlib.util.find_spec("pymem") is None:
            LOGGER.warning("pymem is not installed; memory reads will use placeholder state.")
            return False

        pymem = importlib.import_module("pymem")
        self.pm = pymem.Pymem(self.process_name)
        module = importlib.import_module("pymem.process").module_from_name(
            self.pm.process_handle,
            self.module_name,
        )
        self.module_base = int(module.lpBaseOfDll) if module else None
        LOGGER.info("Connected to %s; module base=%s", self.process_name, self.module_base)
        return True

    def close(self) -> None:
        """Release the process handle when pymem exposes a close method."""
        if self.pm is not None and hasattr(self.pm, "close_process"):
            self.pm.close_process()
        self.pm = None
        self.module_base = None

    def read_state(self) -> GameState:
        """Return one state snapshot. Missing addresses become safe defaults."""
        state = GameState(timestamp=time.perf_counter(), connected=self.is_connected)
        if not self.is_connected:
            return state

        for field_name in ("player_x", "player_y", "speed", "on_ground", "level_percent", "player_mode"):
            spec = self.address_specs.get(field_name, {})
            value = self._read_configured_value(field_name, spec)
            if value is not None:
                setattr(state, field_name, value)
        return state

    def _read_configured_value(self, name: str, spec: dict[str, Any]) -> Any | None:
        base = spec.get("base")
        value_type = str(spec.get("type", "float")).lower()
        offsets = spec.get("offsets", []) or []

        if base in (None, "", 0):
            LOGGER.debug("No memory address configured for %s; using default.", name)
            return None
        if value_type not in self.SUPPORTED_TYPES:
            LOGGER.error("Unsupported memory type for %s: %s", name, value_type)
            return None

        address = self._parse_address(base)
        if address is None:
            LOGGER.error("Invalid base address for %s: %r", name, base)
            return None

        final_address = self._resolve_pointer_chain(address, offsets)
        if final_address is None:
            return None
        return self._read_typed(final_address, value_type)

    def _parse_address(self, raw_address: int | str) -> int | None:
        if isinstance(raw_address, int):
            parsed = raw_address
        elif isinstance(raw_address, str):
            parsed = int(raw_address, 16) if raw_address.lower().startswith("0x") else int(raw_address)
        else:
            return None

        # Small values are treated as module-relative RVAs for convenience.
        if self.module_base is not None and parsed < 0x10000000:
            return self.module_base + parsed
        return parsed

    def _resolve_pointer_chain(self, base_address: int, offsets: list[int | str]) -> int | None:
        address = base_address
        if not offsets:
            return address

        for raw_offset in offsets[:-1]:
            offset = self._parse_offset(raw_offset)
            pointer_address = address + offset
            pointer_bytes = self.pm.read_bytes(pointer_address, self.pointer_size)
            address = int.from_bytes(pointer_bytes, byteorder="little", signed=False)
            if address == 0:
                LOGGER.debug("Null pointer while resolving chain at %s", hex(pointer_address))
                return None

        return address + self._parse_offset(offsets[-1])

    @staticmethod
    def _parse_offset(raw_offset: int | str) -> int:
        if isinstance(raw_offset, str):
            return int(raw_offset, 16) if raw_offset.lower().startswith("0x") else int(raw_offset)
        return int(raw_offset)

    def _read_typed(self, address: int, value_type: str) -> Any:
        if value_type == "float":
            return float(self.pm.read_float(address))
        if value_type == "double":
            return struct.unpack("<d", self.pm.read_bytes(address, 8))[0]
        if value_type == "int":
            return int(self.pm.read_int(address))
        if value_type == "uint":
            return int.from_bytes(self.pm.read_bytes(address, 4), "little", signed=False)
        if value_type == "bool":
            return bool(self.pm.read_bool(address))
        if value_type == "byte":
            return int(self.pm.read_bytes(address, 1)[0])
        return None
