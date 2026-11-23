"""
Pipeline - runs every step in order, for one or more papers.

Run (from the project folder):
  python run_pipeline.py                      all 3 papers
  python run_pipeline.py Pandey_2012          one paper
  python run_pipeline.py --rerun-ai           call the AI again even if outputs exist
  """

import subprocess
import sys
from pathlib import Path

ALL_PAPERS = ["Pandey_2012", "Ghosh_2017", "Sarkar_2011"]
PYTHON = sys.executable          # the same Python that runs this file (.venv312)
RERUN_AI = False

def run(script, args):
    """Run one step. Stop the whole pipeline if it fails."""
    print(f"\n=== {script} {' '.join(args)}")
    result = subprocess.run([PYTHON, script] + args)
    if result.returncode != 0:
        print(f"\nSTOPPED: {script} failed. Fix the error above and run the pipeline again.")
        sys.exit(1)


def run_ai(script, args, output):
    """Run an AI step only if its output does not exist yet (or --rerun-ai)."""
    if output.exists() and not RERUN_AI:
        print(f"\n=== {script} {' '.join(args)}")
        print(f"    skipped: {output} already exists (use --rerun-ai to call the AI again)")
        return
    run(script, args)

def ask(question):
    """Human checkpoint: continue only on 'y'."""
    answer = input(f"\n>>> {question} (y/n): ").strip().lower()
    if answer != "y":
        print("STOPPED: finish this human step, then run the pipeline again.")
        sys.exit(0)

def main():
    global RERUN_AI
    args = sys.argv[1:]
    RERUN_AI = "--rerun-ai" in args
    papers = [a for a in args if not a.startswith("--")] or ALL_PAPERS

    for paper in papers:
        if not (Path("data/raw_pdfs") / f"{paper}.pdf").exists():
            print(f"STOPPED: data/raw_pdfs/{paper}.pdf not found")
            sys.exit(1)

    # ---------------- Stage 1 + 3: per paper ----------------
    for paper in papers:
        print(f"\n################ {paper} ################")
        pdf = str(Path("data/raw_pdfs") / f"{paper}.pdf")
        stage1 = Path("outputs/stage1") / paper
        stage3 = Path("outputs/stage3") / paper

        run_ai("src/stage1_ingest/page_audit.py", [pdf], stage1 / "page_audit.csv")   
        run_ai("src/stage1_ingest/classify_captions.py", [paper],
               stage1 / "captions_classified.csv")

        run("src/stage3_extract/fetch_tables.py", [paper])
        run_ai("src/stage3_extract/tables_to_rows.py", [paper], stage3 / "tables_long.csv")
        run_ai("src/stage3_extract/methods_to_rows.py", [paper], stage3 / "methods_long.csv")

    # ---------------- Stage 4: all papers together ----------------
    print("\n################ QAQC ################")
    ask("Have you checked qaqc/check_rules.csv (range rules for these papers)?")
    run("src/stage4_qaqc/run_qaqc.py", papers)

    hand_check = Path("qaqc/hand_check.csv")
    if not hand_check.exists():
        run("src/stage4_qaqc/make_handcheck_sample.py", papers)
        print(f"\nNEXT: fill {hand_check} (Y / N / NA) against the PDFs,")
        print("then run the pipeline again to score it.")
        sys.exit(0)

    ask(f"Have you filled and checked {hand_check} against the PDFs?")
    run("src/stage4_qaqc/score_handcheck.py", [])

    print("\n################ DONE ################")
    print("QAQC log   : outputs/stage4/qaqc_log.csv")
    print("Hand-check : outputs/stage4/handcheck_scores.csv")


if __name__ == "__main__":
    main()
