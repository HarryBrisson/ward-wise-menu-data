# Changelog

## v1.0.0 — 2026-10-16
First release.
- 51,073 line items, 2005 – 2026 Q1 (2026 partial); 94.8% geocoded.
- Every point is checked against its own ward on the applicable map; 1,127 that land elsewhere are discarded (`rejected_outside_ward`), and `ward_map_fit` records the map that matched.
- 2024+ rows from the latest cumulative quarterly report per year (2024 Q4, 2025 Q4, 2026 Q1).
- "Police Cameras" harmonized to "Cameras" (`category_raw` keeps the original).
- 150 out-of-Chicago geocodes from the 2024+ address cache rejected (`rejected_out_of_bounds`).
- Reproduces the City That Works 2023 sidewalk-share finding (Ward 50 4.1%, Ward 40 24.6%).
- Infrastructure menu price list: 111 rows, each with source and confidence label (no city-published price sheet found; see `data/infrastructure_menu_SOURCES.md`).
