"""Build data/infrastructure_menu.csv: the Aldermanic Menu's unit prices, one sourced row per item-year.

Three kinds of evidence (see infrastructure_menu_SOURCES.md):
  * transcribed  - prices printed in a document (2023 CDOT menu packet, 2017 OIG audit, ward-office pages)
  * derived      - the modal line-item cost of a fixed-price item in the city's own ward-detail PDFs,
                   computed from data/menu_line_items.csv (every row of which cites its PDF)

Run from the repo root:  python data/infrastructure_menu_build.py
Writes data/infrastructure_menu.csv and data/infrastructure_menu_line_item_modes.csv.
"""
import collections
import csv
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINE_ITEMS = ROOT / "data" / "menu_line_items.csv"
OUT = ROOT / "data" / "infrastructure_menu.csv"
MODES_OUT = ROOT / "data" / "infrastructure_menu_line_item_modes.csv"
FRONTEND_2023 = ROOT / "sources" / "menu_price_docs" / "ward-wise-front-end_menu_items_info_2023.csv"

COLUMNS = ["item_slug", "item", "menu_year", "unit_cost", "unit", "display_unit_cost", "display_unit",
           "conversion_note", "description", "notes", "vision_zero", "source_document", "source_url",
           "source_page", "retrieved_at", "verification"]

HALF_MILE_NOTE = ("Native unit is a half-mile. Ward Wise Chicago standardized half-mile prices to per block "
                  "(8 blocks ≈ 1 mile, so 4 per half-mile) so items compare apples to apples.")

# --- 2023: CDOT "2023 Aldermanic Menu Packet" --------------------------------------------------------
# slug, title in packet, price, unit as printed, packet text line (sources/menu_price_docs/..._text.txt)
PACKET_2023 = [
    ("street_resurfacing", "Residential Street Resurfacing", 54450, "block", 3),
    ("alley_resurfacing", "Residential Alley Resurfacing", 39425, "alley", 10),
    ("green_alley", "Green Alley Program", 280000, "alley (typical 600 feet)", 17),
    ("alley_speed_hump", "Alley Speed Hump Program", 1400, "block (includes 2 alley speed humps)", 26),
    ("concrete_alley_apron", "Concrete Alley Apron", 17000, "location", 35),
    ("street_speed_hump", "Street Speed Hump Program", 4880, "block (includes 2 street speed humps)", 43),
    ("sidewalk_replacement", "Sidewalk Replacement Program", 105000, "block", 51),
    ("curb_gutter", "Curb & Gutter Replacement Program", 105000, "block", 58),
    ("diagonal_parking", "Diagonal Parking", 85000, "project", 67),
    ("cul_de_sac", "Residential Street Cul-de-Sac", 40000, "project", 77),
    ("neighborhood_greenway", "Neighborhood Greenways", 75000, "half-mile", 86),
    ("traffic_circle", "Residential Street Traffic Circle", 20000, "project", 97),
    ("residential_bump_outs", "Residential Street Bump-Outs", 15000, "project (2 bump-outs)", 107),
    ("arterial_bump_out", "Arterial Street Bump Outs", 50000, "corner", 115),
    ("pedestrian_refuge_island", "Pedestrian Refuge Island", 75000, "location", 123),
    ("protected_bike_lane", "Protected Bike Lane", 250000, "half-mile", 132),
    ("buffered_bike_lane", "Buffered Bike Lane", 60000, "half-mile", 141),
    ("bike_lane", "Bike Lane/Marked Shared Lane", 40000, "half-mile", 150),
    ("light_pole_painting", "Street Light Pole Painting Program", 300, "pole", 158),
    ("signal_pole_painting", "Traffic Signal Intersection Pole Painting Program", 3500, "intersection", 164),
    ("street_lighting", "Residential Street Lighting Program with Piggy Back", 165000, "block", 170),
    ("floodlight", "Floodlight Installation", 950, "fixture", 189),
]
# Old-site item names (ward-wise-front-end data/menu_items_info.csv) -> our slugs, for descriptions.
FRONTEND_NAMES = {
    "Residential Street Resurfacing": "street_resurfacing", "Residential Alley Resurfacing": "alley_resurfacing",
    "Green Alley Program": "green_alley", "Alley Speed Hump Program": "alley_speed_hump",
    "Concrete Alley Apron": "concrete_alley_apron", "Street Speed Hump Program": "street_speed_hump",
    "Sidewalk Replacement Program": "sidewalk_replacement", "Curb & Gutter Replacement Program": "curb_gutter",
    "Diagonal Parking": "diagonal_parking", "Residential Street Cul-de-Sac": "cul_de_sac",
    "Neighborhood Greenways": "neighborhood_greenway", "Residential Street Traffic Circle": "traffic_circle",
    "Residential Street Bump-Outs": "residential_bump_outs", "Arterial Street Bump Outs": "arterial_bump_out",
    "Pedestrian Refuge Island": "pedestrian_refuge_island", "Protected Bike Lane": "protected_bike_lane",
    "Buffered Bike Lane": "buffered_bike_lane", "Bike Lane/Marked Shared Lane": "bike_lane",
    "Street Light Pole Painting Program": "light_pole_painting",
    "Traffic Signal Intersection Pole Painting Program": "signal_pole_painting",
    "Residential Street Lighting Program with Piggy Back": "street_lighting",
    "Floodlight Installation": "floodlight",
}
PACKET_DOC = ("CDOT, '2023 Aldermanic Menu Packet', obtained by Ward Wise Chicago through a FOIA request; "
              "Word conversion committed to ward-wise/alderman-spending-data-viz on 2023-08-06; extracted text in "
              "sources/menu_price_docs/2023_Aldermanic_Menu_Packet_wordconversion_text.txt")
