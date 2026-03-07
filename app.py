import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import classifier
import evaluate
import process_manual_syllabus
import process_dynamic_syllabus

load_dotenv()

# ── Constants ─────────────────────────────────────────────────────────────────

MANUAL_TREE  = Path("syllabus_tree_manual.json")
DYNAMIC_TREE = Path("syllabus_tree_dynamic.json")

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SG Math Classifier",
    page_icon="📐",
    layout="wide",
)

# ── Helper: load tree (cached per path) ──────────────────────────────────────

@st.cache_resource
def load_tree(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📐 SG Math Classifier")
    st.caption("Singapore Primary Math (P3–P4) Syllabus Classifier")

    st.divider()

    # ── Syllabus source ───────────────────────────────────────────────────────
    st.subheader("Syllabus Source")
    mode = st.radio(
        label="Source",
        options=["Manual (CSV)", "Dynamic (API)"],
        help=(
            "**Manual**: built from the hand-curated CSV covering all 77 LOs.\n\n"
            "**Dynamic**: built by fetching questions from the API and extracting "
            "unique LOs from their ground-truth labels."
        ),
        label_visibility="collapsed",
    )

    tree_path = MANUAL_TREE if mode == "Manual (CSV)" else DYNAMIC_TREE

    if tree_path.exists():
        with open(tree_path, encoding="utf-8") as f:
            _tree = json.load(f)
        lo_count = sum(
            len(los)
            for subs in _tree.values()
            for topics in subs.values()
            for los in topics.values()
        )
        st.success(f"Loaded — {lo_count} learning outcomes")
    else:
        st.warning(f"`{tree_path.name}` not found.")
        if st.button("Generate Syllabus", type="primary"):
            with st.spinner("Building syllabus..."):
                try:
                    if mode == "Manual (CSV)":
                        df = process_manual_syllabus.load_and_fill()
                        tree, index = process_manual_syllabus.build_syllabus(df)
                        process_manual_syllabus.save_json(tree,  process_manual_syllabus.TREE_JSON)
                        process_manual_syllabus.save_json(index, process_manual_syllabus.INDEX_JSON)
                    else:
                        questions = process_dynamic_syllabus.fetch_questions()
                        df = process_dynamic_syllabus.extract_unique_los(questions)
                        tree, index = process_dynamic_syllabus.build_syllabus(df)
                        process_dynamic_syllabus.save_json(tree,  process_dynamic_syllabus.TREE_JSON)
                        process_dynamic_syllabus.save_json(index, process_dynamic_syllabus.INDEX_JSON)
                    load_tree.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate syllabus: {e}")

    st.divider()

    # ── API settings ──────────────────────────────────────────────────────────
    st.subheader("API Settings")

    api_key = st.text_input(
        "API Key",
        value=os.getenv("LLM_API_KEY", ""),
        type="password",
        help="OpenRouter API key. Changes here override the .env value for this session.",
    )
    model = st.text_input(
        "Model",
        value=os.getenv("MODEL", "google/gemini-2.5-flash-lite"),
        help="Any OpenRouter-compatible model string. Changes here override the .env value.",
    )

    if not api_key:
        st.warning("No API key set. Classification will fail.")


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["📊 Batch Evaluation", "💬 Custom Question", "📚 Syllabus Explorer"])


# ── Tab 1: Batch Evaluation ───────────────────────────────────────────────────

