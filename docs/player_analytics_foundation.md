# Player analytics foundation

Player tables and visual analytics share one immutable analytical dataset. The application service
joins current player metadata with already-generated statistical/market forecasts and current
strategy scores; changing a filter or chart control never reruns forecasting or optimization.

The dataset exposes recognizable player identity, team and position, raw price/ownership/forecast
metrics, strategy value/risk/score, and percentile-normalized values. Raw values remain the source
for tables, scatter axes, exports, and tooltips. Normalized values are reserved for cross-metric
comparison such as radar charts. Metrics where lower is better, currently risk and price, invert
their normalized score so a higher normalized value consistently means a more favorable outcome.

The metric registry is the single source for labels, descriptions, units, display formats,
position support, direction, and normalization method. Future Compare, radar, and matrix views
must consume this registry rather than duplicating metric definitions in Streamlit pages.

The reusable filter specification combines name, one or more clubs, one or more positions, price,
ownership, expected minutes, next/three/five-Gameweek xPts, risk, optimization score, availability,
and future watchlist membership. Filters operate only on the cached analytical records.
