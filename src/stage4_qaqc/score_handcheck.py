"""
Step 4c - Score the hand-check: how many extracted values are correct.

Input : qaqc/hand_check.csv   (Y = correct, N = wrong, NA = not applicable)
Output: outputs/stage4/handcheck_scores.csv

For each field:  accuracy = Y / (Y + N)      (NA rows are not counted)
95 % range (Wilson interval): how sure we can be with a small sample.

Run: python src/stage4_qaqc/score_handcheck.py
"""
import math
from pathlib import Path

import pandas as pd

IN_FILE = Path("qaqc/hand_check.csv")
OUT_FILE = Path("outputs/stage4/handcheck_scores.csv")
FIELDS = ["value_ok", "unit_ok", "treatment_ok", "depth_year_ok", "row_ok"]


def wilson(correct, total, z=1.96):
    """95 % range for a percentage from a small sample (Wilson interval)."""
    if total == 0:
        return None, None
    p = correct / total
    middle = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0, middle - half), min(1, middle + half)


def score(rows, group):
    """One result line per field for this group of rows."""
    lines = []
    for field in FIELDS:
        correct = (rows[field] == "Y").sum()
        wrong = (rows[field] == "N").sum()
        total = correct + wrong
        low, high = wilson(correct, total)
        lines.append({
            "group": group,
            "field": field,
            "correct": correct,
            "wrong": wrong,
            "not_applicable": (rows[field] == "NA").sum(),
            "accuracy_%": round(100 * correct / total, 1) if total else "",
            "95%_low": round(100 * low, 1) if total else "",
            "95%_high": round(100 * high, 1) if total else "",
        })
    return lines


def main():
    s = pd.read_csv(IN_FILE, dtype=str, keep_default_na=False)

    # A row is fully correct when none of its 4 fields is N
    ok_cols = ["value_ok", "unit_ok", "treatment_ok", "depth_year_ok"]
    empty = (s[ok_cols] == "").any(axis=1).sum()
    if empty:
        print(f"WARNING: {empty} rows are not filled in yet - fill them first")
    s["row_ok"] = (s[ok_cols] == "N").any(axis=1).map({True: "N", False: "Y"})

    out = pd.DataFrame(score(s, "all 30 sampled rows"))
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

    print(f"Rows checked: {len(s)}\n")
    print(out.to_string(index=False))
    print(f"\nSaved: {OUT_FILE}")


if __name__ == "__main__":
    main()
