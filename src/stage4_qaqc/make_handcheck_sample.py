"""
Step 4b - Draw a random sample of extracted rows for the hand-check (accuracy).

Input : outputs/stage3/<paper>/tables_long.csv and methods_long.csv
Output: qaqc/hand_check.csv  - a person fills the *_ok columns by comparing with the PDF

Sample: per paper 5 table rows + 5 Methods rows (30 rows), random with a fixed
seed, so the same sample comes out every time (reproducible, not hand-picked).
Empty cells (dash = not measured in the paper) are not sampled.

Run: python src/stage4_qaqc/make_handcheck_sample.py
"""
import sys
from pathlib import Path

import pandas as pd

PAPERS = ["Pandey_2012", "Ghosh_2017", "Sarkar_2011"]
ROWS_PER_SOURCE = 5    # per paper: 5 from tables + 5 from Methods (30 rows in total)
SEED = 42              # fixed -> same sample every run
OUT = Path("qaqc/hand_check.csv")

# Columns the person fills in: Y = correct, N = wrong, NA = not applicable
TO_FILL = ["value_ok", "unit_ok", "treatment_ok", "depth_year_ok",
           "correct_value_if_wrong", "comment"]


def main():
    global PAPERS
    if len(sys.argv) > 1:              # paper names given by the pipeline
        PAPERS = sys.argv[1:]
    if OUT.exists():
        print(f"STOP: {OUT} already exists - it may hold your hand-check answers.")
        print("Delete or rename it first if you really want a new sample.")
        return

    picks = []
    for paper in PAPERS:
        for kind in ["tables", "methods"]:
            file = Path("outputs/stage3") / paper / f"{kind}_long.csv"
            df = pd.read_csv(file, dtype=str, keep_default_na=False)
            df["from"] = kind
            df["file_line"] = [f"{paper}/{file.name} line {i + 2}" for i in range(len(df))]
            df = df[df["value"] != ""]                            # skip empty cells
            n = min(ROWS_PER_SOURCE, len(df))
            picks.append(df.sample(n=n, random_state=SEED))

    s = pd.concat(picks, ignore_index=True).fillna("")
    # what the AI quoted from the paper: table cell or Methods sentence
    s["ai_quote"] = s["value_text"].where(s["from"] == "tables", s["evidence"])
    s.insert(0, "id", range(1, len(s) + 1))

    cols = ["id", "paper_name", "from", "Source", "treatment", "crop", "depth_cm", "year",
            "variable", "value", "unit", "ai_quote", "file_line"]
    s = s[cols]
    for c in TO_FILL:
        s[c] = ""

    s.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"Saved {len(s)} rows to {OUT}")
    print(s.groupby(["paper_name", "from"]).size().to_string())


if __name__ == "__main__":
    main()
