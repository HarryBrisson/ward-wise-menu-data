"""What wards actually paid, per menu item type: counts, spread, by year, by ward, extremes.

Reads data/menu_line_items.csv and writes:
  data/menu_item_types.csv        item name (normalized) -> item type, so the grouping is auditable
  data/menu_item_costs_year.csv   per type x year: n, min, p10, p25, median, p75, p90, max (per project)
                                  + the same quartiles per block where the block count is derivable
  data/menu_item_costs_ward.csv   per type x ward over the last three complete years: n, median, total
  data/menu_item_costs.json       all of the above + the cheapest / most expensive examples, for the site

Per-block costs: from 2012 most street-segment locations print address numbers, e.g.
"ON N CAMPBELL AVE FROM W NORTH AV (1600 N) TO W CORTLAND ST (1900 N)". Chicago's grid runs
800 numbers to the mile, roughly 100 per block, so blocks ~= |to - from| / 100 (summed over a
project's segments). Segments shorter than half a block are skipped as too noisy to divide by.

  python scripts/build_item_costs.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MIN_BLOCKS = 0.5
MIN_N = 5          # fewer line items than this in a year -> no quartiles for that year
WARD_YEARS = 3     # ward comparison window: the last N complete years

# (type id, label, regex over the normalized item name, unit when per-block applies). Order matters:
# first match wins, so specific patterns sit above general ones. Slugs match infrastructure_menu.csv
# where the price list has the same item.
TYPES = [
    ("street_speed_hump", "Street speed humps", r"^(STREET SPEED HUMP|RESURFACING STREET SPEED)", None),
    ("alley_speed_hump", "Alley speed humps", r"^ALLEY SPEED HUMP", None),
    ("street_resurfacing", "Street resurfacing", r"^STREET RESURFAC|^RESIDENTIAL STREET RESURFAC|^ARTERIAL RESURFAC", "block"),
    ("alley_resurfacing", "Alley resurfacing", r"^ALLEY RESURFAC", None),
    ("concrete_alley_apron", "Alley aprons", r"^ALLEY APRON", None),
    ("green_alley", "Concrete & green alleys", r"^(CONCRETE ALLEY|GREEN ALLEY)", None),
    ("sidewalk_replacement", "Sidewalks", r"^SIDEWALK", "block"),
    ("curb_gutter", "Curb & gutter", r"^CURB", "block"),
    ("street_lighting", "Street lighting", r"^STREET LIGHT(ING)?( RESIDENTIAL| PIGGY BACK| ARTERIAL|$)|^STREET LIGHTING|^RESIDENTIAL STREET LIGHT", "block"),
    ("street_light_upgrade", "Street light upgrades", r"^STREET LIGHT UPGRADE", None),
    ("pole_painting", "Pole painting", r"POLE PAINTING", None),
    ("floodlight", "Floodlights", r"^FLOODLIGHT", None),
    ("arterial_bump_out", "Arterial bump-outs", r"^ARTERIAL STREET BUMP", None),
    ("residential_bump_outs", "Street bump-outs", r"BUMP ?OUT", None),
    ("traffic_circle", "Traffic circles", r"TRAFFIC CIRCLE", None),
    ("in_road_stop_signs", "In-road pedestrian stop signs", r"^IN-ROAD", None),
    ("pedestrian_refuge_island", "Pedestrian refuge islands", r"^PEDESTRIAN REFUGE", None),
    ("bike_lane", "Bike lanes", r"BIKE LANE|BIKEWAY|SHARED LANE", None),
    ("pavement_markings", "Pavement markings", r"^PAVEMENT MARKING", None),
    ("bollards", "Bollards", r"^BOLLARD", None),
    ("speed_indicator_signs", "Speed indicator signs", r"^SPEED INDICATOR", None),
    ("diagonal_parking", "Diagonal parking", r"^DIAGONAL PARKING", None),
    ("cul_de_sac", "Cul-de-sacs", r"CUL-DE-SAC", None),
    ("traffic_signals", "Traffic signals & arrows", r"^TRAFFIC SIGNAL|^LEFT-TURN ARROW|COUNTDOWN SIGNAL|^LED TRAFFIC SIGNAL", None),
    ("viaducts", "Viaduct improvements", r"^VIADUCT", None),
    ("guardrails", "Guardrails", r"^GUARDRAIL", None),
    ("cameras", "Police (POD) cameras", r"CAMERA", None),
    ("park_district", "Park District projects", r"^CHICAGO PARK DISTRICT", None),
    ("schools", "School projects", r"^SCHOOL", None),
    ("misc_cdot", "Miscellaneous CDOT", r"^MISCELLANEOUS[- ]?CDOT", None),
]
RANGE = re.compile(r"FROM .*?\((\d+) ([NSEW])\)\s*TO .*?\((\d+) ([NSEW])\)")


def normalize(item: str) -> str:
    text = re.sub(r"\s*\(.*?\)", "", str(item or "")).upper()
    return re.sub(r"\s+", " ", text).strip()


def classify(name: str) -> str | None:
    return next((t for t, _, pattern, _ in TYPES if re.search(pattern, name)), None)


def blocks(location: str) -> float | None:
    total, found = 0.0, False
    for m in RANGE.finditer(str(location or "")):
        a, da, b, db = int(m[1]), m[2], int(m[3]), m[4]
        if da == db:
            span = abs(a - b)
        elif {da, db} in ({"N", "S"}, {"E", "W"}):
            span = a + b  # a segment crossing the 0 baseline (Madison / State)
        else:
            continue  # endpoints on different axes (e.g. 10700 S to 1600 W): not a straight run
        if span / 100 >= MIN_BLOCKS:
            total += span / 100
            found = True
    return round(total, 2) if found else None


def quart(s: pd.Series, prefix: str = "") -> dict:
    q = s.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    return {f"{prefix}min": s.min(), f"{prefix}p10": q[0.1], f"{prefix}p25": q[0.25], f"{prefix}median": q[0.5],
            f"{prefix}p75": q[0.75], f"{prefix}p90": q[0.9], f"{prefix}max": s.max()}


def example(row) -> dict:
    return {"id": row.id, "ward": int(row.ward), "year": int(row.year), "item": row.item, "location": row.location,
            "cost": round(float(row.cost), 2), "blocks": None if pd.isna(row.blocks) else float(row.blocks),
            "source_url": row.source_url if isinstance(row.source_url, str) else None}


def main() -> None:
    items = pd.read_csv(DATA / "menu_line_items.csv", low_memory=False)
    items = items[(items["cost"] > 0) & (items["ward"] != 99)].copy()
    items["name"] = items["item"].map(normalize)
    items["type"] = items["name"].map(classify)
    items["blocks"] = items["location"].map(blocks)

    names = (items.groupby(["name", "type"], dropna=False).size().reset_index(name="line_items")
             .sort_values("line_items", ascending=False))
    names.to_csv(DATA / "menu_item_types.csv", index=False)

    typed = items[items["type"].notna()].copy()
    complete_years = sorted(typed.loc[~typed["is_partial_year"], "year"].unique())
    ward_window = complete_years[-WARD_YEARS:]

    year_rows, ward_rows, out_types = [], [], []
    for type_id, label, pattern, unit in TYPES:
        t = typed[typed["type"] == type_id]
        if t.empty:
            continue
        per_block_ok = unit == "block"
        for year, g in t.groupby("year"):
            row = {"type": type_id, "year": int(year), "n": len(g), "wards": g["ward"].nunique(),
                   "total": round(g["cost"].sum(), 2), "partial_year": bool(g["is_partial_year"].any())}
            if len(g) >= MIN_N:
                row.update({k: round(v, 2) for k, v in quart(g["cost"]).items()})
            if per_block_ok:
                pb = (g["cost"] / g["blocks"])[g["blocks"].notna()]
                row["n_per_block"] = len(pb)
                if len(pb) >= MIN_N:
                    row.update({k: round(v, 2) for k, v in quart(pb, "block_").items()})
            year_rows.append(row)
        w = t[t["year"].isin(ward_window)]
        for ward, g in w.groupby("ward"):
            r = {"type": type_id, "ward": int(ward), "years": f"{ward_window[0]}-{ward_window[-1]}", "n": len(g),
                 "median": round(g["cost"].median(), 2), "total": round(g["cost"].sum(), 2)}
            if per_block_ok:
                pb = (g["cost"] / g["blocks"])[g["blocks"].notna()]
                r["n_per_block"] = len(pb)
                r["block_median"] = round(pb.median(), 2) if len(pb) else None
            ward_rows.append(r)

        recent = t[t["year"].isin(ward_window)]
        pool = recent if len(recent) >= MIN_N else t
        cheapest = pool.nsmallest(3, "cost")
        priciest = pool.nlargest(3, "cost")
        block_ex = {}
        if per_block_ok:
            # Absolute per-block extremes are dominated by errors in the posted address ranges (a
            # FROM/TO pair that doesn't match the street) and by partial charges, so the per-block
            # examples are the projects nearest the 5th and 95th percentile: the honest low and high end.
            withb = pool[pool["blocks"].notna()].assign(pb=lambda d: d["cost"] / d["blocks"])
            if len(withb) >= MIN_N:
                def near(q):
                    target = withb["pb"].quantile(q)
                    return withb.iloc[(withb["pb"] - target).abs().argsort()[:3]].sort_values("pb")
                block_ex = {"low_per_block": [dict(example(r), per_block=round(r.pb, 2)) for r in near(0.05).itertuples()],
                            "high_per_block": [dict(example(r), per_block=round(r.pb, 2)) for r in near(0.95).itertuples()]}
        out_types.append({
            "type": type_id, "label": label, "unit": unit, "n": len(t), "years": [int(t["year"].min()), int(t["year"].max())],
            "total": round(t["cost"].sum(), 2), "names": t["name"].value_counts().head(8).to_dict(),
            "n_per_block": int(t["blocks"].notna().sum()) if per_block_ok else 0,
            "examples_window": f"{ward_window[0]}-{ward_window[-1]}" if pool is recent else "all years",
            "cheapest": [example(r) for r in cheapest.itertuples()],
            "priciest": [example(r) for r in priciest.itertuples()],
            **block_ex,
        })

    years_df = pd.DataFrame(year_rows)
    wards_df = pd.DataFrame(ward_rows)
    years_df.to_csv(DATA / "menu_item_costs_year.csv", index=False)
    wards_df.to_csv(DATA / "menu_item_costs_ward.csv", index=False)

    def records(df, type_id):
        sub = df[df["type"] == type_id].drop(columns="type")
        return json.loads(sub.to_json(orient="records"))

    for entry in out_types:
        entry["by_year"] = records(years_df, entry["type"])
        entry["by_ward"] = records(wards_df, entry["type"])
    unclassified = items[items["type"].isna()]
    payload = {
        "method": {
            "blocks": "address-number span / 100 (Chicago grid: ~800 numbers per mile, ~8 blocks per mile); "
                      f"segments under {MIN_BLOCKS} block skipped",
            "ward_window": [int(ward_window[0]), int(ward_window[-1])],
            "min_n_for_quartiles": MIN_N,
            "classified_share": round(len(typed) / len(items), 3),
            "unclassified_line_items": int(len(unclassified)),
        },
        "types": out_types,
    }
    (DATA / "menu_item_costs.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"{len(out_types)} item types; {len(typed)}/{len(items)} line items classified "
          f"({payload['method']['classified_share']:.1%}); ward window {ward_window[0]}-{ward_window[-1]}")


if __name__ == "__main__":
    main()
