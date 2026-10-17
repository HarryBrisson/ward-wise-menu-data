# Methodology

## What the Aldermanic Menu is

Each year the City of Chicago (CDOT, with the Office of Budget and Management) gives every alder a fixed capital allotment to spend from a **menu** of standard neighborhood infrastructure: street and alley resurfacing, sidewalks, lighting, speed humps, bump-outs, bike lanes and similar items. Alders can also fund some non-menu items such as cameras, park and school projects, and beautification.

The allotment was about $1.32M per ward through the 2010s and has been $1.5M since 2021. OBM publishes itemized postings of what each ward funded.

## Sources

| Years | Document | How the rows were extracted |
|---|---|---|
| 2005–2011 | OBM postings in the Capital Improvements Archive | Scraped by Jake Smith and John C. Ruf; cleaned in ward-wise/data-analysis |
| 2012–2023 | Annual "Menu" postings (one PDF per year, listed in `sources/pdf_manifest.csv`) | ward-wise/data-analysis extractor (Sean MacMullan et al.) |
| 2024–2026 | Quarterly "Menu Program Reports" | Same extractor, adapted to the quarterly layout (Ward Wise) |

Every row carries `source_pdf` and `source_url`. `sources/pdf_manifest.csv` records each PDF's sha256 and the date its chicago.gov URL was last confirmed.

**Gaps in that record:**
- The city no longer serves the 2023 annual posting at any known address. Its rows cite the public mirror in ward-wise/data-analysis.
- 2005–2011 rows have no `source_url`. Those PDFs were not archived with the extraction.

## Periods and partial years

- **Quarterly reports are cumulative year-to-date.** For 2024 onward we keep only each year's latest report: 2024 Q4, 2025 Q4 and 2026 Q1.
- **Partial years are flagged.** A year whose latest report is before Q4 has `is_partial_year = true` (currently 2026). Do not compare a partial year's totals to full years.
- **2023 has two sources.** The 2023 annual posting is used. A separate "Q4 2023 update" exists but is not used.

## Columns (`menu_line_items.csv`)

| Column | Meaning |
|---|---|
| `id` | Stable 12-character hash of ward, year, item, location and cost, plus an ordinal for exact duplicates (the PDFs repeat some rows) |
| `ward` | Ward 1–50. **99** = posted without a ward (15 rows in 2023). Excluded from ward tables. |
| `year` | Menu (program) year |
| `period` | `annual`, or the quarter of the cumulative report used |
| `item` | Menu item as printed |
| `description` | Upstream description, where present |
| `location` | Location as printed. Multi-location projects are separated by `:` or `;`. |
| `cost` | Dollars, as printed |
| `category` | One of 15 standard categories (below) |
| `category_raw` | The category before harmonization. "Police Cameras" in older rows is now "Cameras". |
| `active_transport` | Whether `category` is Bicycle Infrastructure, Pedestrian Infrastructure or Street Redesign |
| `lat`, `lng` | Representative point for the location |
| `geocode_status` | `geocoded`, `unlocatable`, `not_geocoded`, `rejected_out_of_bounds` or `rejected_outside_ward` (see below) |
| `geocode_method` | How the point was found (see below) |
| `ward_map` | Ward boundaries in force that year: 2003, 2015 or 2023. New maps were seated in May 2015 and May 2023. |
| `ward_map_fit` | The map whose ward actually contains the point (see "Ward check") |
| `source_pdf`, `source_url` | The posting the row came from |
| `provenance` | Who extracted the row |

`geocode_status` values:
- `unlocatable`: the location text names no findable place.
- `not_geocoded`: not attempted yet.
- `rejected_out_of_bounds`: a geocoder returned a point outside Chicago, which was discarded.
- `rejected_outside_ward`: the point is in Chicago but not in the project's own ward (see "Ward check"), so it was discarded.

## Categories

The 15 categories come from item-name rules in the upstream `categorization.py`:

- Street Resurfacing
- Sidewalk Repair
- Alleys
- Lighting
- Pedestrian Infrastructure
- Street Redesign
- Bicycle Infrastructure
- Traffic Signals
- Viaducts
- Parks
- Schools
- Cameras
- Beautification
- Misc. CDOT
- Misc.

Categories describe what an item **is**, not what it is for. A speed-hump item counts as Alleys or Pedestrian Infrastructure depending on its menu line.

## Geocoding

