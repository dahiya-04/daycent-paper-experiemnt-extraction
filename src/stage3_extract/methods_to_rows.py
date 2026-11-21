"""
Step 3.3 - Read the Methods section and turn it into data rows with the AI.

Input : data/raw_pdfs/<paper>.pdf
Prompt: prompts/methods_to_rows_v2.txt
        (v1 kept for the record; v2 = one value per row, years, all treatment codes)
Output: outputs/stage3/<paper>/methods_text.txt   (the text sent to the AI, for hand-check)
        outputs/stage3/<paper>/methods_long.csv   (one row per value, assignment format)

Run: python src/stage3_extract/methods_to_rows.py Pandey_2012
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import pymupdf
from dotenv import load_dotenv
from openai import OpenAI

BASE_URL = "https://api.goedelmachines.com/v1"
MODEL = "deepseek/deepseek-v4.1-flash"
TEMPERATURE = 0
PROMPT_FILE = Path("prompts/methods_to_rows_v2.txt")

# A value that is really a LIST: number, then ", " or " and " or "&", then a number.
#   "0, 40, 60 and 120" -> list      "16th and 19th" -> list
#   "3,983" (no space)  -> not list  "0–15" (range)  -> not list
LIST_OF_VALUES = re.compile(r"\d(?:st|nd|rd|th)?\s*(?:,\s+|\s+and\s+|\s*&\s*)\d")

# Columns that make a row unique (used to remove exact duplicates)
DUPLICATE_KEYS = ["category", "variable", "value", "unit", "crop", "treatment",
                  "depth_cm", "year", "Source"]

# Methods starts at "Materials and Methods" / "Methods and Materials" (any case)
# and ends at "Results and Discussion" or a heading that is only "Results".
START = re.compile(r"Materials? and Methods|Methods and Materials", re.IGNORECASE)
END = re.compile(r"Results and Discussion|\n(\d\.?\s*)?Results\n", re.IGNORECASE)

VARIABLES = {
    "site": {"site_name", "latitude", "longitude", "elevation", "climate", "soil_type",
             "experiment_start_year", "experiment_end_year"},
    "treatment": {"treatment_definition"},
    "crop_yield": {"crop", "variety", "sowing_date", "transplanting_date", "harvest_date",
                   "seed_rate", "plant_spacing"},
    "tillage": {"tillage_implement", "tillage_timing", "tillage_depth", "tillage_passes"},
    "fertiliser": {"N_rate", "P_rate", "K_rate", "fertiliser_product", "fertiliser_timing",
                   "manure_type", "manure_rate", "residue_management"},
    "irrigation": {"irrigation_method", "irrigation_amount", "irrigation_timing",
                   "irrigation_number"},
    "end_soil": {"soil_sampling_depth", "soil_sampling_date", "SOC_method",
                 "bulk_density_method"},
}
NEEDED_KEYS = ["category", "variable", "value", "unit", "crop", "treatment",
               "depth_cm", "year", "page", "evidence", "note"]


def clean(text):
    """One line, standard letters. '◦' (wrong degree sign from the PDF font) -> '°'."""
    text = unicodedata.normalize("NFKC", text).replace("\u25e6", "°")
    return " ".join(text.split())

def get_methods_text(pdf_path):
    """All paragraphs of the paper with a page tag, then cut out the Methods part."""
    doc = pymupdf.open(pdf_path)
    paragraphs = []
    for page_no, page in enumerate(doc, start=1):
        for b in page.get_text("blocks"):
            if b[6] == 0:                                  # text blocks only
                paragraphs.append(f"[p{page_no}] {clean(b[4])}")
    full = "\n".join(paragraphs)

    start = START.search(full)
    if start is None:
        return None, "Methods heading not found"
    end = END.search(full, start.end())
    if end is None:
        return None, "Results heading not found"
    return full[start.start():end.start()], ""

def text_per_page(methods_text):
    """{page number: all text of that page} - used to check the AI's evidence."""
    pages = {}
    for line in methods_text.split("\n"):
        m = re.match(r"\[p(\d+)\] (.*)", line)
        if m:
            pages[int(m.group(1))] = pages.get(int(m.group(1)), "") + " " + m.group(2)
    return pages

