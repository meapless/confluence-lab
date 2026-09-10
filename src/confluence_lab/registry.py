from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(
        _jsonable(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _hash_record(previous_hash: str, payload: dict[str, Any]) -> str:
    material = f"{previous_hash}\n{_canonical(payload)}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def read_registry(path: str | Path) -> list[dict[str, Any]]:
    registry_path = Path(path)
    if not registry_path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        registry_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid registry JSON on line {line_number}") from exc
    return records


def verify_registry(path: str | Path) -> bool:
    previous_hash = "GENESIS"
    for record in read_registry(path):
        stored_hash = record.get("record_hash")
        stored_previous = record.get("previous_hash")
        payload = {
            key: value
            for key, value in record.items()
            if key not in {"record_hash", "previous_hash"}
        }
        if stored_previous != previous_hash:
            return False
        if stored_hash != _hash_record(previous_hash, payload):
            return False
        previous_hash = stored_hash
    return True


def append_experiment_record(
    path: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    if not verify_registry(registry_path):
        raise ValueError("experiment registry hash chain is invalid; refusing to append")

    existing = read_registry(registry_path)
    previous_hash = existing[-1]["record_hash"] if existing else "GENESIS"
    record_payload = {
        "run_id": str(uuid4()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **_jsonable(payload),
    }
    record_hash = _hash_record(previous_hash, record_payload)
    record = {
        **record_payload,
        "previous_hash": previous_hash,
        "record_hash": record_hash,
    }

    with registry_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    return record
