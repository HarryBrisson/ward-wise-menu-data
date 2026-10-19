# Changelog

## v1.1.2 — 2026-10-19
Price-list sourcing corrections. No line-item or cost-table changes.
- The 22 prices from CDOT's 2023 Aldermanic Menu packet are relabeled `foia_response` (was `ward_wise_2023_unverified`). Ward Wise Chicago obtained the packet through a FOIA request to CDOT. `foia_response` ranks just below `primary_document`.
- The bike-lane unit note now explains the standardization: half-mile prices converted to per block at 8 blocks ≈ 1 mile, so items compare apples to apples.

## v1.1.1 — 2026-10-17
- Item cost tables are now byte-reproducible: every tie is broken by row `id`, so rebuilds give the same row order on any pandas version. Values are unchanged from v1.1.0.

## v1.1.0 — 2026-10-17
What wards actually paid, per item type (`scripts/build_item_costs.py`). Line items are unchanged from v1.0.0.
- `menu_item_types.csv`: every normalized item name and the type it was grouped under (30 types, 97.6% of line items).
- `menu_item_costs_year.csv`: per type and year, the count plus min / p10 / p25 / median / p75 / p90 / max cost per project, and per block where it can be derived from address ranges.
- `menu_item_costs_ward.csv`: per type and ward, 2023–2025.
- `menu_item_costs.json`: all of the above plus the cheapest and most expensive examples, linked to their source PDFs.

## v1.0.0 — 2026-10-16
First release.
- 51,073 line items, 2005 – 2026 Q1 (2026 partial); 94.8% geocoded.
- Every point is checked against its own ward on the applicable map; 1,127 that land elsewhere are discarded (`rejected_outside_ward`), and `ward_map_fit` records the map that matched.
- 2024+ rows from the latest cumulative quarterly report per year (2024 Q4, 2025 Q4, 2026 Q1).
- "Police Cameras" harmonized to "Cameras" (`category_raw` keeps the original).
- 150 out-of-Chicago geocodes from the 2024+ address cache rejected (`rejected_out_of_bounds`).
- Reproduces the City That Works 2023 sidewalk-share finding (Ward 50 4.1%, Ward 40 24.6%).
- Infrastructure menu price list: 111 rows, each with source and confidence label (no city-published price sheet found; see `data/infrastructure_menu_SOURCES.md`).
