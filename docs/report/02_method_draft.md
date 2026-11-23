# 2. Method: pipeline, tools and choices

## 2.1 The pipeline in plain language

The pipeline turns a research paper (PDF) into rows of DayCent input data. Each row
records the paper, site, treatment, depth, variable, value, unit and the page it came
from. Three papers were processed: Pandey et al. 2012 (12 pages), Ghosh et al. 2017
(12 pages) and Sarkar et al. 2011 (30 pages).

```
 PDF papers (3)
     │
 [1] Page audit ............... is each page digital text or a scan?
     │                          → all 54 pages digital, no OCR needed
 [2] Find captions ............ every "Table N" / "Fig. N" (40 found)
     │
 [3] AI: which tables/figures hold DayCent inputs?      ◆ AI
     │                          → 14 tables kept
 ┌───┴────────────────────┐
 [4a] Fetch table text     [4b] Cut out the Methods section
     │                          │
 [5a] AI: table → rows     [5b] AI: sentences → rows    ◆ AI
     └───────────┬──────────────┘
 [6] Code checks: is every value really in the PDF?
     │
 [7] QAQC rules: is every value plausible?              ● human writes rules
     │
 [8] Hand-check: 30 random rows compared with the PDF   ● AI-assisted, 5 rows re-checked by author
     │
 [9] Final dataset (712 rows) → DayCent workbook
```

One principle decides who does each step:

> **Code does what has one right answer. AI does what needs judgement.
> A human decides what is plausible.**

Finding captions, finding table borders and checking values against the PDF have one
right answer, so they are done in code and give the same result every run. Deciding
whether a table is needed, which column a number belongs to, or what a sentence means
needs judgement, so AI is used there. That happens in only three steps, and every AI
step is followed by a code check. Range rules and the final accuracy check are human
decisions.

The whole pipeline runs with one command (`python run_pipeline.py`). AI steps are skipped
when their output already exists, so the data stays identical to the data that was
QAQC'd and hand-checked. The pipeline stops and asks for confirmation at the two human
steps.

## 2.2 Tools: what was chosen and why

Every tool choice was tested on the same real example before it was adopted. The table
separates alternatives that were **tested and rejected** from those **considered but
not tested**.

| Step | Chosen | Tested and rejected (evidence) | Considered, not tested |
|---|---|---|---|
| Read PDF text | **PyMuPDF** | pdfplumber turned "±" into `(cid:6)` and "−" into `!` on the same sentence | — |
| OCR | **None needed** | Tesseract misread `±2.91` as `42.91`. The page audit showed all pages are digital (OCR and text layer agree on 82–100 % of words). | — |
| Table extraction | **Words grouped into rows by height** (PyMuPDF) | Tested on Pandey Table 1: pdfplumber grid mode found 0 tables (no ruled lines); pdfplumber text mode lost "±" and cut the last column; PyMuPDF `find_tables` **dropped decimal points** (`0.33 ± 0.02` → `033±002`, a 100× error). Only the word-row method kept every value, sign and letter. | Camelot, Tabula (need ruled grids / Java) |
| Table borders | **"3-line table" rule** (caption → 3rd full-width line) | A "large gap = end of table" rule cut Ghosh Table 3 after 2 rows and Sarkar Table 1 after its caption. The 3-line rule fetched all 14 tables completely. | — |
| Full PDF converters | **Not used** | — | Docling, Marker, GROBID: large installs and model downloads; more than needed for 3 digital PDFs |
| Figures | **Not extracted** (limitation) | — | WebPlotDigitizer (manual), reading vector shapes from the PDF |

## 2.3 The AI model

**Model:** DeepSeek v4.1 Flash (`deepseek/deepseek-v4.1-flash`), called through the
Gödel Machines API at temperature 0 with JSON output.

**Why:** free student access; an OpenAI-compatible interface, so the model can be swapped
by changing one line; reliable JSON output; and temperature 0 for repeatable answers.

**Known weaknesses:**
- **Text only, no vision.** The model cannot read figures. Figures are therefore a
  limitation of this pilot (e.g. Pandey's only rice-yield data is in Fig. 8).
- **Prompts are retained** by the provider on student keys. This is acceptable for
  published papers but not for confidential data.

**Alternatives considered:** larger or vision-capable models could read figures and may
make fewer label errors, at higher cost. Local models keep data private but need strong
hardware. Rules only (regex) cost nothing to run but break on each new publisher's layout.

**Why the model choice matters less than the checks:** the model never has the final
word. For every value, code checks that the quoted cell or sentence really exists on the
named page of the PDF, and that the value is inside that quote. The hand-check (30 random rows, compared
with the PDFs by an AI assistant; 5 rows re-checked by the author, who agreed with
all 5) confirms the effect: **all 30 sampled values were correct** (100 %, 95 % CI 89–100 %). The
remaining errors were treatment labels (23/30 rows fully correct, 77 %, 95 % CI 59–88 %),
not numbers.

## 2.4 Prompts were tested and improved

All prompts are stored as versioned files in `prompts/`; older versions are kept.

| Prompt | Change | Why (evidence) |
|---|---|---|
| Caption classifier v1 → v3 | removed the "validation" class; end-of-experiment soil carbon counts as input | v1 sent Ghosh's end-SOC tables to "validation", so they would have been lost |
| Methods extraction v1 → v2 | one value per row; link values to years; define every treatment code | v1 merged lists into one row in 2 cases (Sarkar N rates 0–120 kg/ha, sampling depths) and defined 0 of Sarkar's 10 treatment codes; v2: 0 merged rows, 10 codes defined |

One known prompt problem remains: caption classifier v3 contains a rule "figures that
repeat a table are not needed", but it sees one caption at a time and cannot know what
the tables contain. It wrongly dropped Pandey Fig. 8. The fix (send all captions of a
paper together) is noted for future work.

## 2.5 What I would change with more time

- Use a vision-capable model or WebPlotDigitizer to extract figure data (yields, SOC over time).
- Classify all captions of a paper in one request, so "duplicate figure" decisions are possible.
- Increase the hand-check sample from 30 rows to narrow the confidence interval.
