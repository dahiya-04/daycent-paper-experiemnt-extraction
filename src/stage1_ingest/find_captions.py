import re
import sys
import unicodedata
from pathlib import Path

import pymupdf
import pandas as pd

# re.IGNORECASE -> also matches "TABLE 1", "FIGURE 1" (Taylor & Francis style)
# \d+[A-Z]?     -> also matches numbers with a letter, like "6A", "6B"
CAPTION_START = re.compile(r"^(Table|Fig\.?|Figure)\s*(\d+[A-Z]?)", re.IGNORECASE)

MAX_GAP = 6

def clean(text):
    """Join lines into one line and fix special letters like 'ﬂ' -> 'fl'."""
    text = unicodedata.normalize("NFKC", text)
    return " ".join(text.split())

def find_captions(pdf_path):
    paper = Path(pdf_path).stem
    doc = pymupdf.open(pdf_path)
    rows = []

    for page_no, page in enumerate(doc, start=1):
        # Each block = (x0, y0, x1, y1, text, block_no, block_type)
        # block_type 0 = text, 1 = image. We keep only text blocks.
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]

        for b in blocks:
            match = CAPTION_START.match(clean(b[4]))
            if not match:
                continue  # this paragraph is not a caption

            # --- Join the caption pieces sitting directly below it ---
            x0, top, x1, bottom = b[0], b[1], b[2], b[3]
            pieces = [b]
            # other blocks below the caption AND in the same column
            below = [o for o in blocks
                     if o is not b and o[1] >= top - 1 and o[0] < x1 and o[2] > x0]
            below.sort(key=lambda o: o[1])  # top to bottom
            for o in below:
                if o[1] <= bottom + MAX_GAP:      # close enough -> same caption
                    pieces.append(o)
                    bottom = max(bottom, o[3])
                else:                             # big gap -> caption finished
                    break
            pieces.sort(key=lambda o: (o[1], o[0]))  # reading order
            caption_text = " ".join(clean(p[4]) for p in pieces)

            kind = "Table" if match.group(1).lower() == "table" else "Figure"
            rows.append({
                "Paper": paper,
                "Page": page_no,
                "Label": f"{kind} {match.group(2).upper()}",
                "Type": kind,
                "Caption text": caption_text,
            })

    return pd.DataFrame(rows)


def main():
    pdf_path = Path(sys.argv[1])
    df = find_captions(pdf_path)
    if df.empty:
        print("Found 0 captions - check how this paper writes its captions")
        return
    out_dir = Path("outputs/stage1") / pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_dir / "captions.csv", index=False, encoding="utf-8-sig")

    # --- Simple checks printed on screen ---
    print(f"Found {len(df)} captions: "
          f"{(df['Type'] == 'Table').sum()} tables, {(df['Type'] == 'Figure').sum()} figures")
    duplicates = df[df.duplicated("Label", keep=False)]
    if len(duplicates):
        print("WARNING - same label found more than once:",
              sorted(duplicates["Label"].unique()))   

    else:
        print("OK - every label found only once")
    print(df[["Page", "Label", "Caption text"]].to_string(index=False, max_colwidth=70))


if __name__ == "__main__":
    main()


# RUN : python src\stage1_ingest\find_captions.py data\raw_pdfs\Pandey_2012.pdf
# Output:outputs/stage1/<paper>/captions.csv