PACKET_URL = ("https://github.com/ward-wise/alderman-spending-data-viz/blob/main/"
              "alderman_spending/assets/menu_items_information.docx")

# --- 2015: CDOT prices as reproduced in the OIG audit (Appendix C, page 30 of 42 / PDF page 33) -------
OIG_URL = "https://igchicago.org/wp-content/uploads/2017/04/CDOT-Aldermanic-Menu-Program-Audit.pdf"
OIG_DOC = ("City of Chicago Office of Inspector General, 'Chicago Department of Transportation Aldermanic Menu "
           "Program Audit' (OIG File #14-0430, April 19, 2017), Appendix C table, 'Source: 2015 Menu prices ... "
           "provided by CDOT'")
OIG_2015 = [
    ("street_resurfacing", "Res. Street Resurfacing", 42000, "block",
     "OIG adds a separate $57,000/block ADA supplement (ramps) on top of the $42,000 menu price."),
    ("street_speed_hump", "Res. Street Speed Humps", 3700, "block",
     "OIG table has no unit label; $3,700 equals the 2015 modal line item and the 2023 packet's per-block unit "
     "(2 humps)."),
    ("sidewalk_replacement", "Sidewalk Replacement", 75000, "block", ""),
    ("curb_gutter", "Curb & Gutter Replacement", 80000, "block", ""),
    ("street_lighting", "Res. Street Lighting Program", 73200, "block",
     "Lower than the 2015 modal line items (~$156,000), which are typically 2-block lighting circuits."),
    ("alley_resurfacing", "Res. Alley Resurfacing", 31500, "alley",
     "OIG adds a separate $36,000/alley ADA supplement on top of the $31,500 menu price."),
    ("alley_speed_hump", "Alley Speed Humps", 1400, "block", "Unit inferred as per alley block (2 humps)."),
    ("concrete_alley_apron", "Concrete Alley Apron", 10000, "apron",
     "OIG assumes 2 aprons per alley block ($20,000/block)."),
]

# --- Ward-office reprints (secondary; not CDOT documents) ------------------------------------------
W40_URL = "https://40thward.org/2025/05/2024-peoples-budget-proposals-open/"
W40_DOC = ("40th Ward office, '2025 People's Budget Proposals Open!' cost table (published 2025-05-21, "
           "updated 2025-05-23). "
           "The same table is on https://40thward.org/city-services/participatory-budgeting/ (modified 2026-09-30).")
