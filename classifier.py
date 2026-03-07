"""
Hierarchical LLM classifier for Singapore Primary Math syllabus (P3-P4).

Strategy: 4 sequential LLM calls, each narrowing the syllabus tree one level:
  question -> strand -> sub-strand -> topic -> learning outcome

Each call shows only the options valid at that level, keeping prompts short.
The LLM replies with a single integer (1-based index), minimising output tokens.
"""

import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config (change model/key in .env) ─────────────────────────────────────────
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL   = os.getenv("MODEL", "google/gemini-2.5-flash-lite")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYLLABUS_FILE  = "syllabus_tree.json"


# ── Prompts (edit to tune classification) ─────────────────────────────────────
# Keep them short: the LLM only needs to return the option number.

COMMON_PROMPT = """
You are a classifying machine. You will receive a math question and your goal is to classify the question into one of the options.
"""

STRAND_PROMPT = """\
{COMMON_PROMPT}
Math question: "{question}"
Which strand? Reply with the number only.
{options}"""

SUB_STRAND_PROMPT = """\
{COMMON_PROMPT}
Math question: "{question}"
Strand: {strand}
Which sub-strand? Reply with the number only.
{options}"""

TOPIC_PROMPT = """\
{COMMON_PROMPT}
Math question: "{question}"
{strand} > {sub_strand}
Which topic? Reply with the number only.
{options}"""

LO_PROMPT = """\
{COMMON_PROMPT}
Math question: "{question}"
{strand} > {sub_strand} > {topic}
Which learning outcome? Reply with the number only.
{options}"""


# ── LLM call ──────────────────────────────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    """Send a single prompt, return stripped text response."""
    resp = requests.post(
        url=OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _pick(response: str, options: list, fallback: int = 0) -> int:
    """Parse a 1-based integer from the LLM response; fallback to index 0."""
    m = re.search(r"\d+", response)
    if m:
        idx = int(m.group()) - 1
        if 0 <= idx < len(options):
            return idx
    return fallback


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))


# ── Syllabus loader ───────────────────────────────────────────────────────────

def load_tree(path: str = SYLLABUS_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Core classifier ───────────────────────────────────────────────────────────

def classify(question: str, tree: dict | None = None) -> dict:
    """
    Classify a math question through 4 hierarchical LLM calls.

    Returns:
        {strand, subStrand, topic, learningOutcome, loId}
    """
    if tree is None:
        tree = load_tree()

    # Step 1 – Strand
    strands = list(tree.keys())
    prompt = STRAND_PROMPT.format(
        COMMON_PROMPT=COMMON_PROMPT,
        question=question,
        options=_numbered(strands),
    )
    print(prompt)
    raw = _call_llm(prompt)
    strand = strands[_pick(raw, strands)]

    # Step 2 – Sub-strand
    sub_strands = list(tree[strand].keys())
    prompt = SUB_STRAND_PROMPT.format(
        COMMON_PROMPT=COMMON_PROMPT,
        question=question,
        strand=strand,
        options=_numbered(sub_strands),
    )
    print(prompt)
    raw = _call_llm(prompt)
    sub_strand = sub_strands[_pick(raw, sub_strands)]

    # Step 3 – Topic
    topics = list(tree[strand][sub_strand].keys())
    prompt = TOPIC_PROMPT.format(
        COMMON_PROMPT=COMMON_PROMPT,
        question=question,
        strand=strand,
        sub_strand=sub_strand,
        options=_numbered(topics),
    )
    print(prompt)
    raw = _call_llm(prompt)
    topic = topics[_pick(raw, topics)]

    # Step 4 – Learning Outcome
    lo_entries = tree[strand][sub_strand][topic]
    lo_labels  = [e["learningOutcome"] for e in lo_entries]
    prompt = LO_PROMPT.format(
        COMMON_PROMPT=COMMON_PROMPT,
        question=question,
        strand=strand,
        sub_strand=sub_strand,
        topic=topic,
        options=_numbered(lo_labels),
    )
    print(prompt)
    raw = _call_llm(prompt)
    lo = lo_entries[_pick(raw, lo_entries)]

    return {
        "strand":          strand,
        "subStrand":       sub_strand,
        "topic":           topic,
        "learningOutcome": lo["learningOutcome"],
        "loId":            lo["loId"],
    }


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    tree = load_tree()

    if len(sys.argv) > 1:
        # Manual question passed as argument
        q = " ".join(sys.argv[1:])
        print(f"\nQuestion: {q}")
        result = classify(q, tree)
        print(json.dumps(result, indent=2))
    else:
        # Interactive mode
        print("Math Question Classifier (type 'quit' to exit)")
        while True:
            q = input("\nEnter question: ").strip()
            if q.lower() in ("quit", "exit", "q"):
                break
            if not q:
                continue
            result = classify(q, tree)
            print(json.dumps(result, indent=2))
