# Infrastructure Menu unit prices: sources and confidence

`infrastructure_menu.csv` lists the **unit prices CDOT charges a ward's Menu balance** for each menu item ("Average Cost $X per block"), one row per item, year and source. It is built by `infrastructure_menu_build.py` (run `python data/infrastructure_menu_build.py` from the repo root). Prices are kept in the **native unit of the source**. `display_unit_cost` converts only half-mile bike items to per block (÷4, see below), and `conversion_note` says so on every converted row.

## Bottom line

- **No price list published by the city has been found.** CDOT gives each alder a "Menu packet" with prices every year, but the city does not post it. OBM's CIP archive has only the *spending* postings (what each ward bought, with estimated cost per line item), not the price sheet.
- What we have instead, in order of strength:

| Year(s) | Evidence | `verification` | Confidence |
|---|---|---|---|
| 2023 (22 items) | CDOT "2023 Aldermanic Menu Packet", obtained by Ward Wise Chicago through a FOIA request | `foia_response` | **High.** CDOT's own document, released under FOIA. The original PDF isn't posted publicly; we hold its text and a Word conversion. |
| 2005–2026 (6 items) | Fixed prices recovered from the city's own ward-detail spending PDFs (most common line-item cost) | `derived` | **High** for speed humps, floodlights and light upgrades. Medium for traffic circles 2005–08 and arterial bump-outs 2020. |
| 2015 (8 items) | CDOT's 2015 menu prices, reproduced in the 2017 OIG audit, Appendix C | `official_secondary` | **High.** It's an official city document quoting CDOT. |
| ~2024, ~2025 (24 rows) | Price tables posted by the 35th and 40th ward offices for participatory budgeting | `ward_office_secondary` | **Medium.** Not CDOT documents. Figures are rounded, the year is approximate, and some may be stale. |

There are no `primary_document` rows yet. That label is reserved for a price list published by CDOT or OBM, or one we hold the original file for (see "Next steps"). `foia_response` ranks just below it: an official CDOT document, released under FOIA, whose original file isn't public.

## Sources in detail

### 1. 2023 Aldermanic Menu Packet (22 items): `foia_response`
- **Provenance.** Ward Wise Chicago obtained CDOT's 2023 Aldermanic Menu packet through a FOIA request. That is where the old site's price list came from.
- **How the copy reached this repo.** The old wardwisechicago.org list (`ward-wise-front-end` `data/menu_items_info.csv`, `public/menuItemsInfo.json`) cites no source. Its sibling repo `ward-wise/alderman-spending-data-viz` has `alderman_spending/assets/menu_items_information.docx`, committed 2023-08-06 by "Jonathan" ("Putting assets in/framing for menu items and FAQs"). The docx metadata title is **"2023 Aldermanic Menu Packet.pdf"**. It's an OCR/Word conversion of the CDOT packet: page headers read "2023 Aldermanic Menu Program", and the text is CDOT's own wording, such as "need to clear CDOT's utility review… scheduled for 2023".
- **Check.** All 22 prices and units on the old site match the packet text exactly (the build script asserts this). The packet line number for each price is in `source_page`.
- **Copies.** `sources/menu_price_docs/2023_Aldermanic_Menu_Packet_wordconversion_text.txt` holds the packet text; the .docx itself is at the upstream URL above. `ward-wise-front-end_menu_items_info_2023.csv` is the old site's list.
- **Per-block standardization.** The packet prices bike items per **half-mile**: Bike Lane/Marked Shared Lane $40,000, Buffered $60,000, Protected $250,000, Neighborhood Greenway $75,000. Ward Wise Chicago standardized these to per block ($10,000 and $15,000 for bike lanes) using 8 blocks ≈ 1 mile, so items compare apples to apples. We keep the half-mile price in `unit_cost` and put the ÷4 figure in `display_unit_cost` with a `conversion_note`.
- **One small disagreement.** The packet says alley speed humps cost $1,400 per block, but 2023 spending line items cluster at **$1,450**. Either the packet was printed before a mid-year price change, or the OCR misread it.

