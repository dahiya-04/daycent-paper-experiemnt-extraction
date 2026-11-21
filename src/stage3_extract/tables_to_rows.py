import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

BASE_URL = "https://api.goedelmachines.com/v1"
MODEL = "deepseek/deepseek-v4.1-flash"
TEMPERATURE = 0
PROMPT_FILE = Path("prompts/table_to_rows_v1.txt")

ALLOWED_CATEGORIES = {"site", "initial_soil", "end_soil", "crop_yield",
                      "tillage", "fertiliser", "irrigation"}
NEEDED_KEYS = ["treatment", "depth_cm", "variable", "value", "unit",
               "year", "category", "value_text"]


def ask_ai(client, prompt):
    """Send the prompt, return the AI answer as a Python dict."""
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)

def squash(text):
    """Remove spaces and commas, so '0.33 ± 0.02c' == '0.33±0.02c' and '3,983' == '3983'."""
    return re.sub(r"[\s,]", "", str(text))

def check_row(r, table_text):
    """Check one AI row against the real table text. Returns a list of problems."""
    missing = [k for k in NEEDED_KEYS if k not in r]
    if missing:
        return [f"missing keys {missing}"]

    problems = []
    if r["category"] not in ALLOWED_CATEGORIES:
        problems.append(f"unknown category '{r['category']}'")

    # 1. The cell the AI quotes must really be in the table (no invented values)
    if squash(r["value_text"]) not in squash(table_text):
        problems.append("value_text not found in table (AI may have invented it)")

    # 2. The value must be the first number inside the quoted cell (the mean, not the SE)
    try:
        value = float(str(r["value"]).replace(",", ""))
        first = re.search(r"\d[\d,]*(?:\.\d+)?", str(r["value_text"]))
        if first is None or float(first.group().replace(",", "")) != value:
            problems.append("value does not match the number in value_text")
    except ValueError:                                   # text value, e.g. "Sandy loam"
        if squash(r["value"]) not in squash(table_text):
            problems.append("text value not found in table")

    # 3. Depth must look like "0-15" (or be empty)
    if r["depth_cm"] and not re.fullmatch(r"\d+(\.\d+)?-\d+(\.\d+)?", str(r["depth_cm"])):
        problems.append(f"depth_cm '{r['depth_cm']}' is not like '0-15'")
    return problems


def main():
    paper = sys.argv[1]                                  # e.g. Pandey_2012
    folder = Path("outputs/stage3") / paper
    files = sorted((folder / "tables_text").glob("*.txt"))
    template = PROMPT_FILE.read_text(encoding="utf-8")

    load_dotenv()
    client = OpenAI(base_url=BASE_URL, api_key=os.environ["GOEDEL_API_KEY"])

    all_rows = []
    for file in files:
        text = file.read_text(encoding="utf-8")
        first_line, table_text = text.split("\n", 1)     # "# Pandey_2012 | Table 1 | page 3 | area [...]"
        _, label, page, _ = [p.strip() for p in first_line.lstrip("# ").split("|")]
        source = f"p{page.split()[1]}, {label}"          # e.g. "p3, Table 1"

        print(f"{label:<9}", end=" ", flush=True)
        try:
            rows = ask_ai(client, template.replace("{table_text}", table_text)).get("rows", [])
        except Exception as e:                           # API down, bad JSON, answer cut off ...
            print(f"ERROR: {e}")
            all_rows.append({"paper_name": paper, "Source": source,
                             "Check": f"NEEDS HUMAN REVIEW: error: {e}"})
            continue

        bad = 0
        for r in rows:
            problems = check_row(r, table_text)
            bad += bool(problems)
            all_rows.append({
                "paper_name": paper,
                "Site_name": "",                         # filled later from Methods text (step 3.3)
                "treatment": r.get("treatment"),
                "depth_cm": r.get("depth_cm"),
                "variable": r.get("variable"),
                "value": r.get("value"),
                "unit": r.get("unit"),
                "Source": source,
                "year": r.get("year"),
                "category": r.get("category"),
                "value_text": r.get("value_text"),
                "Check": "OK" if not problems else "NEEDS HUMAN REVIEW: " + "; ".join(problems),
            })
        print(f"rows {len(rows):<4} needs review {bad}")

    df = pd.DataFrame(all_rows)
    df["Model"] = MODEL
    df["Temperature"] = TEMPERATURE
    df["Prompt file"] = PROMPT_FILE.as_posix()
    df["Run date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    out = folder / "tables_long.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {out}")
    print(f"Total rows: {len(df)}   Needs human review: {int((df['Check'] != 'OK').sum())}")


if __name__ == "__main__":
    main()