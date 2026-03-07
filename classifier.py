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
SYLLABUS_FILE       = Path(__file__).parent / "syllabus_tree_manual.json"
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

def _call_llm(prompt: str, api_key: str | None = None, model: str | None = None) -> str:
    """Send a single prompt, return stripped text response."""
    resp = requests.post(
        url=OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key or API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model or MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
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


def _classify_step(
    prompt_template: str,
    options: list[str],
    api_key: str | None = None,
    model: str | None = None,
    **kwargs,
) -> tuple[int, str]:
    """Format a prompt, call the LLM, and return the (chosen index, prompt used)."""
    prompt = prompt_template.format(options=_numbered(options), **kwargs)
    raw = _call_llm(prompt, api_key=api_key, model=model)
    return _pick(raw, options), prompt


# ── Syllabus loader ───────────────────────────────────────────────────────────

def load_tree(path: Path = SYLLABUS_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Core classifier ───────────────────────────────────────────────────────────

def classify(
    question: str,
    tree: dict | None = None,
    verbose: bool = False,
    return_trace: bool = False,
    api_key: str | None = None,
    model: str | None = None,
) -> dict | tuple[dict, list]:
    """
    Classify a math question through 4 hierarchical LLM calls.

    Args:
        question:     The math question to classify.
        tree:         Pre-loaded syllabus tree; loaded from disk if not provided.
        verbose:      Print each prompt to stdout, for CLI explainability.
        return_trace: If True, also return a list of step dicts for UI display.
        api_key:      Override the API key from env.
        model:        Override the model from env.

    Returns:
        {strand, subStrand, topic, learningOutcome, loId}
        If return_trace=True, returns (result_dict, trace_list) where each trace
        step is {step, options, chosen}.
    """
    if tree is None:
        tree = load_tree()

    trace = []

    def step(template, options, step_name: str, **kwargs) -> int:
        idx, prompt = _classify_step(
            template, options, api_key=api_key, model=model, question=question, **kwargs
        )
        if verbose:
            print(prompt)
        trace.append({"step": step_name, "options": options, "chosen": options[idx]})
        return idx

    # Step 1 – Strand
    strands    = list(tree.keys())
    strand     = strands[step(STRAND_PROMPT, strands, "Strand")]

    # Step 2 – Sub-strand
    sub_strands = list(tree[strand].keys())
    sub_strand  = sub_strands[step(SUB_STRAND_PROMPT, sub_strands, "Sub-Strand", strand=strand)]

    # Step 3 – Topic
    topics = list(tree[strand][sub_strand].keys())
    topic  = topics[step(TOPIC_PROMPT, topics, "Topic", strand=strand, sub_strand=sub_strand)]

    # Step 4 – Learning Outcome
    lo_entries = tree[strand][sub_strand][topic]
    lo_labels  = [f"[{e['grade']}] {e['learningOutcome']}" for e in lo_entries]
    lo_idx     = step(LO_PROMPT, lo_labels, "Learning Outcome", strand=strand, sub_strand=sub_strand, topic=topic)
    lo         = lo_entries[lo_idx]

    result = {
        "strand":          strand,
        "subStrand":       sub_strand,
        "topic":           topic,
        "learningOutcome": lo["learningOutcome"],
        "loId":            lo["loId"],
    }

    if return_trace:
        return result, trace
    return result


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
