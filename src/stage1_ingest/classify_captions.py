import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # find src/llm_client.py
from llm_client import MODEL, TEMPERATURE, make_client, model_kwargs   # model chosen in .env
PROMPT_FILE = Path("prompts/caption_classifier_v3.txt")   # v3: input / not_needed only

# ---- The only answers we accept from the AI ----
ALLOWED_USES = {"input", "not_needed"}
ALLOWED_CATEGORIES = {"site", "initial_soil", "crop_yield", "tillage",
                      "fertiliser", "irrigation", "end_soil"}

def ask_ai(client, prompt_template, caption_text):
    """Send one caption to the AI and return its answer as a Python dict."""
    prompt = prompt_template.replace("{caption}", caption_text)
    resp = client.chat.completions.create(
        **model_kwargs(),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},   # force JSON (tested OK)
    )
    return json.loads(resp.choices[0].message.content)



def check_answer(ans):
    """Check the AI answer. Returns a list of problems (empty list = OK)."""
    problems = []
    if ans.get("use") not in ALLOWED_USES:
        problems.append(f"unknown use '{ans.get('use')}'")

    cats = ans.get("categories")
    if not isinstance(cats, list):
        problems.append("categories is not a list")
    else:
        unknown = [c for c in cats if c not in ALLOWED_CATEGORIES]
        if unknown:
            problems.append(f"unknown categories {unknown}")
        if ans.get("use") == "input" and not cats:
            problems.append("use is 'input' but no category given")
        if ans.get("use") == "not_needed" and cats:
            problems.append("use is 'not_needed' but categories given")

    if not ans.get("reason"):
        problems.append("no reason given")
    return problems

def main():
    paper = sys.argv[1]                               # e.g. Pandey_2012
    folder = Path("outputs/stage1") / paper
    captions = pd.read_csv(folder / "captions.csv")
    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")

    client = make_client()

    results = []
    for _, row in captions.iterrows():
        print(f"{row['Label']:<9}", end=" ", flush=True)
        try:
            ans = ask_ai(client, prompt_template, row["Caption text"])
            problems = check_answer(ans)
        except Exception as e:                         # API down, bad JSON, ...
            ans, problems = {}, [f"error: {e}"]

        cats = ans.get("categories")
        results.append({
            "AI use": ans.get("use"),
            "AI categories": ", ".join(map(str, cats)) if isinstance(cats, list) else str(cats),
            "AI reason": ans.get("reason"),
            "Check": "OK" if not problems else "NEEDS HUMAN REVIEW: " + "; ".join(problems),
        })
        print(f"{str(ans.get('use')):<11} {results[-1]['AI categories']:<30} {results[-1]['Check']}")

    df = pd.concat([captions, pd.DataFrame(results)], axis=1)

    # Run details on every row, so each answer can be traced (MRV)
    df["Model"] = MODEL
    df["Temperature"] = TEMPERATURE
    df["Prompt file"] = PROMPT_FILE.as_posix()
    df["Run date"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # CSV (plain text) so it can be opened in VS Code as well as Excel
    out_all = folder / "captions_classified.csv"      # every caption
    out_input = folder / "captions_input.csv"         # only "input" -> goes to Step 3
    df.to_csv(out_all, index=False, encoding="utf-8-sig")
    df[df["AI use"] == "input"].to_csv(out_input, index=False, encoding="utf-8-sig")

    print(f"\nSaved: {out_all}")
    print(f"Saved: {out_input}")
    print(df["AI use"].value_counts().to_string())
    print("Needs human review:", int((df["Check"] != "OK").sum()))


if __name__ == "__main__":
    main()
