"""Command-line entry point for the offline Geometry Dash AI bot project."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from .ai_agent import AiRunner
from .calibrator import Calibrator, TestAddress
from .config import load_config
from .input_controller import InputController
from .memory_reader import MemoryReader
from .recorder import RouteRecorder
from .replay import RouteReplay


def configure_logging(config) -> None:
    log_file = Path(str(config.get("logging.file", "logs/gd_ai_bot_errors.log")))
    log_file.parent.mkdir(parents=True, exist_ok=True)
    level_name = str(config.get("logging.level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline Geometry Dash RAM reader, recorder, replay, and AI bot.")
    parser.add_argument("--config", default=None, help="Path to config.json. Defaults to gd_ai_bot/config.json.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("state", help="Connect and print one RAM state snapshot.")

    calibrate_parser = subparsers.add_parser("calibrate", help="Manually verify configured RAM addresses.")
    calibrate_parser.add_argument(
        "--watch",
        choices=("player_x", "player_y", "speed", "on_ground", "level_percent", "player_mode"),
        help="Highlight one field while printing all calibration values.",
    )
    calibrate_parser.add_argument(
        "--test-address",
        nargs=3,
        metavar=("FIELD", "ADDRESS", "TYPE"),
        help="Temporarily test FIELD at ADDRESS as TYPE without editing config.json.",
    )

    record_parser = subparsers.add_parser("record", help="Record jump presses to a route JSON file.")
    record_parser.add_argument("--output", default=None, help="Route output path.")
    record_parser.add_argument("--duration", type=float, default=None, help="Optional recording duration in seconds.")

    replay_parser = subparsers.add_parser("replay", help="Replay a route JSON file.")
    replay_parser.add_argument("--route", default=None, help="Route path. Defaults to recording.default_route.")
    replay_parser.add_argument("--time", action="store_true", help="Replay by elapsed time instead of RAM coordinate.")

    subparsers.add_parser("ai", help="Run the baseline heuristic AI mode.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)
    configure_logging(config)

    memory_reader = MemoryReader(config)
    try:
        memory_reader.connect()
    except Exception as exc:  # Runtime attach/read failures should not hide the CLI help path.
        logging.getLogger(__name__).error("Could not connect to %s: %s", config.process_name, exc)

    input_controller = InputController(config)

    if args.command == "state":
        state = memory_reader.read_state()
        print(state)
    elif args.command == "calibrate":
        test_address = None
        if args.test_address:
            field, address, value_type = args.test_address
            test_address = TestAddress(field=field, address=address, value_type=value_type.lower())
        Calibrator(config, memory_reader, watch_field=args.watch, test_address=test_address).run()
    elif args.command == "record":
        output = args.output or config.get("recording.default_route", "routes/default_route.json")
        RouteRecorder(config, memory_reader).record(output, duration_seconds=args.duration)
    elif args.command == "replay":
        route = args.route or config.get("recording.default_route", "routes/default_route.json")
        RouteReplay(config, memory_reader, input_controller).run(route, use_time=args.time)
    elif args.command == "ai":
        AiRunner(config, memory_reader, input_controller).run()
    else:
        return 2

    memory_reader.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