Overall, 94.8% of rows are geocoded. Coverage per year is in `release_summary.json`. Methods, in order of preference:

1. **2019–2022:** the upstream geocoder's output (`upstream_geocoder`), with line and polygon geometry where it returned one.
2. **2005–2018 and gaps in 2019–2023:** a local geocoder.
   - It first applies the upstream address grammar.
   - Then it matches street-centerline intersections: alleys go to the centroid of their four corners; street segments go to the midpoint between their bounding cross streets.
   - Location text the PDF extraction garbled was repaired by a language model, but only to identify the streets. Coordinates always come from city street data. See `sources/geocodes/llm_location_repairs.jsonl`.
3. **2024+:** the city address geocoder (`city_address_geocoder`).
   - Points outside Chicago are rejected, which affects 77 rows in 2024.
   - Rows from the 2024 Q4 report that were not in the earlier Q3 batch are not geocoded yet.

A multi-location project is placed at its **first** part that passes the ward check. Use the geojson's geometry for anything finer.

### Ward check

Every point must fall inside its own ward, allowing about 400 m for boundary streets and alley corners. The ward is drawn from the map that applied that year:
- the map in force;
- in a remap year (2015, 2023), also the outgoing map;
- in the three years before a remap, also the incoming map. The 2015 map was adopted in 2012, and many 2013–14 project points fall in their ward's new boundaries.

`ward_map_fit` records which map matched. 1,127 points fail the check and are discarded (`rejected_outside_ward`). Most are 2024+ alley locations, where the city address geocoder misplaces four-street alley descriptions, and some are older local geocodes. These rows still count in every total; they just aren't placed on the map.

## What wards actually paid (item cost tables)

These tables come from `scripts/build_item_costs.py`.

**What a line-item cost is.** It's the amount OBM posts against a ward's menu allotment for one project. For most items that is CDOT's estimate when the project is approved, not an audited final cost. The menu "price" (see `infrastructure_menu.csv`) is CDOT's average used for planning; each project is then estimated on its own length, conditions and add-ons. That is why one item type spans a wide range.

**Item types.**
- Item names are normalized (parenthetical codes dropped, case and spacing folded) and matched to 30 types by ordered rules.
- `menu_item_types.csv` lists every name and its type; unmatched names stay unclassified (about 2% of line items).
- Change orders count under their item. The very smallest amounts are usually partial charges or adjustments, not whole projects.

**Per block.**
- Street-segment locations from 2012 on usually print address numbers ("FROM … (1600 N) TO … (1900 N)").
- Chicago's grid runs 800 numbers per mile, about 8 blocks per mile, so blocks ≈ address span ÷ 100, summed over a project's segments. Segments shorter than half a block are skipped.
- This is an estimate: some blocks are shorter or longer than 1/8 mile.
- It applies only to resurfacing, sidewalks, curb & gutter and lighting.

**Statistics.**
- Quartiles are shown only when a type has at least 5 line items in a year.
- The ward table covers the last three complete years.
- "Cheapest" and "most expensive" examples come from that window when it has enough items, otherwise from all years.

## Ward tables

- `ward_year_category.csv` holds `cost`, `projects` and `share_pct` (that category's share of the ward-year's menu spending).
- `ward_year.csv` holds the total, the approximate allotment and `pct_of_allotment`.
  - The allotment is a program-level approximation.
  - Rollover and top-ups can push a ward above 100%.

## Known issues

- **Ward 33, 2019:** our re-extraction totals $1.32M; the upstream CSV's $827k is what ships here. Not yet resolved.
- **Older extraction differs from upstream post-processing.** Validated on 2019: citywide within +0.81%, and 36 of 50 wards within 1%. The differences are upstream de-duplication of multi-location rows and cost cleanup, not extraction errors.
- **Prices change over time.** Costs are nominal dollars. Unit costs rise over time (see `infrastructure_menu.csv` and the observed-cost tables), so a constant allotment buys less each year.
- **Ward boundaries move between eras.** Comparing a ward across a remap compares different territory. Use `ward_map`.

## Validation (`scripts/validate.py`)

On every release, CI checks:
- schema and value ranges
- all 50 wards present in every complete year
- citywide totals within the program's range
- shares summing to 100
- ward totals matching line items

It also re-checks **findings others have cited**. Example: the 2023 sidewalk share of 4.1% (Ward 50) vs 24.6% (Ward 40), cited by City That Works. A release that changes a cited figure must say why in CHANGELOG.md.
