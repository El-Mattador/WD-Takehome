import json
from tabulate import tabulate


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

rows = sorted(seen.values(), key=lambda r: parse_ref(r["Ref"]))

print(tabulate(rows, headers="keys", tablefmt="grid", maxcolwidths=[25, 20, 25, 8, 50]))
