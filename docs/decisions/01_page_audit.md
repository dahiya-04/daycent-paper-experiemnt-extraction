# Decision record 01 — Page audit (Stage 1, step 1)

**Paper tested first:** Pandey_2012 (Agric. Ecosyst. Environ. 159:133–144, 12 pages)
**Script:** `src/stage1_ingest/page_audit.py`  **Output:** `outputs/stage1/Pandey_2012/page_audit.csv`
**Environment:** Python 3.12.10, PyMuPDF 2.1, pdfplumber 0.11.11, Tesseract 5.5.3

## 1. Question
Can each page be read from its embedded text layer, or does it need OCR?
A second question surfaced during the audit: is the text layer *faithful*, and which tool reads it best?

## 2. Method
For each page we measured: character count, embedded fonts, raster-image coverage of the page,
vector-drawing count, odd glyphs (U+FFFD / private-use chars), special characters (± ° μ − ′),
figure/table captions, and agreement with Tesseract OCR (share of text-layer words OCR also finds).

Rule (thresholds fixed in code):
`born-digital` if chars ≥ 200 AND image coverage ≤ 0.80 AND fonts > 0; otherwise `scanned → OCR`.

## 3. Results

| Page | Chars | Fonts | Image cov. | Vector drawings | OCR word recall | Content | Decision |
|---|---|---|---|---|---|---|---|
| 1 | 5820 | 9 | 0.02 | 9 | 0.95 | Abstract | born-digital |
| 2 | 9124 | 7 | 0 | 0 | 0.96 | Site, treatments | born-digital |
| 3 | 5877 | 9 | 0 | 546 | 0.88 | **Table 1 (soil)**, Fig 1 (vector) | born-digital |
| 4 | 5980 | 10 | 0 | 2430 | 0.98 | Fig 2 (vector), flux method | born-digital |
| 5 | 8412 | 7 | 0 | 4 | 0.96 | Table 2 (ANOVA) | born-digital |
| 6 | 1118 | 8 | 0.39 | 682 | 0.98 | Fig 3 (vector), Fig 4 (raster) | born-digital |
| 7 | 7175 | 11 | 0 | 286 | 0.97 | Fig 5 (vector) | born-digital |
| 8 | 7398 | 7 | 0.15 | 0 | 0.97 | Fig 6 (raster: roots, tillers) | born-digital |
| 9 | 3102 | 7 | 0.41 | 0 | 0.94 | Fig 7 (raster) | born-digital |
| 10 | 7585 | 7 | 0 | 142 | 0.96 | **Fig 8 grain yield (vector)** | born-digital |
| 11–12 | 12402 / 3537 | 6 / 5 | 0 | 0 | 0.98 / 0.97 | Conclusion, references | born-digital |

**All 12 pages are born-digital.** OCR finds 88–98% of the same words (lowest on page 3, which
holds the table and a chart), so it adds no text. It costs about 6 s per page at 300 dpi
against milliseconds for the text layer.

## 4. Finding: the text layer is complete but not fully faithful

Same sentence, "6.73 ± 0.56 μg m⁻² h⁻¹" (page 7), read three ways:

| Tool | Output | ± | − | μ | ° (page 2, "25.14°N") |
|---|---|---|---|---|---|
| PyMuPDF | `6.73 ± 0.56 mg m−2 h−1` | ✅ | ✅ | ❌ → `m` | ⚠️ `◦` (U+25E6) |
| pdfplumber | `6.73 (cid:6) 0.56 mg m!2h!1` | ❌ `(cid:6)` | ❌ `!` | ❌ → `m` | — |
| Tesseract | `6.73+0.564gm-~*h7!` | ❌ | ❌ | ❌ garbled | ✅ |

**Root cause.** The PDF draws μ with a maths font (`MATHG-1A`) whose ToUnicode map says the glyph
is the letter "m". Every text tool therefore reads "mg" for "μg". This is a flaw in the PDF, not
in any one tool. The degree sign comes from the `MTSY` font as `◦`.

**Impact on DayCent inputs.** It is a 1000× unit error in two places:
- Table 1, "Available P (μg/g)", would read as mg/g. "Total N (mg/g)" in the same table really is mg/g, in normal font.
- N₂O fluxes (μg m⁻² h⁻¹) would read as mg m⁻² h⁻¹.

**Fix (verified).** The paper contains exactly 5 `m` glyphs in the `MATHG` font, and all 5 are μ.
A font-aware normalisation rule repairs them: `MATHG` + `m` → `μ`, and `MTSY` + `◦` → `°`.
This rule only works with a tool that exposes the font for each character (PyMuPDF and
pdfplumber both do).

## 5. Decisions

| # | Decision | Reason | Alternatives rejected |
|---|---|---|---|
| D1 | **No OCR** for Pandey_2012 | All pages born-digital; OCR recall 0.88–0.98 adds nothing and garbles numbers and symbols | Tesseract on every page: slower, and less accurate on ±, −, digits |
| D2 | **Keep Tesseract only as a per-page fallback** | The audit rule decides per page, so older scanned papers still work | OCR-everything; cloud OCR (cost, privacy) |
| D3 | **Use PyMuPDF for the text layer** | Keeps ± and −, gives each character's font (needed for the μ fix), fast | pdfplumber: `(cid:6)` for ±, `!` for −; pypdf: no font-level access |
| D4 | **Add font-aware symbol normalisation** after extraction | Prevents the silent 1000× unit errors | Trusting raw text; regex on "mg" (cannot tell mg from μg) |
| D5 | **Unit check in QAQC**: flag N₂O fluxes and available-P values whose magnitude is implausible for the stated unit | Second safety net if a symbol is missed in another paper | — |

## 6. Leads for the next steps (not yet verified)
- **Fig. 8 (grain yield) is vector graphics** (page 10 has no raster image, but 142 drawings).
  Rice yield appears only in this chart, so the bar heights might be read exactly from the PDF
  geometry instead of digitised by eye. To be tested in the figure step.
- Figs 4, 6 and 7 are raster images. Values from them (roots, tillers) need a vision LLM or
  WebPlotDigitizer, and must be flagged as "digitised from figure".
- The caption regex also catches body-text references at the start of a line (e.g. "Table 1" on
  page 2). Tighten it when building the page → table/figure map.
- The table-extraction comparison (pdfplumber vs PyMuPDF `find_tables`) is the next step. Table 1 is on page 3.
