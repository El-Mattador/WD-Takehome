"""
Batch evaluation logic: fetch questions, run classifier, compute accuracy metrics.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

import classifier

QUESTIONS_URL = "https://api-v1.zyrooai.com/api/v1/math-classifier/interview/questions"
RESULTS_DIR   = Path("results")

# The 4 levels we compare, in hierarchy order
LEVELS = ["strand", "subStrand", "topic", "loId"]
LEVEL_LABELS = {
    "strand":    "Strand",
    "subStrand": "Sub-Strand",
    "topic":     "Topic",
    "loId":      "LO ID",
}


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_questions(url: str = QUESTIONS_URL) -> list[dict]:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()["data"]


# ── Batch classification ──────────────────────────────────────────────────────

def run_batch(
    questions: list[dict],
    tree: dict,
    api_key: str,
    model: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    Run classifier on every question. Returns a list of result dicts.
    Each result contains the question, ground truth, prediction, and per-level match flags.
    """
    results = []

    for i, q in enumerate(questions):
        if progress_cb:
            progress_cb(i, len(questions))

        try:
            predicted = classifier.classify(
                question=q["question"],
                tree=tree,
                api_key=api_key,
                model=model,
            )
            error = None
        except Exception as e:
            predicted = {lvl: None for lvl in LEVELS}
            error = str(e)

        gt = q["label"]
        # Normalise whitespace in GT fields before comparing
        gt_clean = {k: v.strip() if isinstance(v, str) else v for k, v in gt.items()}

        correct = {
            lvl: (predicted.get(lvl) or "").strip() == (gt_clean.get(lvl) or "").strip()
            for lvl in LEVELS
        }

        results.append({
            "id":           q["id"],
            "grade":        q["grade"],
            "question":     q["question"],
            "ground_truth": gt_clean,
            "predicted":    predicted,
            "correct":      correct,
            "all_correct":  all(correct.values()),
            "error":        error,
        })

        time.sleep(0.05)  # small pause to avoid rate-limiting

    if progress_cb:
        progress_cb(len(questions), len(questions))

    return results


# ── Accuracy metrics ──────────────────────────────────────────────────────────

def compute_accuracy(results: list[dict]) -> dict:
    """
    Returns:
        overall     - {level: accuracy_float} for all 4 levels
        by_strand   - {strand: {total, correct: {level: int}}}
        by_substrand - {sub_strand: {total, correct: {level: int}}}
        total       - int
    """
    total = len(results)
    if total == 0:
        return {}

    # Overall
    overall = {
        lvl: sum(r["correct"][lvl] for r in results) / total
        for lvl in LEVELS
    }

    # Per-strand breakdown
    by_strand: dict = {}
    by_substrand: dict = {}

    for r in results:
        gt = r["ground_truth"]
        strand = gt.get("strand", "Unknown")
        sub    = gt.get("subStrand", "Unknown")

        for bucket, key in [(by_strand, strand), (by_substrand, sub)]:
            if key not in bucket:
                bucket[key] = {"total": 0, "correct": {lvl: 0 for lvl in LEVELS}}
            bucket[key]["total"] += 1
            for lvl in LEVELS:
                if r["correct"][lvl]:
                    bucket[key]["correct"][lvl] += 1

    return {
        "overall":      overall,
        "by_strand":    by_strand,
        "by_substrand": by_substrand,
        "total":        total,
    }


# ── DataFrame builders ────────────────────────────────────────────────────────

