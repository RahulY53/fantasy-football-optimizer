"""Tests for canonical player-name construction and tolerant search."""

from __future__ import annotations

from fpl_optimizer.domain.names import (
    full_player_name,
    normalize_name_query,
    player_name_search_text,
    resolved_player_name,
)


def test_full_name_uses_first_and_second_name_with_clean_whitespace() -> None:
    assert full_player_name("  Bukayo ", "  Saka  ", "Saka") == "Bukayo Saka"


def test_full_name_falls_back_to_web_name_when_official_parts_are_missing() -> None:
    assert full_player_name("", "", "Gabriel") == "Gabriel"
    assert resolved_player_name("", "", "", "Gabriel") == "Gabriel"


def test_search_covers_name_forms_and_ignores_accents_and_case() -> None:
    search_text = player_name_search_text("Enzo", "Fernández", "E. Fernández", "Enzo Fernández")

    assert normalize_name_query("FERNANDEZ") in search_text
    assert normalize_name_query("e. fern") in search_text
    assert normalize_name_query("Enz") in search_text


def test_search_transliterates_special_latin_letters() -> None:
    search_text = player_name_search_text("Martin", "Ødegaard", "Ødegaard")

    assert normalize_name_query("odegaard") in search_text
