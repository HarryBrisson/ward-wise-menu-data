# Chicago Aldermanic Menu spending — open data

Every project Chicago's alders funded through the **Aldermanic Menu program** (about $1.5M per ward per year, roughly $70M citywide), **2005 to 2026 Q1**, as one clean, geocoded, citable table.

These are the data behind the menu-money pages on [wardwise.org/menu](https://www.wardwise.org/menu).

## Files (`data/`)

| File | What it is |
|---|---|
| `menu_line_items.csv` / `.parquet` | One row per project line item: ward, year, item, location, cost, category, lat/lng, source PDF |
| `ward_year_category.csv` | Spending and share of spending per ward × year × category. Most citations quote this table. |
| `ward_year.csv` | Totals per ward × year, plus the approximate allotment and the share spent |
| `menu_projects.geojson` | Geocoded line items. Uses line or polygon geometry where the city geocoder returned it, points otherwise. |
| `infrastructure_menu.csv` | The menu's unit prices, with a source for every row (see `infrastructure_menu_SOURCES.md`) |
| `release_summary.json` | Row counts, citywide totals and geocode coverage per year |

Column definitions, sources and known limitations are in [METHODOLOGY.md](METHODOLOGY.md).

## How to cite

Please cite the **release** you used, so others can reproduce your numbers:

> Ward Wise. *Chicago Aldermanic Menu spending, 2005–2026* (release vX.Y.Z). https://github.com/HarryBrisson/ward-wise-menu-data/releases/tag/vX.Y.Z. Source: City of Chicago Office of Budget and Management, Aldermanic Menu postings.

If you quote a specific ward-year figure, linking the matching Ward Wise page also helps readers. For example, [wardwise.org/menu/compare?wards=40,50&year=2023](https://www.wardwise.org/menu/compare?wards=40,50&year=2023). Machine-readable citation metadata is in [CITATION.cff](CITATION.cff). Use GitHub's "Cite this repository" button.

Found an error? Open an issue with the ward, year and row `id`. Every row links to the city PDF it came from (`source_url`), so a discrepancy can be checked against the original.

## Reproduce

```bash
pip install -r requirements.txt
python scripts/build_release.py   # sources/ -> data/
python scripts/validate.py        # schema, totals, and previously cited findings
```

`sources/` holds every input: the upstream extraction, our 2024+ extraction, the geocodes (each with the method that produced it), and a manifest that maps each source PDF to its chicago.gov URL and sha256.

## Credits

- **Line-item extraction for 2005–2023:** Sean MacMullan and contributors, [ward-wise/data-analysis](https://github.com/ward-wise/data-analysis).
- **Earlier scraping of the OBM Capital Improvements Archive:** Jake Smith and John C. Ruf.
- **Original menu-spending visualizer:** Ward Wise Chicago, wardwisechicago.org.
- **2024+ extraction, geocoding backfill and this release:** Ward Wise (wardwise.org).

## License

Code is MIT. The data are public records published by the City of Chicago; our compilation is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please attribute "Ward Wise".
