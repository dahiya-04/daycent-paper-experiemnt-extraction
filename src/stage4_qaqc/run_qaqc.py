"""
Step 4 - QAQC checks on the extracted data (code only, no AI).

Input : outputs/stage3/<paper>/tables_long.csv and methods_long.csv   (3 papers)
        qaqc/check_rules.csv                                          (range + unit rules)
Output: outputs/stage4/qaqc_log.csv       (one line per check: PASS / WARN / FAIL / INFO)
        outputs/stage4/qaqc_summary.csv   (number of PASS / WARN / FAIL / INFO per paper)

Checks:
  1. ai_extraction  - rows the step-3 code checks already flagged         -> WARN
  2. range          - value inside min-max of check_rules.csv             -> PASS / FAIL
     unit           - unit is the one expected in check_rules.csv          -> WARN
  3. unit_missing   - a number in a table with no unit                     -> WARN
  4. texture_sum    - sand + silt + clay = 95-105 %                        -> PASS / FAIL
  5. depth_order    - in "top-bottom" the top is smaller than the bottom   -> FAIL
  6. year_order     - experiment end year >= start year                    -> PASS / FAIL
  7. c_input_sum    - Ghosh Table 2: FYM + crop residue = total (+-0.5)    -> PASS / FAIL
  8. duplicate      - the same row twice                                   -> WARN
  9. rule_not_used  - a rule that matched no data (ready for future papers)-> INFO

Run: python src/stage4_qaqc/run_qaqc.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

PAPERS = ["Pandey_2012", "Ghosh_2017", "Sarkar_2011"]
RULES_FILE = Path("qaqc/check_rules.csv")
OUT_DIR = Path("outputs/stage4")

# Variables that have no unit on purpose (so "unit missing" is not a problem)
UNITLESS = {"pH", "Texture", "No of irrigation", "tillage_passes", "replicates",
            "experiment_start_year", "experiment_end_year"}
DEPTH = re.compile(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


# ---------------------------------------------------------------- loading
def load_data():
    """All 6 extraction files in one table. Every row remembers its file and line."""
    frames = []
    for paper in PAPERS:
        for kind in ["tables", "methods"]:
            file = Path("outputs/stage3") / paper / f"{kind}_long.csv"
            df = pd.read_csv(file, dtype=str, keep_default_na=False)   # empty cell -> ""
            df["from"] = kind
            df["file_line"] = [f"{paper}/{file.name} line {i + 2}" for i in range(len(df))]
            frames.append(df)
    # tables files have no "crop" column -> "" instead of empty (NaN)
    return pd.concat(frames, ignore_index=True).fillna("")


def load_rules():
    rules = pd.read_csv(RULES_FILE, comment="#", dtype=str, keep_default_na=False)
    rules["used"] = False
    return rules


# ---------------------------------------------------------------- helpers
def to_number(value, variable=""):
    """'3,983' -> 3983.0   '26°27'N' -> 26.45   'two' -> 2.0   'Sandy loam' -> None"""
    text = str(value).strip().replace(",", "")
    if text.lower() in NUMBER_WORDS:
        return float(NUMBER_WORDS[text.lower()])
    if variable in ("latitude", "longitude"):
        m = re.match(r"(\d+(?:\.\d+)?)\s*°\s*(?:(\d+(?:\.\d+)?)\s*['′’])?", text)
        if m:
            minutes = float(m.group(2)) / 60 if m.group(2) else 0
            return float(m.group(1)) + minutes
    try:
        return float(text)
    except ValueError:
        return None


def same_unit(a, b):
    return str(a).replace(" ", "").lower() == str(b).replace(" ", "").lower()


def entry(row, check, result, detail):
    """One line of the QAQC log, linked to the data row it is about."""
    return {"paper": row.get("paper_name", ""), "check": check, "result": result,
            "detail": detail, "from": row.get("from", ""), "file_line": row.get("file_line", ""),
            "Source": row.get("Source", ""), "treatment": row.get("treatment", ""),
            "depth_cm": row.get("depth_cm", ""), "variable": row.get("variable", ""),
            "value": row.get("value", ""), "unit": row.get("unit", "")}


def find_rule(rules, paper, variable):
    """Paper-specific rule first, then the universal (*) rule."""
    for p in (paper, "*"):
        hit = rules[(rules["paper"] == p) & (rules["variable"] == variable)]
        if len(hit):
            return hit.index[0]
    return None


# ---------------------------------------------------------------- row checks
def check_rule(row, rule):
    """Range + unit check of one row against one rule."""
    if row["value"] == "":
        return entry(row, "range", "INFO", "empty cell in paper (dash = not measured) - not checked")
    number = to_number(row["value"], row["variable"])
    if number is None:
        return entry(row, "range", "FAIL", f"value '{row['value']}' is not a number")

    problems = []
    expected = rule["expected_unit"]
    if expected != "*" and not same_unit(row["unit"], expected):
        problems.append(f"unit '{row['unit']}' but expected '{expected}'")

    low = float(rule["min"]) if rule["min"] != "" else None
    high = float(rule["max"]) if rule["max"] != "" else None
    if (low is not None and number < low) or (high is not None and number > high):
        detail = f"{number:g} outside {rule['min'] or '-inf'}-{rule['max'] or 'inf'} ({rule['why']})"
        return entry(row, "range", "FAIL", "; ".join([detail] + problems))
    if problems:
        return entry(row, "range", "WARN", "in range, but " + "; ".join(problems))
    return entry(row, "range", "PASS", f"{number:g} inside {rule['min'] or '-inf'}-{rule['max'] or 'inf'}")


