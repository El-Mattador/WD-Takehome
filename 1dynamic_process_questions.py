import csv
import json


def parse_ref(ref):
    """Parse ref like '1.3.3' into tuple of ints for sorting."""
    return tuple(int(x) for x in ref.split("."))


with open("questions.json") as f:
    data = json.load(f)

seen = {}
for item in data["data"]:
    label = item["label"]
    ref = label["ref"]
    if ref not in seen:
        seen[ref] = {
            "Strand": label["strand"],
            "Sub-Strand": label["subStrand"],
            "Topic": label["topic"],
            "Loid": label["loId"],
            "Learning Outcome": label["learningOutcome"]
        }

rows = [v for _, v in sorted(seen.items(), key=lambda x: parse_ref(x[0]))]

output = "dynamic_learning_outcomes.csv"
with open(output, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Strand", "Sub-Strand", "Topic", "Loid", "Learning Outcome"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Saved {len(rows)} rows to {output}")
