"""Tests for the atomic JSON cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fpl_optimizer.data.cache import JsonCache


def test_cache_round_trip_and_freshness(tmp_path) -> None:
    cache = JsonCache(tmp_path)
    retrieved = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    stored = cache.put("/fixtures/", [{"id": 1}], retrieved_at=retrieved)

    loaded = cache.latest("/fixtures/")

    assert loaded is not None
    assert loaded.payload == [{"id": 1}]
    assert loaded.payload_hash == stored.payload_hash
    assert loaded.is_fresh(60, now=retrieved + timedelta(seconds=60))
    assert not loaded.is_fresh(60, now=retrieved + timedelta(seconds=61))


def test_cache_detects_modified_payload(tmp_path) -> None:
    cache = JsonCache(tmp_path)
    stored = cache.put("/fixtures/", [{"id": 1}])
    stored.payload_path.write_text("[]", encoding="utf-8")

    assert cache.latest("/fixtures/") is None
