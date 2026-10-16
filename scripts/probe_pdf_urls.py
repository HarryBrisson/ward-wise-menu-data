"""Resolve the official chicago.gov URL (and sha256) for each source menu PDF.

The OBM index pages block scripts, but the /content/dam/ asset files are not gated: a HEAD with a
browser User-Agent is enough. Each local PDF name is tried under the asset folders the city has used.
Writes sources/pdf_manifest.csv (file, menu_year, period, source_url, sha256, bytes, verified_at).

  python scripts/probe_pdf_urls.py --pdf-dir ../data-analysis/data/pdf
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import re
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"
DAM = "https://www.chicago.gov/content/dam/city/depts/obm"
# Files the city no longer serves at any known asset path: cite the public mirror instead, labeled as such.
MIRRORS = {
    "2023 Menu - 2-27-24.pdf":
        "https://raw.githubusercontent.com/ward-wise/data-analysis/main/data/pdf/2023%20Menu%20-%202-27-24.pdf",
}
FOLDERS = (
    "general/CIP/CIPDocs/AldermanicMenuPostings",
    "supp_info/CIP_Archive/Aldermanic Menu",
    "supp_info/CIP_Archive",
)


def head_ok(url: str) -> bool:
    try:
        with urlopen(Request(url, method="HEAD", headers={"User-Agent": UA}), timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def year_period(name: str) -> tuple[int | None, str]:
    year = re.search(r"(20\d\d)", name)
    quarter = re.findall(r"Q([1-4])", name)
    period = f"Q{max(quarter)}" if quarter else "annual"
    return (int(year.group(1)) if year else None), period


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", type=Path, default=ROOT.parent / "data-analysis" / "data" / "pdf")
    args = parser.parse_args()
    today = dt.date.today().isoformat()
    rows = []
    for pdf in sorted(args.pdf_dir.glob("*.pdf")):
        url = next((u for u in (f"{DAM}/{quote(f)}/{quote(pdf.name)}" for f in FOLDERS) if head_ok(u)), "")
        year, period = year_period(pdf.name)
        data = pdf.read_bytes()
        rows.append({"file": pdf.name, "menu_year": year, "period": period, "source_url": url,
                     "mirror_url": "" if url else MIRRORS.get(pdf.name, ""),
                     "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                     "verified_at": today if url else ""})
        print(("OK  " if url else "--  ") + pdf.name)
    out = ROOT / "sources" / "pdf_manifest.csv"
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out} ({sum(1 for r in rows if r['source_url'])}/{len(rows)} resolved)")


if __name__ == "__main__":
    main()
