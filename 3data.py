import csv
import json
import re

SYLLABUS_CSV = "manual syllabus LO filled.csv"


def strip_topic_prefix(topic: str) -> str:
    """Remove leading numbering like '1. ' or '3. ' from topic names."""
    return re.sub(r"^\d+\.\s*", "", topic).strip()


def build_syllabus(csv_path: str = SYLLABUS_CSV) -> tuple[dict, dict]:
    """
    Reads the syllabus CSV and returns:
        syllabus_tree  - nested dict: strand -> sub_strand -> topic -> [lo, ...]
        lo_index       - flat dict:   loId   -> full label dict
    """
    syllabus_tree: dict = {}
    lo_index: dict = {}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            grade_raw = row["Primary Level"].strip()       # "3.0" or "4.0"
            strand    = row["Strand"].strip()
            sub       = row["Sub-Strand"].strip()
            topic_raw = row["Topic"].strip()
            ref       = row["Ref"].strip()
            lo_text   = row["Learning Outcomes"].strip()

            grade = int(float(grade_raw))                  # 3 or 4
            topic = strip_topic_prefix(topic_raw)          # "Multiplication and Division"
            lo_id = f"P{grade}:{sub}:{ref}"                # "P3:WHOLE NUMBERS:1.3.3"

            lo_entry = {
                "loId": lo_id,
                "learningOutcome": lo_text,
            }

            # Build nested tree
            syllabus_tree \
                .setdefault(strand, {}) \
                .setdefault(sub, {}) \
                .setdefault(topic, []) \
                .append(lo_entry)

            # Build flat index
            lo_index[lo_id] = {
                "strand":          strand,
                "subStrand":       sub,
                "topic":           topic,
                "learningOutcome": lo_text,
                "loId":            lo_id,
                "grade":           grade,
            }

    return syllabus_tree, lo_index


if __name__ == "__main__":
    tree, index = build_syllabus()

    print("=" * 60)
    print("SYLLABUS TREE")
    print("=" * 60)
    print(json.dumps(tree, indent=2))

    print()
    print("=" * 60)
    print("LO INDEX")
    print("=" * 60)
    print(json.dumps(index, indent=2))

    print()
    print("=" * 60)
    print(f"Total LOs: {len(index)}")
    for strand, subs in tree.items():
        for sub, topics in subs.items():
            total = sum(len(los) for los in topics.values())
            print(f"  {strand} > {sub}: {len(topics)} topics, {total} LOs")
