"""Build the release tables in data/ from the vendored inputs in sources/.

Inputs (all under sources/, so the build is reproducible from this repo alone):
  upstream/2005-2023 menu spending.csv     Sean MacMullan's extraction (ward-wise/data-analysis)
  extracted/menu_2024_2026_processed.csv    our extraction of the 2024+ quarterly reports
  geocodes/*                                 per-(year, location) geocodes with method provenance
  pdf_manifest.csv                           source PDF -> official chicago.gov URL + sha256

Outputs (data/):
  menu_line_items.csv / .parquet   one row per project line item
  ward_year_category.csv           totals + shares per ward x year x category
  ward_year.csv                    totals + approximate allotment per ward x year
  menu_projects.geojson            geocoded line items (original line/polygon geometry where known)
  release_summary.json             row counts, citywide totals per year, geocode coverage

  python scripts/build_release.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "sources"
OUT = ROOT / "data"

CATEGORIES = (
    "Street Resurfacing", "Sidewalk Repair", "Alleys", "Lighting", "Pedestrian Infrastructure",
    "Street Redesign", "Bicycle Infrastructure", "Traffic Signals", "Viaducts", "Parks", "Schools",
    "Cameras", "Beautification", "Misc. CDOT", "Misc.",
)
ACTIVE_TRANSPORT = {"Bicycle Infrastructure", "Pedestrian Infrastructure", "Street Redesign"}
# The annual posting that carries each year's 2012-2023 line items in the upstream extraction.
ANNUAL_PDF = {
    2012: "2012Menu.pdf", 2013: "2013Menu.pdf", 2014: "2014Menu.pdf", 2015: "2015Menu.pdf",
    2016: "2016Menu.pdf", 2017: "2017OBMMenu50WardDetailsRpt3Dec2018.pdf",
    2018: "2018OBMrpt_MenuWarddetailsprojects2DEC2019.pdf", 2019: "2019 Menu Posting - 22-10-02.pdf",
    2020: "2020 Menu Posting - 22-10-02.pdf", 2021: "2021 Menu Posting - 22-10-02.pdf",
    2022: "2022 Menu - 2-9-23.pdf", 2023: "2023 Menu - 2-27-24.pdf",
}
LATEST_YEAR_IS_PARTIAL = True  # the newest year in the 2024+ extraction is a year-to-date quarter


def allotment(year: int) -> int:
    """Approximate per-ward annual menu allotment (raised to $1.5M in 2021; ~$1.32M in the 2010s)."""
    return 1_500_000 if year >= 2021 else 1_320_000 if year >= 2012 else 1_300_000


def ward_map(year: int) -> int:
    """Ward boundary map in force for a menu year (new maps seated May 2015 and May 2023)."""
    return 2023 if year >= 2023 else 2015 if year >= 2015 else 2003


def _key(year, location) -> tuple[int, str]:
    """Normalized join key. Multi-location rows use ':' in the CSV but '; ' in the geojson."""
    text = str(location or "").replace(":", "; ")
    return int(year), " ".join(text.split()).upper()


def _in_chicago(hit: dict | None) -> bool:
    """Reject NaN and far-off geocodes (the 2024+ address cache maps some alley quads ~120 km west)."""
    if not hit or hit.get("lat") is None:
        return False
    lat, lng = hit["lat"], hit["lng"]
    return lat == lat and lng == lng and 41.6 <= lat <= 42.1 and -87.95 <= lng <= -87.5


def _parts(location) -> list[str]:
    return [p for p in _key(0, location)[1].split("; ") if p]


def load_geocodes() -> tuple[dict, dict]:
    """(by_year_location, by_location_2024plus) -> {lat, lng, method, geometry}."""
    by_key: dict[tuple[int, str], dict] = {}
    geo = SRC / "geocodes"

    for feature in json.loads((geo / "menu_2019_2022.geojson").read_text())["features"]:
        props, geom = feature.get("properties") or {}, feature.get("geometry")
        if not geom:
            continue
        try:
            point = shape(geom).representative_point()
        except Exception:  # degenerate one-vertex lines in the upstream file
            continue
        by_key.setdefault(_key(props["year"], props.get("location")), {
            "lat": round(point.y, 6), "lng": round(point.x, 6), "method": "upstream_geocoder",
            "geometry": geom})

    for name, method_field in (("menu_2019_2023_fill_log.jsonl", "how"),
                               ("menu_2005_2018_geocode_log.jsonl", "method")):
        for line in (geo / name).read_text().splitlines():
            row = json.loads(line)
            if "year" not in row:
                continue
            key = _key(row["year"], row.get("location"))
            if row.get("lat") is None:
                by_key.setdefault(key, {"method": None})
                continue
            if by_key.get(key, {}).get("lat") is None:
                by_key[key] = {"lat": row["lat"], "lng": row["lng"],
                               "method": row.get(method_field) or "local_geocoder", "geometry": None}

    by_location: dict[str, dict] = {}
    for line in (geo / "menu_2024_2026_geocodes.jsonl").read_text().splitlines():
        row = json.loads(line)
        if not row.get("wkt"):
            continue
        geom = shapely_wkt.loads(row["wkt"])
        point = geom.representative_point()
        by_location[_key(0, row["loc"])[1]] = {
            "lat": round(point.y, 6), "lng": round(point.x, 6), "method": "city_address_geocoder",
            "geometry": mapping(geom)}
    return by_key, by_location


def load_items() -> pd.DataFrame:
    manifest = {r["file"]: r for r in csv.DictReader((SRC / "pdf_manifest.csv").open())}

    def cite(pdf: str | None) -> tuple[str, str]:
        row = manifest.get(pdf or "", {})
        return pdf or "", row.get("source_url") or row.get("mirror_url") or ""

    old = pd.read_csv(SRC / "upstream" / "2005-2023 menu spending.csv")
    old["period"] = "annual"
    old["source_pdf"] = old["year"].map(ANNUAL_PDF)
    old["provenance"] = "ward-wise/data-analysis extraction (Sean MacMullan; 2005-2011 scraped by Jake Smith & John C. Ruf)"

    new = pd.read_csv(SRC / "extracted" / "menu_2024_2026_processed.csv")
    # Quarterly reports are cumulative year-to-date: keep only each year's latest report.
    order = new["period"].str.slice(1).astype(int)
    latest = new.assign(_q=order).groupby("year")["_q"].transform("max")
    new = new[order == latest].copy()
    new["description"] = ""
    new["provenance"] = "Ward Wise extraction of OBM quarterly menu reports"

    items = pd.concat([old, new], ignore_index=True, sort=False)
    items["cost"] = pd.to_numeric(items["cost"], errors="coerce")
    # Ward 99 = items the source posts without a ward (a handful per year): kept, excluded from ward tables.
    items = items[items["cost"].notna() & (items["ward"].between(1, 50) | (items["ward"] == 99))].copy()
    items["category_raw"] = items["category"]
    items["category"] = items["category"].replace({"Police Cameras": "Cameras"})
    items["ward"] = items["ward"].astype(int)
    items["year"] = items["year"].astype(int)
    items["description"] = items["description"].fillna("")
    items["location"] = items["location"].fillna("")
    cited = items["source_pdf"].map(cite)
    items["source_pdf"] = [c[0] for c in cited]
    items["source_url"] = [c[1] for c in cited]
    newest = items["year"].max()
    items["is_partial_year"] = (items["year"] == newest) & LATEST_YEAR_IS_PARTIAL & (items["period"] != "Q4")
    items["ward_map"] = items["year"].map(ward_map)
    items["active_transport"] = items["category"].isin(ACTIVE_TRANSPORT)
    return items


def stable_ids(items: pd.DataFrame) -> list[str]:
    """Hash of the identifying fields + an ordinal for exact duplicates (the PDFs repeat some rows)."""
    seen: Counter = Counter()
    ids = []
    for row in items[["ward", "year", "item", "location", "cost"]].itertuples(index=False):
        base = f"{row.ward}|{row.year}|{row.item}|{row.location}|{row.cost:.2f}"
        seen[base] += 1
        ids.append(hashlib.sha1(f"{base}|{seen[base]}".encode()).hexdigest()[:12])
    return ids


def main() -> None:
    OUT.mkdir(exist_ok=True)
    items = load_items().sort_values(["year", "ward", "category", "item", "location"], kind="stable")
    items.insert(0, "id", stable_ids(items))

    by_key, by_location = load_geocodes()
    lats, lngs, statuses, methods, geometries = [], [], [], [], []
    for row in items.itertuples(index=False):
        key = _key(row.year, row.location)
        lookup = (lambda loc: by_location.get(loc)) if row.year >= 2024 else (lambda loc: by_key.get((key[0], loc)))
        hit = lookup(key[1])
        if not _in_chicago(hit):  # multi-location row: first locatable part
            hit = next((h for h in map(lookup, _parts(row.location)) if _in_chicago(h)), hit)
        if _in_chicago(hit):
            lats.append(hit["lat"]); lngs.append(hit["lng"])
            statuses.append("geocoded"); methods.append(hit["method"]); geometries.append(hit.get("geometry"))
        else:
            lats.append(None); lngs.append(None); geometries.append(None); methods.append("")
            statuses.append("rejected_out_of_bounds" if hit and hit.get("lat") is not None
                            else "unlocatable" if hit else "not_geocoded")
    items["lat"], items["lng"] = lats, lngs
    items["geocode_status"], items["geocode_method"] = statuses, methods

    columns = ["id", "ward", "year", "period", "is_partial_year", "item", "description", "location",
               "cost", "category", "category_raw", "active_transport", "lat", "lng", "geocode_status", "geocode_method",
               "ward_map", "source_pdf", "source_url", "provenance"]
    items = items[columns]
    items.to_csv(OUT / "menu_line_items.csv", index=False)
    items.to_parquet(OUT / "menu_line_items.parquet", index=False)

    # Ward x year x category: the table most citations quote.
    warded = items[items["ward"] != 99]
    totals = warded.groupby(["ward", "year", "category"], as_index=False).agg(
        cost=("cost", "sum"), projects=("id", "count"))
    ward_totals = warded.groupby(["ward", "year"], as_index=False).agg(
        total_cost=("cost", "sum"), projects=("id", "count"), is_partial_year=("is_partial_year", "max"))
    totals = totals.merge(ward_totals[["ward", "year", "total_cost"]], on=["ward", "year"])
    totals["share_pct"] = (100 * totals["cost"] / totals["total_cost"]).round(2)
    totals["cost"] = totals["cost"].round(2)
    totals.drop(columns="total_cost").to_csv(OUT / "ward_year_category.csv", index=False)

    ward_totals["allotment_approx"] = ward_totals["year"].map(allotment)
    ward_totals["pct_of_allotment"] = (100 * ward_totals["total_cost"] / ward_totals["allotment_approx"]).round(1)
    ward_totals["total_cost"] = ward_totals["total_cost"].round(2)
    ward_totals["ward_map"] = ward_totals["year"].map(ward_map)
    ward_totals.to_csv(OUT / "ward_year.csv", index=False)

    features = []
    for row, geom in zip(items.itertuples(index=False), geometries):
        if row.lat is None or pd.isna(row.lat):
            continue
        features.append({"type": "Feature",
                         "geometry": geom or {"type": "Point", "coordinates": [row.lng, row.lat]},
                         "properties": {"id": row.id, "ward": row.ward, "year": row.year, "item": row.item,
                                        "location": row.location, "cost": round(row.cost, 2),
                                        "category": row.category}})
    (OUT / "menu_projects.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                                          separators=(",", ":")))

    by_year = items.groupby("year").agg(cost=("cost", "sum"), rows=("id", "count"),
                                        wards=("ward", lambda w: int(w[w != 99].nunique())), period=("period", "first"))
    geo = items.groupby("year")["geocode_status"].apply(lambda s: round(100 * (s == "geocoded").mean(), 1))
    summary = {
        "rows": int(len(items)),
        "years": [int(items["year"].min()), int(items["year"].max())],
        "geocoded_pct": round(100 * (items["geocode_status"] == "geocoded").mean(), 1),
        "by_year": {int(y): {"cost": round(float(r.cost), 2), "rows": int(r.rows), "wards": int(r.wards),
                             "period": r.period, "geocoded_pct": float(geo[y]),
                             "unassigned_ward_rows": int(((items["year"] == y) & (items["ward"] == 99)).sum())}
                    for y, r in by_year.iterrows()},
        "categories": sorted(items["category"].unique().tolist()),
    }
    (OUT / "release_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    unknown = set(summary["categories"]) - set(CATEGORIES)
    print(f"{summary['rows']} rows {summary['years']} geocoded {summary['geocoded_pct']}%"
          + (f" UNKNOWN CATEGORIES {unknown}" if unknown else ""))


if __name__ == "__main__":
    main()
