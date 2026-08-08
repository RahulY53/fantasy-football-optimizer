"""Canonical Premier League team aliases for vendor fixture matching."""

from __future__ import annotations

import re
from pathlib import Path

import yaml  # type: ignore[import-untyped]


class TeamAliases:
    """Resolve common team-name variants to a stable canonical label."""

    def __init__(self, path: Path) -> None:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        groups: dict[str, list[str]] = payload.get("aliases", {})
        self.lookup = {
            _normalize(alias): canonical
            for canonical, aliases in groups.items()
            for alias in [canonical, *aliases]
        }

    def canonical(self, value: str) -> str:
        """Return a configured canonical name or a normalized fallback."""

        normalized = _normalize(value)
        return self.lookup.get(normalized, normalized)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
