# Player Compare and radar chart

The Player Analytics page reuses the cached analytical dataset. Searching, filtering, changing a
comparison universe, selecting radar dimensions, or opening a different tab does not rerun a
forecast, optimization, or simulation.

## Explorer and comparison table

The Explorer combines name, club, position, price, ownership, expected-minutes, expected-points,
risk, availability, and strategy-score filters. Users can configure and sort its columns, then
choose two to five players from the filtered result. The comparison table displays raw values in
their original units. Unsupported or unavailable market-only fields are omitted rather than
estimated.

## Radar normalization

Radar dimensions use tie-aware percentile ranks from zero to 100. The comparison universe can be
all players, players at the selected position, or only the selected players. Same Position is the
default for a single-position comparison; All Players is the default for mixed positions.

Every radar direction is favorable: higher means better. Negative metrics are therefore inverted
and relabelled—Risk becomes Reliability, Price becomes Affordability, and Ownership becomes
Differential Appeal. Hover text always exposes the raw value and unit so the normalized chart does
not hide the underlying projection.

Position-specific defaults use only metrics already produced by the current forecast model. The
application does not invent xG, xA, VORP, ceiling, consistency, or other future-roadmap metrics.
Those dimensions can be added to the same registry after their forecasting releases are built.

## Freshness and limitations

The page displays official FPL, statistical forecast, and market forecast timestamps when they are
available. The goal probability is market-derived and may be absent where player odds have not
been imported. All radar percentiles are relative ranks, not probabilities or guarantees.
