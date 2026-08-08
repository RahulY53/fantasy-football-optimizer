"""Atomic, content-addressed JSON response cache."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """A cached provider payload and its retrieval metadata."""

    key: str
    payload: Any
    payload_hash: str
    payload_path: Path
    retrieved_at: datetime

    def is_fresh(self, ttl_seconds: int, now: datetime | None = None) -> bool:
        """Return whether the entry falls within a non-negative TTL."""

        reference = now or datetime.now(UTC)
        return reference - self.retrieved_at <= timedelta(seconds=ttl_seconds)


class JsonCache:
    """Store immutable JSON bodies and one atomic latest pointer per cache key."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, payload: Any, retrieved_at: datetime | None = None) -> CacheEntry:
        """Persist a payload atomically and update its latest pointer."""

        timestamp = retrieved_at or datetime.now(UTC)
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        key_dir = self.root / self._safe_key(key)
        key_dir.mkdir(parents=True, exist_ok=True)
        payload_path = key_dir / f"{digest}.json"
        if not payload_path.exists():
            self._atomic_write(payload_path, body)
        metadata = {
            "key": key,
            "payload_hash": digest,
            "payload_path": payload_path.name,
            "retrieved_at": timestamp.isoformat(),
        }
        self._atomic_write(key_dir / "latest.json", json.dumps(metadata, sort_keys=True))
        return CacheEntry(key, payload, digest, payload_path, timestamp)

    def latest(self, key: str) -> CacheEntry | None:
        """Load the latest valid entry or return `None` for missing/corrupt data."""

        key_dir = self.root / self._safe_key(key)
        metadata_path = key_dir / "latest.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            payload_path = key_dir / str(metadata["payload_path"])
            payload_text = payload_path.read_text(encoding="utf-8")
            digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
            if digest != metadata["payload_hash"]:
                return None
            timestamp = datetime.fromisoformat(metadata["retrieved_at"])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return CacheEntry(
                key=key,
                payload=json.loads(payload_text),
                payload_hash=digest,
                payload_path=payload_path,
                retrieved_at=timestamp,
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _safe_key(key: str) -> str:
        normalized = "".join(char if char.isalnum() else "_" for char in key).strip("_")
        if not normalized:
            raise ValueError("Cache key must contain at least one alphanumeric character")
        return normalized

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".cache-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
