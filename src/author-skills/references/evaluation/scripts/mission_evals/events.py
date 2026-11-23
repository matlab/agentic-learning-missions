"""Durable, ordered evidence shared by the two evaluation suites."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EventLog:
    """Write each event before returning; never overwrite an existing trace."""

    def __init__(self, path: Path, *, run_id: str, suite: str, case_id: str,
                 mission_name: str | None = None, trial_id: str | None = None):
        self.path = Path(path)
        self._stream = self.path.open("x", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self._sequence = 0
        self._context = dict(run_id=run_id, trial_id=trial_id or run_id, suite=suite,
                             case_id=case_id, mission_name=mission_name, task_id=None,
                             learner_type=None)

    def emit(self, event_type: str, actor: str, payload: dict[str, Any],
             *, turn_id: str | None = None, action_id: str | None = None) -> str:
        with self._lock:
            event_id = str(uuid.uuid4())
            event = dict(self._context, schema_version="1.0", event_id=event_id,
                         timestamp=datetime.now(timezone.utc).isoformat(),
                         sequence=self._sequence + 1, event_type=event_type,
                         actor=actor, turn_id=turn_id, action_id=action_id,
                         payload=payload)
            line = json.dumps(event, ensure_ascii=False, allow_nan=False)
            self._stream.write(line + "\n")
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._sequence += 1
            return event_id

    def close(self) -> None:
        self._stream.close()

    def set_task(self, task_id: str | None) -> None:
        with self._lock:
            self._context["task_id"] = task_id

    def set_learner(self, profile: str) -> None:
        with self._lock:
            self._context["learner_type"] = profile

    def __enter__(self) -> EventLog:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read_events(path: Path) -> list[dict[str, Any]]:
    """Reject damaged or out-of-order evidence instead of silently dropping it."""
    events = []
    identifiers = set()
    with Path(path).open(encoding="utf-8") as stream:
        for sequence, line in enumerate(stream, 1):
            event = json.loads(line)
            if event.get("schema_version") != "1.0":
                raise ValueError(f"Unsupported event schema on line {sequence}")
            if event.get("sequence") != sequence:
                raise ValueError(f"Out-of-order event on line {sequence}")
            identifier = event["event_id"]
            if identifier in identifiers:
                raise ValueError(f"Duplicate event ID on line {sequence}")
            identifiers.add(identifier)
            events.append(event)
    return events


def write_json(path: Path, value: Any) -> None:
    """Atomically publish a report after a complete JSON serialization."""
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    staging = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with staging.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)