W40 = [
    ("street_resurfacing", "Residential Street Resurfacing", 54450, "block", "Same as the 2023 packet."),
    ("green_alley", "Alley Reconstruction", 300000, "block",
     "Ward calls it 'Alley Reconstruction'; mapped to Green Alley (2023 packet: $280,000 per alley)."),
    ("sidewalk_replacement", "Sidewalk Replacement", 115000, "block", ""),
    ("curb_gutter", "Curb and Gutter Replacement", 115000, "block", ""),
    ("diagonal_parking", "Diagonal Parking", 90000, "block", "2023 packet priced this per project, not per block."),
    ("cul_de_sac", "Residential cul-de-sac", 50000, "project", ""),
    ("neighborhood_greenway", "Neighborhood Bike Greenway", 75000, "half-mile", ""),
    ("traffic_circle", "Residential Traffic Circle", 20000, "project", ""),
    ("residential_bump_outs", "Residential Bump-outs", 16000, "pair", ""),
    ("arterial_bump_out", "Arterial Bump-outs", 60000, "corner", ""),
    ("pedestrian_refuge_island", "Pedestrian Refuge Island", 75000, "island", ""),
    ("protected_bike_lane", "Protected Bike Lanes", 250000, "half-mile", ""),
    ("buffered_bike_lane", "Buffered Bike Lanes", 60000, "half-mile", ""),
    ("street_lighting", "Residential Street Lighting", 280000, "block",
     "Much higher than the 2023 packet's $165,000/block 'with piggy back'; may be a different lighting option."),
    ("traffic_signal", "Traffic Signal (e.g., left turn arrow)", None, "signal",
     "Ward gives a range, $50,000-$150,000 per signal; no single price."),
]
W35_URL = "https://www.aldermancarlosrosa.org/pb"
W35_DOC = "35th Ward office, Participatory Budgeting page (ballot open through 2024-12-20)"
W35 = [
    ("alley_resurfacing", "Asphalt alley resurfacing", 40000, "alley", ""),
    ("street_resurfacing", "Street resurfacing", 55000, "block", "Rounded; 2023 packet is $54,450."),
    ("sidewalk_replacement", "Sidewalk repair", 115000, "block (one side)", ""),
    ("bike_lane", "Marked shared lane", 40000, "half-mile (per side)", ""),
    ("buffered_bike_lane", "Buffered bike lane", 60000, "half-mile (per side)", ""),
    ("pedestrian_refuge_island", "Pedestrian refuge island", 75000, "island", "'roughly'"),
    ("street_lighting", "Residential street lighting", 165000, "block", "'about'"),
    ("residential_bump_outs", "Bump-out", 16000, "corner",
     "Ward says per corner; the 40th Ward says $16K per pair and the 2023 packet $15,000 per 2 bump-outs."),
    ("traffic_circle", "Roundabout / traffic circle", 20000, "block", ""),
]

# --- Derived: modal line item cost in the city's ward-detail PDFs -------------------------------------
# slug -> (item, regex over normalized line-item names, unit, rule)
#   rule 'pair' : speed humps. Line items are 1 or 2 humps; the per-block (2-hump) price is the median when it is
#                 twice the mode, or the mode when it is also the median, covers >= 35% and its double is rare (<15%).
#   rule 'mode' : fixed-price items; keep the mode when it covers >= 50% of >= 5 line items.
DERIVED = {
    "street_speed_hump": ("Street Speed Hump Program", r"^STREET SPEED HUMP", "block (2 street speed humps)", "pair"),
    "alley_speed_hump": ("Alley Speed Hump Program", r"^ALLEY SPEED HUMP MENU$", "block (2 alley speed humps)", "pair"),
    "floodlight": ("Floodlight Installation", r"^FLOODLIGHT", "fixture", "mode"),
    "street_light_upgrade": ("Street Light Upgrade", r"^STREET LIGHT UPGRADE", "line item (unit not stated)", "mode"),
    "traffic_circle": ("Residential Street Traffic Circle", r"^STREET TRAFFIC CIRCLES? MENU$", "project", "mode"),
    "arterial_bump_out": ("Arterial Street Bump Outs", r"^ARTERIAL STREET BUMP OUTS", "corner", "mode"),
}
UPSTREAM_URL = ("https://github.com/ward-wise/data-analysis/blob/main/data/2005-2023%20menu%20spending.csv")


def norm(item):
    item = re.sub(r"\s*\(\d{4}\)", "", item or "")
    return re.sub(r"\s+", " ", item).strip().upper()


def line_item_modes():
    groups = collections.defaultdict(list)
    urls = collections.defaultdict(set)
    for r in csv.DictReader(open(LINE_ITEMS, newline="")):
        try:
            cost = round(float(r["cost"]), 2)
        except (TypeError, ValueError):
            continue
        if cost <= 0:
            continue
        for slug, (_, pat, _, _) in DERIVED.items():
            if re.search(pat, norm(r["item"])):
                groups[(slug, int(r["year"]))].append(cost)
                urls[int(r["year"])].add(r.get("source_url") or "")
    rows = []
    for (slug, year), costs in sorted(groups.items()):
        counts = collections.Counter(costs)
        mode, mode_n = counts.most_common(1)[0]
        rows.append({"item_slug": slug, "menu_year": year, "n_line_items": len(costs), "mode": mode,
                     "mode_share": round(mode_n / len(costs), 3),
                     "half_multiple_share": round(sum(abs(c / mode * 2 - round(c / mode * 2)) < 1e-6
                                                      for c in costs) / len(costs), 3),
                     "double_share": round(counts[2 * mode] / len(costs), 3),
                     "median": statistics.median(costs),
                     "source_url": sorted(u for u in urls[year] if u)[:1][0] if any(urls[year]) else UPSTREAM_URL})
    return rows


