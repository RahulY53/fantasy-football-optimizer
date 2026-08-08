"""Framework-independent selection rules for cross-view player comparison."""

from __future__ import annotations

from dataclasses import dataclass

MAX_COMPARE_PLAYERS = 5


@dataclass(frozen=True, slots=True)
class PlayerSelection:
    """A capped, deduplicated player selection and any rejected IDs."""

    player_ids: tuple[int, ...]
    rejected_ids: tuple[int, ...]


def normalize_player_selection(
    player_ids: list[int] | tuple[int, ...],
    *,
    valid_ids: set[int] | frozenset[int] | None = None,
    limit: int = MAX_COMPARE_PLAYERS,
) -> PlayerSelection:
    """Preserve input order while removing duplicates, invalid IDs, and overflow."""

    if limit < 1:
        raise ValueError("Player selection limit must be positive")
    accepted: list[int] = []
    rejected: list[int] = []
    seen: set[int] = set()
    for player_id in player_ids:
        if player_id in seen:
            continue
        seen.add(player_id)
        if (valid_ids is not None and player_id not in valid_ids) or len(accepted) >= limit:
            rejected.append(player_id)
        else:
            accepted.append(player_id)
    return PlayerSelection(tuple(accepted), tuple(rejected))
