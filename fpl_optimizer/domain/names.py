"""Canonical player-name construction and search helpers."""

from __future__ import annotations

import unicodedata

SPECIAL_LATIN_TRANSLITERATION = str.maketrans(
    {
        "æ": "ae",
        "ð": "d",
        "đ": "d",
        "ł": "l",
        "ø": "o",
        "œ": "oe",
        "þ": "th",
    }
)


def clean_name(value: str | None) -> str:
    """Collapse provider whitespace and return a display-safe name part."""

    return " ".join((value or "").split())


def full_player_name(first_name: str, second_name: str, web_name: str) -> str:
    """Return the official full name with a safe web-name fallback."""

    full_name = " ".join(part for part in (clean_name(first_name), clean_name(second_name)) if part)
    return full_name or clean_name(web_name) or "Unknown player"


def display_player_name(first_name: str, second_name: str, web_name: str) -> str:
    """Return the preferred recognizable name used by detailed application views."""

    return full_player_name(first_name, second_name, web_name)


def resolved_player_name(
    stored_name: str | None,
    first_name: str,
    second_name: str,
    web_name: str,
) -> str:
    """Use a stored canonical name, with a fallback for pre-migration rows."""

    return clean_name(stored_name) or display_player_name(first_name, second_name, web_name)


def player_name_search_text(
    first_name: str,
    second_name: str,
    web_name: str,
    full_name: str | None = None,
) -> str:
    """Return accent-insensitive searchable text covering every official name form."""

    values = (
        clean_name(first_name),
        clean_name(second_name),
        clean_name(web_name),
        clean_name(full_name) or full_player_name(first_name, second_name, web_name),
    )
    combined = " ".join(dict.fromkeys(value for value in values if value))
    return _search_normalize(combined)


def normalize_name_query(value: str) -> str:
    """Normalize a user-entered name fragment for partial matching."""

    return _search_normalize(clean_name(value))


def _search_normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold()).translate(
        SPECIAL_LATIN_TRANSLITERATION
    )
    return "".join(character for character in decomposed if not unicodedata.combining(character))
