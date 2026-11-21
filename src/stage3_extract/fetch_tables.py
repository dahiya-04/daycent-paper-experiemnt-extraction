import re
import sys
from pathlib import Path

import pandas as pd
import pymupdf


ROW_TOLERANCE = 2     # words whose bottoms differ by <= 2 points = same row
FOOTNOTE_GAP = 10     # text starting within 10 points below the bottom line = footnote
MIN_LINE_WIDTH = 80   


def find_caption_block(page, label):
    """Find the paragraph on this page that starts with the label, e.g. 'Table 1'."""
    kind, number = label.split()
    pattern = re.compile(rf"^{kind}\s*{number}\b", re.IGNORECASE)
    for b in page.get_text("blocks"):
        if b[6] == 0 and pattern.match(" ".join(b[4].split())):
            return b
    return None

def table_area(page, caption):
    """Caption top -> 3rd full-width horizontal line below it (+ footnote).
    Returns (area, problem). problem = "" when everything looks fine."""
    cap_top = caption[1]
    # horizontal lines below the caption, top to bottom
    lines = [d["rect"] for d in page.get_drawings()
             if d["rect"].height < 2 and d["rect"].width > MIN_LINE_WIDTH
             and d["rect"].y0 > cap_top]
    lines.sort(key=lambda r: r.y0)
    if not lines:
        return None, "no table lines found"

    # "full width" = same left and right ends as the first (top) line
    top = lines[0]
    full = [r for r in lines if abs(r.x0 - top.x0) < 3 and abs(r.x1 - top.x1) < 3]
    if len(full) < 3:
        return None, f"only {len(full)} full-width lines found (expected 3)"
    bottom_line = full[2]

    x0, x1 = min(caption[0], top.x0), max(caption[2], top.x1)
    bottom = bottom_line.y1

    # footnote: text that starts just below the bottom line
    for b in sorted(page.get_text("blocks"), key=lambda b: b[1]):
        if b[6] == 0 and bottom_line.y1 <= b[1] <= bottom + FOOTNOTE_GAP and b[0] < x1 and b[2] > x0:
            bottom = max(bottom, b[3])

    return pymupdf.Rect(x0, cap_top, x1, bottom), ""

def rows_from_words(page, area):
    """Put words with the same height on the page into one row, left to right."""
    rows = {}
    for w in page.get_text("words", clip=area):   # w = (x0, y0, x1, y1, word, ...)
        y = w[3]
        key = next((k for k in rows if abs(k - y) <= ROW_TOLERANCE), y)
        rows.setdefault(key, []).append(w)
    lines = []
    for y in sorted(rows):
        words = sorted(rows[y], key=lambda w: w[0])
        lines.append(" ".join(w[4] for w in words))
    return lines


def main():
    paper = sys.argv[1]                                   # e.g. Pandey_2012
    out_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("outputs/stage3")
    doc = pymupdf.open(Path("data/raw_pdfs") / f"{paper}.pdf")
    wanted = pd.read_csv(Path("outputs/stage1") / paper / "captions_input.csv")
    wanted = wanted[wanted["Type"] == "Table"]

    out_dir = out_root / paper / "tables_text"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for _, row in wanted.iterrows():
        label, page_no = row["Label"], int(row["Page"])
        page = doc[page_no - 1]

        caption = find_caption_block(page, label)
        area, problem = (None, "caption not found") if caption is None else table_area(page, caption)

        if area is None:
            lines = []
        else:
            lines = rows_from_words(page, area)
            file = out_dir / f"{label.replace(' ', '_')}.txt"
            header = f"# {paper} | {label} | page {page_no} | area {[round(v) for v in area]}\n"
            file.write_text(header + "\n".join(lines), encoding="utf-8")

        check = "OK" if not problem else "NEEDS HUMAN REVIEW: " + problem
        summary.append({"Paper": paper, "Label": label, "Page": page_no,
                        "Rows": len(lines), "Check": check})
        print(f"{label:<9} page {page_no:<3} rows {len(lines):<3} {check}")

    pd.DataFrame(summary).to_csv(out_root / paper / "tables_fetched.csv",
                                 index=False, encoding="utf-8-sig")
    print(f"\nSaved text files in: {out_dir}")


if __name__ == "__main__":
    main()