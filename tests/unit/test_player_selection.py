"""Tests for capped cross-view Player Compare selections."""

from __future__ import annotations

import pytest

from fpl_optimizer.analytics.selection import normalize_player_selection


def test_selection_preserves_order_and_removes_duplicates() -> None:
    selection = normalize_player_selection([4, 2, 4, 1])

    assert selection.player_ids == (4, 2, 1)
    assert selection.rejected_ids == ()


def test_selection_rejects_invalid_and_overflow_players() -> None:
    selection = normalize_player_selection(
        [1, 8, 2, 3, 4, 5, 6],
        valid_ids={1, 2, 3, 4, 5, 6},
    )

    assert selection.player_ids == (1, 2, 3, 4, 5)
    assert selection.rejected_ids == (8, 6)


def test_selection_requires_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        normalize_player_selection([1], limit=0)