def row_checks(data, rules):
    log = []
    for _, row in data.iterrows():
        # 1. flags from step 3 (AI extraction checks)
        if row["Check"] != "OK":
            log.append(entry(row, "ai_extraction", "WARN", row["Check"]))

        # 2. range + unit
        i = find_rule(rules, row["paper_name"], row["variable"])
        if i is not None:
            rules.at[i, "used"] = True
            log.append(check_rule(row, rules.loc[i]))

        # 5. depth order
        m = DEPTH.match(row["depth_cm"])
        if m and float(m.group(1)) >= float(m.group(2)):
            log.append(entry(row, "depth_order", "FAIL",
                             f"top {m.group(1)} is not smaller than bottom {m.group(2)}"))
    return log


# ---------------------------------------------------------------- cross-field checks
def unit_missing(data):
    """3. Numbers in a table with no unit - one log line per table + variable."""
    log = []
    d = data[(data["from"] == "tables") & (data["unit"] == "")
             & ~data["variable"].isin(UNITLESS)
             & data["value"].map(lambda v: to_number(v) is not None)]
    for (paper, source, variable), g in d.groupby(["paper_name", "Source", "variable"]):
        row = g.iloc[0].to_dict()
        row.update(treatment="", depth_cm="", value=f"{len(g)} values", unit="")
        log.append(entry(row, "unit_missing", "WARN",
                         f"{len(g)} numbers have no unit in the source table"))
    return log


def texture_sum(data):
    log = []
    tex = data[data["variable"].str.lower().isin(["sand", "silt", "clay"])].copy()
    tex["number"] = tex["value"].map(to_number)
    for keys, g in tex.groupby(["paper_name", "Source", "treatment", "depth_cm", "year"]):
        if len(g) != 3 or g["number"].isna().any():
            continue
        total = g["number"].sum()
        row = g.iloc[0].to_dict()
        row.update(variable="sand+silt+clay", value=f"{total:g}", unit="%")
        result = "PASS" if 95 <= total <= 105 else "FAIL"
        log.append(entry(row, "texture_sum", result,
                         " + ".join(f"{v:g}" for v in g["number"]) + f" = {total:g} (must be 95-105)"))
    return log


def year_order(data):
    log = []
    for paper in PAPERS:
        d = data[(data["paper_name"] == paper) & (data["from"] == "methods")]
        start = d.loc[d["variable"] == "experiment_start_year", "value"].map(to_number).dropna()
        end = d.loc[d["variable"] == "experiment_end_year", "value"].map(to_number).dropna()
        row = {"paper_name": paper, "from": "methods", "variable": "experiment years"}
        if start.empty or end.empty:
            log.append(entry(row, "year_order", "INFO", "start or end year not reported"))
        else:
            ok = end.min() >= start.max()
            log.append(entry(row, "year_order", "PASS" if ok else "FAIL",
                             f"start {start.max():g}, end {end.min():g}"))
    return log


def c_input_sum(data):
    """Ghosh Table 2: rows come in blocks FYM, Crop residue, Total (file order)."""
    log = []
    t2 = data[(data["paper_name"] == "Ghosh_2017") & (data["Source"] == "p4, Table 2")
              & data["variable"].isin(["FYM", "Crop residue", "Total"])]
    block = {}
    for _, row in t2.iterrows():
        block[row["variable"]] = to_number(row["value"])
        if row["variable"] == "Total":
            fym, res, total = block.get("FYM"), block.get("Crop residue"), block.get("Total")
            if None not in (fym, res, total):
                r = row.to_dict()
                r.update(variable="FYM + Crop residue vs Total")
                ok = abs(fym + res - total) <= 0.5
                log.append(entry(r, "c_input_sum", "PASS" if ok else "FAIL",
                                 f"{fym:g} + {res:g} = {fym + res:g}, table total {total:g}"))
            block = {}
    return log


def duplicates(data):
    keys = ["paper_name", "from", "Source", "treatment", "crop", "depth_cm",
            "variable", "value", "year"]
    dup = data[data.duplicated(subset=keys, keep=False) & (data["value"] != "")]
    return [entry(row, "duplicate", "WARN",
                  "same row appears more than once - usually the AI dropped the column that "
                  "tells the rows apart (e.g. crop, rotation, year)")
            for _, row in dup.iterrows()]


def unused_rules(rules):
    return [entry({"paper_name": r["paper"], "variable": r["variable"]}, "rule_not_used", "INFO",
                  "no data matched this rule (kept for future papers)")
            for _, r in rules[~rules["used"]].iterrows()]


# ---------------------------------------------------------------- main
def main():
    global PAPERS
    if len(sys.argv) > 1:              # paper names given by the pipeline
        PAPERS = sys.argv[1:]
    data = load_data()
    rules = load_rules()

    log = row_checks(data, rules)
    log += unit_missing(data) + texture_sum(data) + year_order(data) + c_input_sum(data)
    log += duplicates(data) + unused_rules(rules)

    df = pd.DataFrame(log)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "qaqc_log.csv", index=False, encoding="utf-8-sig")

    summary = pd.crosstab(df["paper"], df["result"])
    summary.to_csv(OUT_DIR / "qaqc_summary.csv", encoding="utf-8-sig")

    print(f"Data rows checked: {len(data)}   Log lines: {len(df)}\n")
    print(summary.to_string(), "\n")
    print("FAIL and WARN by check:")
    bad = df[df["result"].isin(["FAIL", "WARN"])]
    print(pd.crosstab(bad["check"], bad["result"]).to_string())
    print(f"\nSaved: {OUT_DIR / 'qaqc_log.csv'}")
    print(f"Saved: {OUT_DIR / 'qaqc_summary.csv'}")


if __name__ == "__main__":
    main()
