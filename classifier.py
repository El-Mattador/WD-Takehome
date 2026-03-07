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
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY             = os.getenv("LLM_API_KEY", "")
MODEL               = os.getenv("MODEL", "google/gemini-2.5-flash-lite")

OPENROUTER_URL      = "https://openrouter.ai/api/v1/chat/completions"
SYLLABUS_FILE       = Path(__file__).parent / "syllabus_tree.json"
MAX_RESPONSE_TOKENS = 8  # LLM only needs to return a single digit index


# ── Prompts (edit to tune classification) ─────────────────────────────────────
# Each prompt is self-contained so they can be read and edited in isolation.
# The LLM only needs to return the option number.

STRAND_PROMPT = """\
You are a classifying machine. You will receive a math question and your goal is to classify the question into one of the options.
Math question: "{question}"
Which strand? Reply with the number only.
{options}"""

SUB_STRAND_PROMPT = """\
You are a classifying machine. You will receive a math question and your goal is to classify the question into one of the options.
Math question: "{question}"
Strand: {strand}
Which sub-strand? Reply with the number only.
{options}"""

TOPIC_PROMPT = """\
You are a classifying machine. You will receive a math question and your goal is to classify the question into one of the options.
Math question: "{question}"
{strand} > {sub_strand}
Which topic? Reply with the number only.
{options}"""

LO_PROMPT = """\
You are a classifying machine. You will receive a math question and your goal is to classify the question into one of the options.
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
            "max_tokens": MAX_RESPONSE_TOKENS,
        },
        timeout=30,
    )
    resp.raise_for_status()
    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected API response structure: {resp.json()}") from e


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


def _classify_step(prompt_template: str, options: list[str], **kwargs) -> tuple[int, str]:
    """Format a prompt, call the LLM, and return the (chosen index, prompt used)."""
    prompt = prompt_template.format(options=_numbered(options), **kwargs)
    raw = _call_llm(prompt)
    return _pick(raw, options), prompt


# ── Syllabus loader ───────────────────────────────────────────────────────────

def load_tree(path: Path = SYLLABUS_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Core classifier ───────────────────────────────────────────────────────────

def classify(question: str, tree: dict | None = None, verbose: bool = False) -> dict:
    """
    Classify a math question through 4 hierarchical LLM calls.

    Args:
        question: The math question to classify.
        tree:     Pre-loaded syllabus tree; loaded from disk if not provided.
        verbose:  Print each prompt before the LLM call, for explainability.

    Returns:
        {strand, subStrand, topic, learningOutcome, loId}
    """
    if tree is None:
        tree = load_tree()

    def step(template, options, **kwargs) -> int:
        idx, prompt = _classify_step(template, options, question=question, **kwargs)
        if verbose:
            print(prompt)
        return idx

    # Step 1 – Strand
    strands    = list(tree.keys())
    strand     = strands[step(STRAND_PROMPT, strands)]

    # Step 2 – Sub-strand
    sub_strands = list(tree[strand].keys())
    sub_strand  = sub_strands[step(SUB_STRAND_PROMPT, sub_strands, strand=strand)]

    # Step 3 – Topic
    topics = list(tree[strand][sub_strand].keys())
    topic  = topics[step(TOPIC_PROMPT, topics, strand=strand, sub_strand=sub_strand)]

    # Step 4 – Learning Outcome
    lo_entries = tree[strand][sub_strand][topic]
    lo_labels  = [e["learningOutcome"] for e in lo_entries]
    lo         = lo_entries[step(LO_PROMPT, lo_labels, strand=strand, sub_strand=sub_strand, topic=topic)]

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
        q = " ".join(sys.argv[1:])
        print(f"\nQuestion: {q}")
        result = classify(q, tree, verbose=True)
        print(json.dumps(result, indent=2))
    else:
        print("Math Question Classifier (type 'quit' to exit)")
        while True:
            q = input("\nEnter question: ").strip()
            if q.lower() in ("quit", "exit", "q"):
                break
            if not q:
                continue
            result = classify(q, tree, verbose=True)
            print(json.dumps(result, indent=2))