def pick_price(m, rule):
    if rule == "pair":
        if m["n_line_items"] < 10 or m["half_multiple_share"] < 0.85:
            return None
        if m["median"] == 2 * m["mode"]:
            return m["median"]
        # Mode is the per-block price unless single-hump items (half of it) are common, or doubles of it are
        # common enough that the mode itself may be a single hump.
        if m["median"] == m["mode"] and m["mode_share"] >= 0.35 and m["double_share"] < 0.15:
            return m["mode"]
        return None
    if m["n_line_items"] >= 5 and m["mode_share"] >= 0.5:
        return m["mode"]
    return None


def display(slug, cost, unit):
    if cost is not None and unit.startswith("half-mile"):
        return round(cost / 4), "block" + unit[len("half-mile"):], HALF_MILE_NOTE
    return cost, unit, ""


def row(slug, item, year, cost, unit, description, notes, vz, doc, url, page, retrieved, verification):
    d_cost, d_unit, conv = display(slug, cost, unit)
    return {"item_slug": slug, "item": item, "menu_year": year, "unit_cost": "" if cost is None else cost,
            "unit": unit, "display_unit_cost": "" if d_cost is None else d_cost, "display_unit": d_unit,
            "conversion_note": conv, "description": description, "notes": notes, "vision_zero": vz,
            "source_document": doc, "source_url": url, "source_page": page, "retrieved_at": retrieved,
            "verification": verification}


def main():
    fe = {FRONTEND_NAMES[r["Menu_Item"]]: r for r in csv.DictReader(open(FRONTEND_2023, newline=""))}
    out = []
    for slug, title, cost, unit, line in PACKET_2023:
        f = fe[slug]
        assert float(f["Average_Unit_Cost"]) == cost, slug  # old site agrees with the packet text
        notes = "; ".join(json.loads(f["Notes"]))
        notes = ("Packet price matches the old wardwisechicago.org list. " + notes).strip()
        out.append(row(slug, title, 2023, cost, unit, f["Description"], notes,
                       f["Vision_Zero_Project"].lower(), PACKET_DOC, PACKET_URL,
                       f"packet text line {line} (2023_Aldermanic_Menu_Packet_wordconversion_text.txt)",
                       "2026-10-16", "foia_response"))
    for slug, title, cost, unit, note in OIG_2015:
        out.append(row(slug, title, 2015, cost, unit, "", note, "", OIG_DOC, OIG_URL,
                       "Appendix C, report page 30 of 42 (PDF page 33)", "2026-10-16", "official_secondary"))
    for slug, title, cost, unit, note in W40:
        out.append(row(slug, title, 2025, cost, unit, "",
                       ("menu_year approximate: the year the ward office published the table. " + note).strip(),
                       "", W40_DOC, W40_URL, "'Cost' table", "2026-10-16", "ward_office_secondary"))
    for slug, title, cost, unit, note in W35:
        out.append(row(slug, title, 2024, cost, unit, "",
                       ("menu_year approximate: 2024 ballot cycle; ward says costs are estimates. " + note).strip(),
                       "", W35_DOC, W35_URL, "PB category list", "2026-10-16", "ward_office_secondary"))

    modes = line_item_modes()
    with open(MODES_OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(modes[0]))
        w.writeheader()
        w.writerows(modes)
    for m in modes:
        item, _, unit, rule = DERIVED[m["item_slug"]]
        price = pick_price(m, rule)
        if price is None:
            continue
        price = int(price) if float(price).is_integer() else price
        notes = (f"Modal line-item cost: {m['n_line_items']} line items, {m['mode_share']:.0%} exactly "
                 f"${m['mode']:,.0f}, {m['half_multiple_share']:.0%} a half-multiple of it, median ${m['median']:,.0f}.")
        if m["menu_year"] == 2026:
            notes += " 2026 is Q1 only."
        if m["menu_year"] <= 2011:
            notes += " 2005-2011 line items come from an older scrape (Jake Smith & John C. Ruf); unit unconfirmed."
        out.append(row(m["item_slug"], item, m["menu_year"], price, unit, "", notes, "",
                       "Ward-detail line items (City of Chicago OBM/CDOT Aldermanic Menu postings) via "
                       "data/menu_line_items.csv; full table in data/infrastructure_menu_line_item_modes.csv",
                       m["source_url"], f"all '{item}' line items for {m['menu_year']}", "2026-10-16", "derived"))

    out.sort(key=lambda r: (r["item_slug"], r["menu_year"], r["verification"]))
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
