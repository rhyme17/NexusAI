from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.message_bus import InMemoryMessageBus, get_message_bus
from app.services.migration import export_runtime_snapshot, import_runtime_snapshot, snapshot_counts, validate_runtime_snapshot
from app.services.store import get_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export or import NexusAI runtime snapshots for cutover migration.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export the current runtime snapshot to a JSON file.")
    export_parser.add_argument("--output", required=True, help="Output JSON file path.")

    import_parser = subparsers.add_parser("import", help="Import a runtime snapshot into the currently configured backend.")
    import_parser.add_argument("--input", required=True, help="Input JSON file path.")
    import_parser.add_argument(
        "--keep-default-agents",
        action="store_true",
        help="Keep default agents before applying the imported snapshot.",
    )

    verify_parser = subparsers.add_parser("verify", help="Validate a snapshot file before import.")
    verify_parser.add_argument("--input", required=True, help="Input JSON file path.")

    return parser.parse_args()


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    args = parse_args()
    try:
        if args.command == "verify":
            input_path = Path(args.input).expanduser().resolve()
            if not input_path.exists():
                _print_json({"status": "error", "error": "snapshot file does not exist", "input": str(input_path)})
                return 2
            snapshot = json.loads(input_path.read_text(encoding="utf-8"))
            errors = validate_runtime_snapshot(snapshot)
            if errors:
                _print_json({"status": "invalid", "input": str(input_path), "errors": errors})
                return 1
            _print_json({"status": "valid", "input": str(input_path), "counts": snapshot_counts(snapshot)})
            return 0

        store = get_store()
        bus: InMemoryMessageBus = get_message_bus()

        if args.command == "export":
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot = export_runtime_snapshot(store=store, bus=bus)
            output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            _print_json({"status": "exported", "output": str(output_path), "counts": snapshot.get("counts", {})})
            return 0

        input_path = Path(args.input).expanduser().resolve()
        if not input_path.exists():
            _print_json({"status": "error", "error": "snapshot file does not exist", "input": str(input_path)})
            return 2

        snapshot = json.loads(input_path.read_text(encoding="utf-8"))
        result = import_runtime_snapshot(
            snapshot,
            store=store,
            bus=bus,
            keep_default_agents=bool(args.keep_default_agents),
        )
        _print_json({"status": "imported", "input": str(input_path), **result})
        return 0
    except json.JSONDecodeError as exc:
        _print_json({"status": "error", "error": "invalid json", "detail": str(exc)})
        return 2
    except Exception as exc:  # pragma: no cover - defensive path for CLI runtime failures
        _print_json({"status": "error", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