def to_comparison_df(results: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build a display DataFrame and a boolean match DataFrame (same shape,
    used for Styler colouring).

    Display columns: ID | Grade | Question | Strand | Sub-Strand | Topic | LO ID
    Each level column shows: predicted value; if mismatch, "PRED ≠ GT"
    """
    display_rows = []
    match_rows   = []

    for r in results:
        gt   = r["ground_truth"]
        pred = r["predicted"]
        corr = r["correct"]

        display_row = {
            "ID":       r["id"],
            "Grade":    r["grade"],
            "Question": r["question"][:70] + "…" if len(r["question"]) > 70 else r["question"],
        }
        match_row = {}

        for lvl, col in LEVEL_LABELS.items():
            p = (pred.get(lvl) or "").strip()
            g = (gt.get(lvl)   or "").strip()
            if corr[lvl]:
                display_row[col] = p
            else:
                display_row[col] = f"{p}\n≠ {g}"
            match_row[col] = corr[lvl]

        display_rows.append(display_row)
        match_rows.append(match_row)

    return pd.DataFrame(display_rows), pd.DataFrame(match_rows)


def to_breakdown_df(by_group: dict) -> pd.DataFrame:
    """Convert a by_strand or by_substrand dict to a styled breakdown DataFrame."""
    rows = []
    for name, data in by_group.items():
        total = data["total"]
        row = {"Group": name, "Total": total}
        for lvl, col in LEVEL_LABELS.items():
            n = data["correct"][lvl]
            row[col] = f"{n}/{total} ({100*n/total:.0f}%)"
        rows.append(row)
    return pd.DataFrame(rows)


# ── Persistence ───────────────────────────────────────────────────────────────

def save_results(results: list[dict], metadata: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "results": results}, f, indent=2, ensure_ascii=False)


def load_results(path: Path) -> tuple[list[dict], dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["results"], data.get("metadata", {})


def results_path(source: str, model: str) -> Path:
    """Deterministic path so the same (source, model) always overwrites the same file."""
    safe_model = model.replace("/", "_").replace(":", "_")
    return RESULTS_DIR / f"results_{source}_{safe_model}.json"


# ── Terminal display ──────────────────────────────────────────────────────────

def _print_results(results: list[dict], meta: dict) -> None:
    accuracy = compute_accuracy(results)
    overall  = accuracy["overall"]
    total    = accuracy["total"]

    print()
    print("=" * 70)
    print("BATCH EVALUATION RESULTS")
    print("=" * 70)
    if meta:
        print(f"  Model   : {meta.get('model', '—')}")
        print(f"  Source  : {meta.get('source', '—')}")
        print(f"  Run at  : {meta.get('timestamp', '—')}")
        print(f"  Total   : {total} questions")
    print()

    # Overall accuracy
    print("OVERALL ACCURACY")
    print("-" * 40)
    for lvl, label in LEVEL_LABELS.items():
        n_ok = sum(r["correct"][lvl] for r in results)
        pct  = overall[lvl] * 100
        bar  = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {label:<14} {bar}  {n_ok:>2}/{total}  ({pct:.1f}%)")
    print()

    # Per-strand breakdown
    print("ACCURACY BY STRAND")
    print("-" * 70)
    header = f"  {'Strand':<38} {'Total':>5}  " + "  ".join(f"{LEVEL_LABELS[l]:<10}" for l in LEVELS)
    print(header)
    print("  " + "-" * 66)
    for strand, data in accuracy["by_strand"].items():
        t = data["total"]
        cells = "  ".join(
            f"{data['correct'][l]:>2}/{t} ({100*data['correct'][l]/t:>4.0f}%)"
            for l in LEVELS
        )
        print(f"  {strand:<38} {t:>5}  {cells}")
    print()

    # Per-sub-strand breakdown
    print("ACCURACY BY SUB-STRAND")
    print("-" * 70)
    header = f"  {'Sub-Strand':<34} {'Total':>5}  " + "  ".join(f"{LEVEL_LABELS[l]:<10}" for l in LEVELS)
    print(header)
    print("  " + "-" * 66)
    for sub, data in accuracy["by_substrand"].items():
        t = data["total"]
        cells = "  ".join(
            f"{data['correct'][l]:>2}/{t} ({100*data['correct'][l]/t:>4.0f}%)"
            for l in LEVELS
        )
        print(f"  {sub:<34} {t:>5}  {cells}")
    print()

    # Mismatches
    mismatches = [r for r in results if not r["all_correct"]]
    print(f"MISMATCHES  ({len(mismatches)}/{total} questions)")
    print("-" * 70)
    for r in mismatches:
        gt   = r["ground_truth"]
        pred = r["predicted"]
        q    = r["question"][:65] + "…" if len(r["question"]) > 65 else r["question"]
        print(f"\n  [{r['id']}] {q}")
        for lvl, label in LEVEL_LABELS.items():
            p = (pred.get(lvl) or "").strip()
            g = (gt.get(lvl)   or "").strip()
            mark = "✓" if r["correct"][lvl] else "✗"
            if r["correct"][lvl]:
                print(f"    {mark} {label:<14} {p}")
            else:
                print(f"    {mark} {label:<14} predicted : {p}")
                print(f"      {'':14} expected  : {g}")
    print()
    print("=" * 70)


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    SOURCE  = os.getenv("SYLLABUS_SOURCE", "manual")   # "manual" or "dynamic"
    API_KEY = os.getenv("LLM_API_KEY", "")
    MODEL   = os.getenv("MODEL", "google/gemini-2.5-flash-lite")

    tree_file = Path(f"syllabus_tree_{SOURCE}.json")
    rpath     = results_path(SOURCE, MODEL)

    if rpath.exists():
        print(f"Results file found: {rpath}")
        print("Loading existing results…")
        results, meta = load_results(rpath)
    else:
        print(f"No results file found at {rpath}. Running evaluation…")

        if not tree_file.exists():
            raise FileNotFoundError(
                f"Syllabus tree '{tree_file}' not found. "
                f"Run process_{SOURCE}_syllabus.py first."
            )
        if not API_KEY:
            raise ValueError("LLM_API_KEY not set in .env")

        with open(tree_file, encoding="utf-8") as f:
            tree = json.load(f)

        print("Fetching questions from API…")
        questions = fetch_questions()
        print(f"Fetched {len(questions)} questions. Classifying…")

        def cli_progress(i, total):
            print(f"  {i}/{total}", end="\r", flush=True)

        results = run_batch(
            questions=questions,
            tree=tree,
            api_key=API_KEY,
            model=MODEL,
            progress_cb=cli_progress,
        )

        meta = {
            "source":    SOURCE,
            "model":     MODEL,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total":     len(results),
        }
        save_results(results, meta, rpath)
        print(f"\nSaved to {rpath}")

    _print_results(results, meta)
