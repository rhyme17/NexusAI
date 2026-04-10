from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def load_json_file(path: Path, default_factory: Callable[[], T]) -> T:
    if not path.exists():
        return default_factory()

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load JSON persistence file '%s': %s", path, exc)
        return default_factory()


def write_json_file_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f"{path.stem}.",
        suffix=f"{path.suffix}.tmp",
        delete=False,
    ) as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        temp_path = Path(file.name)
    last_error: OSError | None = None
    for _ in range(3):
        try:
            os.replace(temp_path, path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)

    logger.warning("Failed to persist JSON file '%s': %s", path, last_error)
    try:
        temp_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to clean up temp persistence file '%s'", temp_path)


def merge_json_object_atomic(
    path: Path,
    updates: dict[str, Any],
    *,
    remove_keys: Iterable[str] = (),
) -> None:
    existing = load_json_file(path, default_factory=dict)
    if not isinstance(existing, dict):
        existing = {}

    merged = dict(existing)
    for key in remove_keys:
        merged.pop(key, None)
    merged.update(updates)
    write_json_file_atomic(path, merged)


