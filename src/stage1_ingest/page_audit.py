"""
Stage 1 - Page audit.

Decides, per page, whether a PDF page is born-digital (use the embedded text
layer) or scanned (needs OCR), and records what each page contains so later
stages know where to look.

Usage:
    python src/stage1_ingest/page_audit.py data/raw_pdfs/Pandey_2012.pdf [--no-ocr-check]

Outputs (outputs/stage1/<paper>/):
    page_audit.csv         one row per page with all metrics + decision
    ocr_check/page_NN.txt  Tesseract output for each page (evidence for the OCR decision)
"""
import argparse
import re
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ---- Decision thresholds (kept in one place so they can be cited in the report) ----
MIN_CHARS_BORN_DIGITAL = 200      # fewer chars than this on a page -> suspicious
MAX_IMAGE_COVERAGE = 0.80         # a single image covering >80% of page -> likely a scan
OCR_DPI = 300                     # standard resolution for Tesseract

CAPTION_RE = re.compile(r"^\s*(Table|Fig\.?|Figure)\s*(\d+)\s*[.:]?", re.MULTILINE)
TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def image_coverage(page: fitz.Page) -> float:
    """Fraction of the page area covered by embedded raster images (clipped to page)."""
    page_area = page.rect.width * page.rect.height
    covered = 0.0
    for info in page.get_image_info():
        r = fitz.Rect(info["bbox"]) & page.rect
        if not r.is_empty:
            covered += r.width * r.height
    return min(covered / page_area, 1.0)


def ocr_agreement(page: fitz.Page, text_layer: str, out_txt: Path) -> tuple[float, float]:
    """Render page, OCR it, and measure how many text-layer words OCR also finds.

    Returns (recall_of_text_layer_words_in_ocr, ocr_seconds).
    High recall = text layer and OCR agree -> OCR adds nothing.
    """
    t0 = time.time()
    pix = page.get_pixmap(dpi=OCR_DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    ocr_text = pytesseract.image_to_string(img, lang="eng")
    secs = time.time() - t0
    out_txt.write_text(ocr_text, encoding="utf-8")

    layer_tokens = set(TOKEN_RE.findall(text_layer.lower()))
    ocr_tokens = set(TOKEN_RE.findall(ocr_text.lower()))
    if not layer_tokens:
        return 0.0, secs
    return len(layer_tokens & ocr_tokens) / len(layer_tokens), secs


def audit(pdf_path: Path, out_root: Path, ocr_check: bool) -> pd.DataFrame:
    paper = pdf_path.stem
    out_dir = out_root / paper
    (out_dir / "ocr_check").mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    rows = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        fonts = page.get_fonts()
        cov = image_coverage(page)
        captions = sorted({f"{m.group(1).rstrip('.').replace('Figure', 'Fig')} {m.group(2)}"
                           for m in CAPTION_RE.finditer(text)})

        n_letters = len(text)
        n_fonts = len(fonts)

        # Simple, readable column names (this table goes into the report)
        row = {
            "Paper": paper,
            "Page": i,
            "Letters on page": n_letters,
            "Fonts used": n_fonts,
            "Pictures on page": len(page.get_image_info()),
            "% of page covered by pictures": round(cov * 100),
            "Shapes drawn (lines, bars, boxes)": len(page.get_drawings()),
            "Table/Figure captions found": ", ".join(captions),
        }

        if ocr_check:
            recall, _ = ocr_agreement(page, text, out_dir / "ocr_check" / f"page_{i:02d}.txt")
            row["OCR finds same words (%)"] = round(recall * 100)

        # The decision rule
        born_digital = (n_letters >= MIN_CHARS_BORN_DIGITAL
                        and cov <= MAX_IMAGE_COVERAGE
                        and n_fonts > 0)
        row["Decision"] = "Digital - no OCR needed" if born_digital else "Scanned - needs OCR"

        rows.append(row)
        print(f"  page {i:2d} done -> {row['Decision']}", file=sys.stderr)

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "page_audit.csv", index=False, encoding="utf-8-sig")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, default=Path("outputs/stage1"))
    ap.add_argument("--no-ocr-check", action="store_true")
    args = ap.parse_args()
    df = audit(args.pdf, args.out, ocr_check=not args.no_ocr_check)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
