# Player name data quality

The application keeps the official FPL player ID as the durable identity key. Names are display
metadata and never replace IDs in forecasts, saved squads, optimizer runs, or historical results.

For every official FPL refresh, the canonical full name is built from `first_name` and
`second_name`, with provider whitespace removed. If either provider field is unavailable, the
FPL `web_name` is retained as the safe recognizable fallback. `display_name` currently uses the
same full-name policy; compact pitch-only labels can be introduced later without changing player
identity or detailed tables.

Player search covers first name, surname, full name, and web name. Matching is case-insensitive,
partial, and accent-insensitive, so an unaccented query such as `Fernandez` can match
`Fernández`. Player selectors add team and position to distinguish duplicate or similar names.

Migration `0015` adds and backfills `full_name` and `display_name` for existing databases. Read
paths also retain a computed fallback, which keeps pre-migration and manually constructed records
recognizable during upgrades.