def ask_ai(client, prompt):
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def squash(text):
    """Remove spaces, commas and hyphens, so small spacing differences don't matter."""
    return re.sub(r"[\s,\-–]", "", str(text)).lower()


def check_row(r, pages):
    """Check one AI row against the real Methods text. Returns a list of problems."""
    missing = [k for k in NEEDED_KEYS if k not in r]
    if missing:
        return [f"missing keys {missing}"]

    problems = []
    cat, var = r["category"], r["variable"]
    if cat not in VARIABLES:
        problems.append(f"unknown category '{cat}'")
    elif var not in VARIABLES[cat]:
        problems.append(f"unknown variable '{var}' for category '{cat}'")
    try:
        page_text = pages.get(int(r["page"]), "")
    except (TypeError, ValueError):
        page_text = ""
    if not page_text:
        problems.append(f"page '{r['page']}' is not in the Methods text")
    elif squash(r["evidence"]) not in squash(page_text):
        problems.append("evidence not found on that page (AI may have changed or invented it)")

    if squash(r["value"]) not in squash(r["evidence"]):
        problems.append("value is not inside the evidence")

    # 3. Depth must look like "0-15" (or be empty)
    if r["depth_cm"] and not re.fullmatch(r"\d+(\.\d+)?-\d+(\.\d+)?", str(r["depth_cm"])):
        problems.append(f"depth_cm '{r['depth_cm']}' is not like '0-15'")

    # 4. One value per row: a list like "0, 40, 60 and 120" must be split
    if LIST_OF_VALUES.search(str(r["value"])):
        problems.append("value is a list of several values (should be one row each)")
    return problems

def main():
    paper = sys.argv[1]                                     # e.g. Pandey_2012
    folder = Path("outputs/stage3") / paper
    folder.mkdir(parents=True, exist_ok=True)

    # --- Part 1: cut out the Methods text (no AI) ---
    methods_text, problem = get_methods_text(Path("data/raw_pdfs") / f"{paper}.pdf")
    if methods_text is None:
        print("STOP:", problem)
        return
    (folder / "methods_text.txt").write_text(methods_text, encoding="utf-8")
    pages = text_per_page(methods_text)
    print(f"Methods text: {len(methods_text)} characters, pages {sorted(pages)}")

    # --- Part 2: send it to the AI ---
    template = PROMPT_FILE.read_text(encoding="utf-8")
    load_dotenv()
    client = OpenAI(base_url=BASE_URL, api_key=os.environ["GOEDEL_API_KEY"])
    try:
        rows = ask_ai(client, template.replace("{methods_text}", methods_text)).get("rows", [])
    except Exception as e:                                  # API down, bad JSON, answer cut off ...
        print(f"ERROR: {e}")
        return

    # --- Part 3: check every row ---
    out_rows = []
    for r in rows:
        problems = check_row(r, pages)
        out_rows.append({
            "paper_name": paper,
            "Site_name": "",                                # filled when tables + methods are joined
            "treatment": r.get("treatment"),
            "crop": r.get("crop"),
            "depth_cm": r.get("depth_cm"),
            "variable": r.get("variable"),
            "value": r.get("value"),
            "unit": r.get("unit"),
            "Source": f"p{r.get('page')}, Methods",
            "year": r.get("year"),
            "category": r.get("category"),
            "evidence": r.get("evidence"),
            "note": r.get("note"),
            "Check": "OK" if not problems else "NEEDS HUMAN REVIEW: " + "; ".join(problems),
        })

    df = pd.DataFrame(out_rows)

    # 5. Remove exact duplicate rows (same information given twice by the AI)
    before = len(df)
    df = df.drop_duplicates(subset=DUPLICATE_KEYS).reset_index(drop=True)
    print(f"Duplicates removed: {before - len(df)}")

    df["Model"] = MODEL
    df["Temperature"] = TEMPERATURE
    df["Prompt file"] = PROMPT_FILE.as_posix()
    df["Run date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    out = folder / "methods_long.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Saved: {out}")
    print(f"Total rows: {len(df)}   Needs human review: {int((df['Check'] != 'OK').sum())}")
    print(df["category"].value_counts().to_string())


if __name__ == "__main__":
    main()