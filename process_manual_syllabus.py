import json
import re

import pandas as pd

INPUT_CSV  = "manual syllabus LO.csv"
OUTPUT_CSV = "manual syllabus LO filled.csv"
TREE_JSON  = "syllabus_tree.json"
INDEX_JSON = "lo_index.json"


def strip_topic_prefix(topic: str) -> str:
    """Remove leading numbering like '1. ' or '3. ' from topic names."""
    return re.sub(r"^\d+\.\s*", "", topic).strip()


def load_and_fill(input_csv: str = INPUT_CSV, output_csv: str = OUTPUT_CSV) -> pd.DataFrame:
    """Read raw CSV, forward-fill merged cells, construct loId column, save filled CSV."""
    df = pd.read_csv(input_csv)
    df = df.ffill()
    df["loId"] = df["Primary Level"].astype(str) + ":" + df["Sub-Strand"] + ":" + df["Ref"].astype(str)
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} rows to '{output_csv}'")
    return df


def build_syllabus(df: pd.DataFrame) -> tuple[dict, dict]:
    """
    Build syllabus structures from a filled DataFrame.

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
    df = load_and_fill()
    tree, index = build_syllabus(df)

    save_json(tree,  TREE_JSON)
    save_json(index, INDEX_JSON)

    print()
    print(f"Total LOs: {len(index)}")
    for strand, subs in tree.items():
        for sub, topics in subs.items():
            total = sum(len(los) for los in topics.values())
            print(f"  {strand} > {sub}: {len(topics)} topics, {total} LOs")
