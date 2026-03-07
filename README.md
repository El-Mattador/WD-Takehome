# Singapore Primary Math Classifier (P3–P4)

An AI engine that classifies a Singapore Primary Math question into its correct syllabus node across a 4-level taxonomy:

```
Strand > Sub-Strand > Topic > Learning Outcome
```

---

## Setup

### Requirements

- Python 3.10
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Create virtual environment
uv venv --python 3.10

# Install dependencies
uv pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
LLM_API_KEY=your_openrouter_api_key_here
MODEL=google/gemini-2.5-flash-lite
```

The model can be any [OpenRouter-compatible model string](https://openrouter.ai/models).

### Data Files

The following files are excluded from the repository and must be placed in the project root before running:

- `manual syllabus LO.csv` — the hand-curated Singapore MOE P3–P4 syllabus (77 learning outcomes)

> **These files will be provided separately by the submitter.**

---

## How to Run

### Step 1 — Generate the syllabus tree

Before running the app or classifier, build the syllabus knowledge base from the CSV:

```bash
# Manual syllabus (recommended — full 77 LOs)
uv run python process_manual_syllabus.py

# Dynamic syllabus (derived from the 67 API questions)
uv run python process_dynamic_syllabus.py
```

This produces `syllabus_tree_manual.json` and `lo_index_manual.json` (or `*_dynamic.json`).

### Step 2 — Launch the web app

```bash
uv run streamlit run app.py
```

Opens at `http://localhost:8501`.


---

## Web App

The app has three tabs:

### Batch Evaluation
- Click **Run Evaluation** to classify all 67 API questions and compare against ground truth labels
- Results are saved automatically and can be reloaded without re-running via **Load Previous Results**
- Displays:
  - Overall accuracy metric cards at each level (Strand / Sub-Strand / Topic / LO ID)
  - Accuracy breakdown table by Strand and Sub-Strand
  - Question-by-question comparison table with colour-coded cells (green = correct, red = mismatch showing predicted vs expected)
  - Filter to show All / Correct only / Mismatches only

### Custom Question
- Enter any math question and classify it in real time
- Shows the full decision trace — which options were presented at each step and which the model chose
- Displays the final structured result

### Syllabus Explorer
- Browse the full loaded syllabus tree (strand > sub-strand > topic > LOs)
- Shows LO count per level and grade labels per outcome

The **sidebar** controls:
- **Syllabus Source** — toggle between Manual (CSV, 77 LOs) and Dynamic (API-derived) at any time
- **API Key** and **Model** — override `.env` values live without restarting the app. If the syllabus JSON for the selected source has not been generated yet, a **Generate Syllabus** button appears to build it on the spot.

---

## Classification Strategy

### Approach: Hierarchical LLM Calls

The classifier makes **4 sequential LLM calls**, narrowing the taxonomy one level at a time:

```
Question
  → Step 1: Pick Strand         (3 options)
  → Step 2: Pick Sub-Strand     (2–7 options, given the strand)
  → Step 3: Pick Topic          (2–6 options, given the sub-strand)
  → Step 4: Pick Learning Outcome (1–6 options, given the topic)
```

At each step, the LLM is shown only the valid options for that level — never the full 77-LO list at once. It replies with a single integer index, keeping output tokens minimal (`max_tokens=8`).

### Why hierarchical over single-shot?

| Approach | Decision space per call | Explainability | Error propagation |
|---|---|---|---|
| Single-shot (all 77 LOs at once) | 77 options | Low | None |
| Hierarchical (4 steps) | 3–7 options | High — each step is auditable | Errors at higher levels cascade |

The hierarchical approach was chosen because:

1. **Smaller decision spaces** — the LLM is less likely to confuse similar-sounding LOs when only shown 3–7 options rather than 77
2. **Explainability** — every classification decision is visible and auditable in the UI's decision trace
3. **Grade determination falls out naturally** — P3 and P4 topics with the same name are merged in the tree. The final LO step presents grade-labelled options (`[P3] division with remainder` vs `[P4] ...`), so grade is determined as a consequence of picking the right LO rather than as a separate step

### Prompt Design

Each prompt is minimal and self-contained:

```
You are a classifying machine. You will receive a math question and your goal
is to classify the question into one of the options.
Math question: "{question}"
Which strand? Reply with the number only.
1. NUMBER AND ALGEBRA
2. MEASUREMENT AND GEOMETRY
3. STATISTICS
```

The instruction to reply with a number only keeps the response deterministic and the token cost near zero. A fallback to index 0 handles any unexpected output.

### Two Syllabus Modes

| Mode | Source | LO Count | Best for |
|---|---|---|---|
| **Manual (CSV)** | Hand-curated `manual syllabus LO.csv` | 77 (complete syllabus) | Full coverage, custom questions outside the test set |
| **Dynamic (API)** | LOs extracted from the 67 ground-truth labels | ~30–40 (only what appears in the test set) | Comparing against a minimal knowledge base |

The Dynamic mode demonstrates the trade-off: by only knowing LOs present in the test questions, the classifier has fewer options to choose from per step, but cannot correctly classify any question whose true LO was not represented in the 67-question set.

---

## Accuracy Results

> Results are saved to `results/results_<source>_<model>.json` after each evaluation run.
> Run `python evaluate.py` or use the web app to generate results.

*To be filled in after evaluation run.*

---

## File Structure

```
.
├── app.py                          # Streamlit web app
├── classifier.py                   # Hierarchical LLM classifier
├── evaluate.py                     # Batch evaluation + metrics
├── process_manual_syllabus.py      # Build syllabus tree from CSV
├── process_dynamic_syllabus.py     # Build syllabus tree from API questions
├── requirements.txt
├── .env                            # API key + model config (not committed)
│
├── manual syllabus LO.csv          # Source syllabus data (provided separately)
├── manual syllabus LO filled.csv   # Generated by process_manual_syllabus.py
├── syllabus_tree_manual.json       # Generated knowledge base (manual)
├── syllabus_tree_dynamic.json      # Generated knowledge base (dynamic)
├── lo_index_manual.json            # Flat LO lookup (manual)
├── lo_index_dynamic.json           # Flat LO lookup (dynamic)
│
└── results/
    └── results_<source>_<model>.json   # Evaluation output
```

---

## Requirements

```
streamlit
pandas
requests
python-dotenv
```
