"""Configuration loading and validation for the Geometry Dash offline bot."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")


class ConfigError(ValueError):
    """Raised when the configuration file is missing required values."""


@dataclass(frozen=True)
class BotConfig:
    """Thin wrapper around the JSON configuration dictionary."""

    data: dict[str, Any]
    path: Path

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Read a nested key using dot notation, returning *default* if missing."""
        current: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    @property
    def process_name(self) -> str:
        return str(self.get("process.name", "GeometryDash.exe"))

    @property
    def emergency_stop_key(self) -> str:
        return str(self.get("safety.emergency_stop_key", "esc"))


def load_config(path: str | Path | None = None) -> BotConfig:
    """Load JSON configuration from *path* or the bundled config.json."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)

    if not isinstance(data, dict):
        raise ConfigError("Config root must be a JSON object.")
    if not data.get("safety", {}).get("offline_only", False):
        raise ConfigError("This project is intentionally limited to offline/single-player use.")

    return BotConfig(data=data, path=config_path)