with tab1:
    st.header("Batch Evaluation")
    st.caption(f"Syllabus source: **{mode}**")

    source_key  = "manual" if mode == "Manual (CSV)" else "dynamic"
    rpath       = evaluate.results_path(source_key, model)
    tree_ready  = tree_path.exists()

    # ── Action buttons ────────────────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns([1, 1])
    run_btn  = btn_col1.button("▶ Run Evaluation",   type="primary",   disabled=not tree_ready or not api_key)
    load_btn = btn_col2.button("📂 Load Previous Results", disabled=not rpath.exists())

    # ── Load saved results ────────────────────────────────────────────────────
    if load_btn and rpath.exists():
        results, meta = evaluate.load_results(rpath)
        st.session_state["eval_results"] = results
        st.session_state["eval_meta"]    = meta

    # ── Run evaluation ────────────────────────────────────────────────────────
    if run_btn:
        tree = load_tree(str(tree_path))

        with st.spinner("Fetching questions from API..."):
            try:
                questions = evaluate.fetch_questions()
            except Exception as e:
                st.error(f"Failed to fetch questions: {e}")
                st.stop()

        progress_bar = st.progress(0, text="Classifying questions…")

        def update_progress(i, total):
            progress_bar.progress(i / total, text=f"Classifying {i}/{total}…")

        results = evaluate.run_batch(
            questions=questions,
            tree=tree,
            api_key=api_key,
            model=model,
            progress_cb=update_progress,
        )
        progress_bar.empty()

        meta = {
            "source":    mode,
            "model":     model,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total":     len(results),
        }
        evaluate.save_results(results, meta, rpath)
        st.session_state["eval_results"] = results
        st.session_state["eval_meta"]    = meta
        st.success(f"Done — {len(results)} questions classified and saved to `{rpath}`")

    # ── Display results ───────────────────────────────────────────────────────
    if "eval_results" not in st.session_state:
        if rpath.exists():
            st.info("Previous results found. Click **Load Previous Results** to view them, or run a fresh evaluation.")
        else:
            st.info("No results yet. Click **Run Evaluation** to start.")
    else:
        results = st.session_state["eval_results"]
        meta    = st.session_state.get("eval_meta", {})

        if meta:
            st.caption(
                f"Model: `{meta.get('model', '—')}` · "
                f"Source: {meta.get('source', '—')} · "
                f"Run at: {meta.get('timestamp', '—')} · "
                f"Total: {meta.get('total', len(results))} questions"
            )

        accuracy = evaluate.compute_accuracy(results)
        overall  = accuracy["overall"]

        # ── Accuracy summary cards ────────────────────────────────────────────
        st.subheader("Overall Accuracy")
        c1, c2, c3, c4 = st.columns(4)
        for col, (lvl, label) in zip(
            [c1, c2, c3, c4],
            evaluate.LEVEL_LABELS.items(),
        ):
            pct   = overall[lvl] * 100
            n_ok  = sum(r["correct"][lvl] for r in results)
            col.metric(label, f"{pct:.1f}%", f"{n_ok}/{len(results)} correct")

        st.divider()

        # ── Breakdown tables ──────────────────────────────────────────────────
        with st.expander("Accuracy Breakdown by Strand / Sub-Strand", expanded=True):
            t_strand, t_sub = st.tabs(["By Strand", "By Sub-Strand"])

            with t_strand:
                df_strand = evaluate.to_breakdown_df(accuracy["by_strand"])
                st.dataframe(df_strand.set_index("Group"), use_container_width=True)

            with t_sub:
                df_sub = evaluate.to_breakdown_df(accuracy["by_substrand"])
                st.dataframe(df_sub.set_index("Group"), use_container_width=True)

        st.divider()

        # ── Comparison table ──────────────────────────────────────────────────
        st.subheader("Question-by-Question Comparison")

        view_filter = st.radio(
            "Show",
            ["All", "Correct only", "Mismatches only"],
            horizontal=True,
            label_visibility="collapsed",
        )

        filtered = results
        if view_filter == "Correct only":
            filtered = [r for r in results if r["all_correct"]]
        elif view_filter == "Mismatches only":
            filtered = [r for r in results if not r["all_correct"]]

        st.caption(f"Showing {len(filtered)} / {len(results)} questions")

        if filtered:
            disp_df, match_df = evaluate.to_comparison_df(filtered)

            level_cols = list(evaluate.LEVEL_LABELS.values())

            def _colour_cells(col_series):
                col_name = col_series.name
                if col_name not in level_cols:
                    return [""] * len(col_series)
                match_col = match_df[col_name]
                return [
                    "background-color: #1c4532; color: #d1fae5" if m
                    else "background-color: #4c1616; color: #fee2e2"
                    for m in match_col
                ]

            styled = (
                disp_df.style
                .apply(_colour_cells, axis=0)
                .set_properties(**{"white-space": "pre-wrap"})
            )
            st.dataframe(styled, use_container_width=True, height=500)


# ── Tab 2: Custom Question ────────────────────────────────────────────────────

with tab2:
    st.header("Custom Question")
    st.caption(f"Syllabus source: **{mode}**")

    question = st.text_area(
        "Enter a math question",
        placeholder="e.g. What is the remainder when 3079 is divided by 8?",
        height=100,
    )

    classify_btn = st.button("Classify", type="primary", disabled=not tree_path.exists() or not api_key)

    if classify_btn and question.strip():
        tree = load_tree(str(tree_path))

        with st.spinner("Classifying..."):
            try:
                result, trace = classifier.classify(
                    question=question.strip(),
                    tree=tree,
                    return_trace=True,
                    api_key=api_key,
                    model=model,
                )
            except Exception as e:
                st.error(f"Classification failed: {e}")
                st.stop()

        # Decision trace
        st.subheader("Decision Trace")
        cols = st.columns(len(trace))
        for col, step in zip(cols, trace):
            with col:
                st.markdown(f"**{step['step']}**")
                for opt in step["options"]:
                    if opt == step["chosen"]:
                        st.markdown(f"✅ **{opt}**")
                    else:
                        st.markdown(f"<span style='color:grey'>{opt}</span>", unsafe_allow_html=True)

        # Final result
        st.subheader("Result")
        res_cols = st.columns(4)
        res_cols[0].metric("Strand",            result["strand"])
        res_cols[1].metric("Sub-Strand",        result["subStrand"])
        res_cols[2].metric("Topic",             result["topic"])
        res_cols[3].metric("Learning Outcome",  result["learningOutcome"])

        st.code(json.dumps(result, indent=2), language="json")


# ── Tab 3: Syllabus Explorer ──────────────────────────────────────────────────

with tab3:
    st.header("Syllabus Explorer")
    st.caption(f"Syllabus source: **{mode}**")

    if not tree_path.exists():
        st.error(f"`{tree_path.name}` not found.")
    else:
        tree = load_tree(str(tree_path))

        total_strands   = len(tree)
        total_sub       = sum(len(subs) for subs in tree.values())
        total_topics    = sum(len(topics) for subs in tree.values() for topics in subs.values())
        total_los       = sum(
            len(los)
            for subs in tree.values()
            for topics in subs.values()
            for los in topics.values()
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Strands",           total_strands)
        m2.metric("Sub-Strands",        total_sub)
        m3.metric("Topics",            total_topics)
        m4.metric("Learning Outcomes", total_los)

        st.divider()

        for strand, subs in tree.items():
            with st.expander(f"**{strand}**", expanded=False):
                for sub, topics in subs.items():
                    st.markdown(f"**{sub}**")
                    for topic, los in topics.items():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📌 *{topic}*", unsafe_allow_html=True)
                        for lo in los:
                            grade_badge = f"`{lo['grade']}`"
                            st.markdown(
                                f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                                f"{grade_badge} {lo['loId']} — {lo['learningOutcome']}",
                                unsafe_allow_html=True,
                            )
