"""Release checks: schema, value ranges, internal consistency, and known published findings.

  python scripts/validate.py        (exit 1 on any failure)
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LINE_ITEM_COLUMNS = [
    "id", "ward", "year", "period", "is_partial_year", "item", "description", "location", "cost",
    "category", "category_raw", "active_transport", "lat", "lng", "geocode_status", "geocode_method",
    "ward_map", "source_pdf", "source_url", "provenance",
]
# Findings others have published from this data; a release that stops reproducing them needs a
# CHANGELOG entry explaining why. (ward, year, category, expected share %, tolerance)
CITED_FINDINGS = [
    # City That Works, "The city dug up the street…" (2026), footnote 2: sidewalk share on either
    # side of Granville Ave in 2023 — 4% (Ward 50) vs 24% (Ward 40).
    (50, 2023, "Sidewalk Repair", 4.1, 0.5),
    (40, 2023, "Sidewalk Repair", 24.6, 0.5),
]

failures: list[str] = []


def check(ok: bool, message: str) -> None:
    if not ok:
        failures.append(message)


def main() -> None:
    items = pd.read_csv(DATA / "menu_line_items.csv", low_memory=False)
    check(list(items.columns) == LINE_ITEM_COLUMNS, f"line-item columns differ: {list(items.columns)}")
    check(items["id"].is_unique, "line-item ids are not unique")
    check(items["ward"].isin(list(range(1, 51)) + [99]).all(), "ward outside 1-50 (99 = unassigned)")
    check((items["cost"] >= 0).all(), "negative cost")
    check(items["year"].between(2005, 2100).all(), "year out of range")
    check(items["category"].notna().all(), "missing category")
    located = items["geocode_status"] == "geocoded"
    check(items.loc[located, "lat"].between(41.6, 42.1).all()
          and items.loc[located, "lng"].between(-87.95, -87.5).all(), "geocode outside Chicago bbox")
    check(located.mean() >= 0.95, f"geocode coverage fell to {located.mean():.1%}")
    check((items.loc[items["year"] >= 2012, "source_url"].fillna("") != "").mean() >= 0.95,
          "2012+ rows missing source_url")

    for year, rows in items.groupby("year"):
        partial = rows["is_partial_year"].any()
        wards = rows.loc[rows["ward"] != 99, "ward"].nunique()
        check(partial or wards == 50, f"{year}: only {wards} wards in a complete year")
        if not partial:
            total = rows["cost"].sum()
            check(40e6 <= total <= 90e6, f"{year}: citywide total ${total:,.0f} outside the program's range")

    shares = pd.read_csv(DATA / "ward_year_category.csv")
    ward_year = pd.read_csv(DATA / "ward_year.csv")
    spent = shares.groupby(["ward", "year"])["cost"].sum() > 0
    sums = shares.groupby(["ward", "year"])["share_pct"].sum()[spent]
    check(sums.between(99.5, 100.5).all(), "category shares do not sum to 100 for some ward-year")
    merged = ward_year.set_index(["ward", "year"])["total_cost"]
    recomputed = items[items["ward"] != 99].groupby(["ward", "year"])["cost"].sum().round(2)
    check(((merged - recomputed).abs() < 1).all(), "ward_year totals disagree with line items")

    lookup = shares.set_index(["ward", "year", "category"])["share_pct"]
    for ward, year, category, expected, tol in CITED_FINDINGS:
        got = lookup.get((ward, year, category))
        check(got is not None and abs(got - expected) <= tol,
              f"cited finding moved: ward {ward} {year} {category} = {got} (expected ~{expected})")

    if (DATA / "infrastructure_menu.csv").exists():
        menu = list(csv.DictReader((DATA / "infrastructure_menu.csv").open()))
        allowed = {"primary_document", "ward_wise_2023_unverified", "derived"}
        for row in menu:
            check(row.get("verification") in allowed, f"price row {row.get('item_slug')}: bad verification")
            check(bool(row.get("source_url")) or row.get("verification") != "primary_document",
                  f"price row {row.get('item_slug')}: primary_document without source_url")

    summary = json.loads((DATA / "release_summary.json").read_text())
    check(summary["rows"] == len(items), "release_summary row count stale")

    if failures:
        print("FAIL\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"OK  {len(items)} line items, {len(shares)} ward-year-category rows")


if __name__ == "__main__":
    main()
