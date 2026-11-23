# 6. Assumptions and limitations

Limitations come from three sources: the PDF files, the papers themselves, and the AI
extraction. For each, the table gives the evidence, the effect on the data, and how it
is handled. No extracted value was changed; every issue below is recorded in the QAQC
log (`outputs/stage4/qaqc_log.csv`).

## 6.1 PDF text layer (font encoding)

The papers are digital PDFs, but some symbols are stored with special fonts. When the
text is read, these symbols come out as other characters. This is invisible on screen
and dangerous for units.

| Limitation | Evidence | Effect | Handling |
|---|---|---|---|
| **μ is read as "m"** (MATHG-1A font) | Pandey Table 1: "Available P (mg/g)" is printed as μg/g | a **1000× unit error** if used as is | range rule flags all 5 values (QAQC FAIL) |
| **° is read as "◦"** (MTSY font) | Pandey "25.14◦N" | coordinates not parsed | replaced by "°" before AI extraction |
| **′ (minutes) is read as "0"** | Ghosh "26°270N" = 26°27′N | latitude/longitude misread | AI evidence check flags the row (AI silently corrected it) |
| **Superscripts lost** | Sarkar "Mg/m" = Mg/m³ | unit looks wrong | QAQC unit WARN |
| **"≤" read as "B", "+" read as "?"** | Ghosh footnotes "P B 0.05", "crop residue ? FYM" | footnote meaning unclear | noted; does not affect values |

## 6.2 Errors and gaps in the papers

These values were extracted **correctly**: they are what the paper prints. They are
flagged because they are not plausible or not complete.

| Limitation | Evidence | Effect | Handling |
|---|---|---|---|
| Impossible bulk density | Pandey RNT-WNT: **2.53 g/cm³** (mineral soils 0.8–1.9; likely 1.53) | wrong end-soil BD for one treatment | QAQC FAIL; value kept unchanged |
| Depth typo | Sarkar: "0–15, **150–30** and 30–45 cm" | impossible soil layer | QAQC depth-order FAIL |
| Likely wrong N unit | Sarkar total N **0.04–0.06 g/kg**; with SOC 3.6 g/kg this gives C:N ≈ 90 (normal ≈ 10). If the unit is %, C:N ≈ 9 | initial soil N 10× too low | QAQC FAIL (min 0.1 g/kg) |
| **Unit not printed** | Ghosh TOC and C-fractions (150 values) have no unit in Tables 3–4 or the text | end-SOC values **cannot be used for DayCent** until the unit is confirmed | QAQC unit-missing WARN |
| Unusual significance level | Pandey Table 1 caption: Duncan's test "p < 0.5" (probably 0.05) | significance letters may be misleading | noted only |

## 6.3 AI extraction

The AI (DeepSeek v4.1 Flash) is checked by code after every step, but some error types
pass the checks.

| Limitation | Evidence | Effect | Handling |
|---|---|---|---|
| **Numbers right, labels wrong**: the AI drops the column that tells rows apart | Hand-check: values **30/30** correct, but rows fully correct only **23/30** (77 %, 95 % CI 59–88 %). Lost: crop (Ghosh T1), rotation (Ghosh T2), residue code (Sarkar T3), transplanted/direct-seeded column (Sarkar T5), 2003 treatment (Pandey) | a correct number can be assigned to the **wrong treatment** | QAQC duplicate check finds such rows (54 flagged); fix by hand before use |
| Value placed in the wrong column | Ghosh Table 1: "No of irrigation" holds fertiliser-timing text (6 rows); FYM / crop residue got the unit of the wrong header | wrong value for a variable | AI check and QAQC range/unit flags |
| AI "repairs" source text despite instructions | Ghosh latitude: prompt v2 says "do not fix strange characters", the AI still changed "26°270N" to "26°27'N" | output no longer matches the PDF exactly | evidence check flags it; shows that **code checks, not prompts, guarantee traceability** |
| Information missed | Pandey rice puddling (RCT tillage); Sarkar TR/DR codes; wheat straw stored as "manure" and given to all treatments | incomplete or mislabelled management data | not caught automatically: measures correctness, not completeness |
| Caption classifier sees one caption at a time | Pandey Fig. 8 (the **only** rice-yield data) marked "not needed" under the rule "figures that repeat a table" | a key input lost before extraction | known issue; fix: classify all captions of a paper together |

## 6.4 Main assumptions

- Values are used **as printed**; no value is corrected in the dataset. Corrections are
  a decision for the DayCent user, supported by the QAQC log.
- Units are kept **as reported** (no conversion between papers) for this 3-paper pilot.
- Weather is not extracted: DayCent takes weather from external databases.
