"""Shared recorded provider payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def bootstrap_payload() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "bootstrap.json").read_text(encoding="utf-8"))


@pytest.fixture
def fixture_payload() -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIR / "fixtures.json").read_text(encoding="utf-8"))
