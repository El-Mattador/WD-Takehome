import json
import re

import pandas as pd
import requests

QUESTIONS_URL = "https://api-v1.zyrooai.com/api/v1/math-classifier/interview/questions"
DYNAMIC_CSV   = "dynamic syllabus LO filled.csv"
TREE_JSON     = "syllabus_tree.json"
INDEX_JSON    = "lo_index.json"


def strip_topic_prefix(topic: str) -> str:
    """Remove leading numbering like '1. ' or '3. ' from topic names."""
    return re.sub(r"^\d+\.\s*", "", topic).strip()


def fetch_questions(url: str = QUESTIONS_URL) -> list[dict]:
    response = requests.get(url)
    response.raise_for_status()
    return response.json()["data"]


def extract_unique_los(questions: list[dict]) -> pd.DataFrame:
    """
    Deduplicate questions by loId to produce one row per learning outcome.
    Sorts by (grade, ref) to mirror the manual CSV ordering.
    """
    seen: dict[str, dict] = {}
    for item in questions:
        lo_id = item["label"]["loId"]
        if lo_id not in seen:
            label = item["label"]
            seen[lo_id] = {
                "Primary Level":     item["grade"],
                "Strand":            label["strand"],
                "Sub-Strand":        label["subStrand"],
                "Topic":             label["topic"],
                "Ref":               label["ref"],
                "Learning Outcomes": label["learningOutcome"],
                "loId":              lo_id,
            }

    rows = list(seen.values())
    rows.sort(key=lambda r: (r["Primary Level"], tuple(int(x) for x in r["Ref"].split("."))))

    df = pd.DataFrame(rows, columns=["Primary Level", "Strand", "Sub-Strand", "Topic", "Ref", "Learning Outcomes", "loId"])
    df.to_csv(DYNAMIC_CSV, index=False)
    print(f"Saved {len(df)} unique LOs to '{DYNAMIC_CSV}'")
    return df


def build_syllabus(df: pd.DataFrame) -> tuple[dict, dict]:
    """
    Build syllabus structures from a DataFrame of unique LOs.

    Returns:
        syllabus_tree  - nested dict: strand -> sub_strand -> topic -> [lo, ...]
        lo_index       - flat dict:   loId   -> full label dict
    """
    syllabus_tree: dict = {}
    lo_index: dict = {}

    for _, row in df.iterrows():
        grade   = str(row["Primary Level"]).strip()
        strand  = str(row["Strand"]).strip()
        sub     = str(row["Sub-Strand"]).strip()
        topic   = strip_topic_prefix(str(row["Topic"]))
        lo_text = str(row["Learning Outcomes"]).strip()
        lo_id   = str(row["loId"]).strip()

        lo_entry = {
            "loId":            lo_id,
            "learningOutcome": lo_text,
            "grade":           grade,
        }

        # Build nested tree: strand > sub_strand > topic > [lo_entries]
        syllabus_tree \
            .setdefault(strand, {}) \
            .setdefault(sub, {}) \
            .setdefault(topic, []) \
            .append(lo_entry)

        # Build flat index keyed by loId
        lo_index[lo_id] = {
            "strand":          strand,
            "subStrand":       sub,
            "topic":           topic,
            "learningOutcome": lo_text,
            "loId":            lo_id,
            "grade":           grade,
        }

    return syllabus_tree, lo_index


def save_json(obj: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"Saved {path}")


if __name__ == "__main__":
    questions = fetch_questions()
    print(f"Fetched {len(questions)} questions from API")

    df = extract_unique_los(questions)
    tree, index = build_syllabus(df)

    save_json(tree,  TREE_JSON)
    save_json(index, INDEX_JSON)

    print()
    print(f"Total unique LOs: {len(index)}")
    for strand, subs in tree.items():
        for sub, topics in subs.items():
            total = sum(len(los) for los in topics.values())
            print(f"  {strand} > {sub}: {len(topics)} topics, {total} LOs")