### 2. 2015 CDOT prices via the OIG audit (8 items): `official_secondary`
- City of Chicago OIG, *CDOT Aldermanic Menu Program Audit* (File #14-0430, 2017-04-19), Appendix C "Life cycle estimates", report page 30 of 42 (PDF page 33), sourced to "2015 Menu prices … provided by CDOT". URL: https://igchicago.org/wp-content/uploads/2017/04/CDOT-Aldermanic-Menu-Program-Audit.pdf. Copies of the PDF and a rendered image of the table are in `sources/menu_price_docs/`.
- **Prices:** street resurfacing $42,000/block; street speed humps $3,700; sidewalk $75,000/block; curb & gutter $80,000/block; residential lighting $73,200/block; alley resurfacing $31,500/alley; alley speed humps $1,400; concrete alley apron $10,000. OIG also lists separate **ADA ramp supplements** of $57,000 per street block and $36,000 per alley, which are not included in the menu price.
- **Cross-check.** The $3,700 speed-hump and $1,400 alley-hump prices match the 2015 line-item modes exactly.

### 3. Prices recovered from spending line items: `derived`
- **Method.** Some menu items have a fixed price, so the same exact dollar amount appears over and over in the city's ward-detail postings. For each item and year we take the most common line-item cost from `data/menu_line_items.csv`, where every row cites its chicago.gov PDF in `source_url`. We keep it only when the evidence is strong:
  - **Speed humps.** At least 10 line items, and at least 85% of them must be whole multiples of half the mode (a single hump is half the block price). The block price is the median when the median is twice the mode, or the mode when it is also the median, covers at least 35% of items, and its double is rare (under 15%).
  - **Other items.** At least 5 line items, and the mode must cover at least 50% of them.
- **Full table.** Every item-year is listed in `infrastructure_menu_line_item_modes.csv` with n, mode, share, half-multiple share, double share, median and source URL, including the ones the rules rejected.
- **Speed humps per block (2 humps):** $5,000 (2005) → $3,300 (2007) → $3,500 (2008–09) → **$3,700 (2011–18)** → **$4,700 (2019–22)** → **$4,880 (2023–25)** → $5,300 (2026, Q1 only). The 2015 value matches OIG and the 2023 value matches the packet.
- **Alley speed humps per block:** about $1,000 (2006–09) → **$1,400 (2012–21)** → **$1,450 (2023–25)**.
- **Floodlight per fixture:** $600 (2013–15) → $900 (2018–19) → **$950 (2021–24, matches packet)** → $1,150 (2025).
- **Street light upgrade:** $500 for every year from 2017 to 2026. The unit isn't stated, probably per fixture. This item isn't in the 2023 packet text.
- **Traffic circle:** $10,000 (2005–06), $12,000 (2007), $15,000 (2008). Arterial bump-out: $50,000 (2020).
- **Caveats.**
  - The 2005–2011 line items come from an older scrape whose source PDFs are no longer online, so their units are unconfirmed.
  - 2026 covers Q1 only.
  - This method recovers **only fixed-price items**. Estimate-based items (resurfacing, sidewalks, lighting, bump-outs, bike lanes) vary by project, so no mode survives. Comparing observed costs to the menu prices for those items is a separate analysis.

### 4. Ward-office reprints: `ward_office_secondary`
- **40th Ward.** Cost table on "2025 People's Budget Proposals Open!" (published 2025-05-21, https://40thward.org/2025/05/2024-peoples-budget-proposals-open/). The same table is on the ward's People's Budget page, last modified 2026-09-30. We assign `menu_year` 2025. The table shows increases over 2023:
  - sidewalk and curb & gutter $115K (2023: $105K)
  - arterial bump-outs $60K (2023: $50K)
  - residential bump-outs $16K per pair (2023: $15K)
  - cul-de-sac $50K (2023: $40K)
  - diagonal parking $90K per block (2023: $85K per project)
  - "alley reconstruction" $300K (2023 green alley: $280K)
  - residential lighting $280K per block (2023: $165K with piggy back, so possibly a different option)

  Resurfacing is still $54,450, which may be stale. Traffic signals are given only as a range, $50–150K, so `unit_cost` is blank.
- **35th Ward.** PB page with the ballot open through 2024-12-20 (https://www.aldermancarlosrosa.org/pb). We assign `menu_year` 2024. Its figures are rounded and mostly match 2023, except sidewalk $115K. It prices bump-outs at "$16,000 per corner", which conflicts with the 40th Ward's "per pair".
- Local HTML copies of both pages were taken on 2026-10-16. They are not republished here because they are third-party web pages; cite the live URLs above.

## Search trail (what was checked)
- **OBM CIP archive assets.** A Wayback CDX listing of every archived `chicago.gov/content/dam/city/depts/obm/supp_info/CIP_Archive/*`, `…/general/CIP/*` and `…/depts/cdot/*` URL with "menu" or "alder" in the path found only spending postings and quarterly reports (2012–2026), with **no price packet**. The quarterly reports ("Annual Allocation and Project Overview", 2023 Q4 to 2026 Q1) also have no price table: their "How to Read" pages explain the line items, not the prices.
- **OIG.** Found the 2017 audit and its 2015 price table. OIG's later follow-up advisory was not examined for prices.
- **Ward sites.**
  - 32nd Ward (`ward32.org`): project lists with no prices.
  - 1st Ward: confirms the 2023 bump-out prices and gives "up to" amounts per PB project.
  - 48th Ward 2024 project list: $4,880 and $9,760 speed humps, consistent with the derived price.
  - 35th and 40th Wards: used above.
- **News and other sites.**
  - The Daily Line: an old "$38,000 first 5 blocks" resurfacing figure. Not used: undated and not from CDOT.
  - City That Works (Substack): says resurfacing a block cost "28% more in 2025 than in 2015" with no dollar figure. A reader comment there claims "$36,000 per pair" for bump-outs in 2026, unsourced and not used.
- **Not found:** packet PDFs for any year on chicago.gov, DocumentCloud, MuckRock or Scribd. Search engines don't index the packet's wording ("will be deducted from the Ward Menu balance").

## Next steps to reach `primary_document`
1. **FOIA CDOT for current packets** (a 2026 request is planned), ideally every year available from 2012 to 2026. Ward offices receive the packet each year, and several already republish parts of it.
2. When a packet arrives, add the original PDF under `sources/menu_price_docs/`, add a transcription block to the build script, and mark those rows `primary_document`.
