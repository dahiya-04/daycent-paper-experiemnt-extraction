"""
Step 5a - Combine all extracted data into ONE final CSV.

Input : outputs/stage3/<paper>/tables_long.csv and methods_long.csv
Output: outputs/final/all_data.csv

- Columns follow the assignment: paper_name, Site_name, treatment, depth_cm,
  variable, value, unit, Source  (+ crop, year, category, note, from)
- Site_name is filled from the Methods row "site_name" of each paper
- Empty cells (dash = not measured in the paper) are left out
- Values are NOT changed; QAQC results stay in outputs/stage4/qaqc_log.csv

Run: python src/stage5_output/build_final.py
"""
import sys
from pathlib import Path

import pandas as pd

PAPERS = ["Pandey_2012", "Ghosh_2017", "Sarkar_2011"]
OUT = Path("outputs/final/all_data.csv")
COLUMNS = ["paper_name", "Site_name", "treatment", "crop", "depth_cm", "variable",
           "value", "unit", "Source", "year", "category", "note", "from"]


def main():
    papers = sys.argv[1:] or PAPERS
    frames = []
    for paper in papers:
        for kind in ["tables", "methods"]:
            file = Path("outputs/stage3") / paper / f"{kind}_long.csv"
            df = pd.read_csv(file, dtype=str, keep_default_na=False)
            df["from"] = kind
            frames.append(df)
    data = pd.concat(frames, ignore_index=True).fillna("")

    # leave out empty cells (dash in the paper = not measured)
    empty = (data["value"] == "").sum()
    data = data[data["value"] != ""]

    # Site_name: copy the site_name value of each paper to all its rows
    sites = data[data["variable"] == "site_name"].groupby("paper_name")["value"].first()
    data["Site_name"] = data["paper_name"].map(sites).fillna("")

    data = data[COLUMNS].sort_values(["paper_name", "category", "variable"], kind="stable")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUT, index=False, encoding="utf-8-sig")

    print(f"Saved {len(data)} rows to {OUT}   (left out {empty} empty cells)\n")
    print(pd.crosstab(data["paper_name"], data["category"]).to_string())
    missing_site = sorted(set(papers) - set(sites.index))
    if missing_site:
        print("\nWARNING - no site_name found for:", missing_site)


if __name__ == "__main__":
    main()
