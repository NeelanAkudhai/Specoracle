"""
Streamlit Frontend for SpecOracle Multi-Agent Verification.

Three Interactive Tabs:
  1. Live Problem Verification: Choose a problem, observe multi-agent consensus live.
  2. Benchmark Analytics: Inspect raw runs, summary metrics tables, and evaluation figures.
  3. System Documentation: Review architecture, formal consensus formulation, and academic rubric.
"""
from __future__ import annotations
import os
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import streamlit as st
except ImportError:
    print("Streamlit not installed. Install via: pip install streamlit")
    sys.exit(0)

from specoracle.config import load_config
from specoracle.llm import LLMClient
from specoracle.dataset import load_problems, get_bundled_seed_problems
from specoracle.graph import run_graph
from specoracle.baselines import run_b1, run_b2
from specoracle.schemas import Problem

st.set_page_config(page_title="SpecOracle | Multi-Agent Bug Detection", page_icon="🛡️", layout="wide")

cfg = load_config()
HAS_KEY = bool(os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"))

@st.cache_resource
def get_llm(mock: bool):
    return LLMClient(cache_db=ROOT / cfg.cache_db, rpm=cfg.rpm, mock=mock)

def render_case_outcomes(outcomes, suite):
    if not outcomes:
        st.info("No case outcomes recorded.")
        return
    rows = []
    for i, o in enumerate(outcomes):
        case = suite[i] if i < len(suite) else None
        args_val = getattr(case, "args", None) if case else None
        rows.append({
            "Case #": i + 1,
            "Input Arguments": str(args_val),
            "Writer Expected": str(o.get("writer_expected")),
            "Reference Output": str(o.get("reference_output")),
            "Candidate Output": str(o.get("code_output")),
            "Consensus Verdict": o.get("label"),
            "Error Details": o.get("error") or "None"
        })
    st.dataframe(rows, use_container_width=True)

def tab_run_single():
    st.header("🔍 Interactive Code Verification")
    data_path = ROOT / cfg.data_dir / "problems.jsonl"
    if data_path.exists():
        sample = load_problems(data_path)
    else:
        sample = get_bundled_seed_problems()

    if not sample:
        st.warning("No benchmark problems loaded.")
        return

    cols = st.columns([3, 2, 2])
    with cols[0]:
        idx = st.selectbox("Select Target Problem", list(range(len(sample))), format_func=lambda i: f"{sample[i].task_id} ({sample[i].entry_point})")
    with cols[1]:
        variant = st.selectbox("Implementation Under Test", ["buggy", "canonical"])
    with cols[2]:
        system = st.selectbox("Verification Engine", ["proposed", "proposed_same", "b1", "b2"], format_func=lambda s: {
            "proposed": "SpecOracle (Cross-Model Consensus)",
            "proposed_same": "Ablation: Same-Family Model",
            "b1": "Baseline B1 (Code-Aware Writer)",
            "b2": "Baseline B2 (Spec-Only Single Agent)"
        }.get(s, s))

    problem = sample[idx]
    code = problem.buggy_code if variant == "buggy" else problem.canonical_code

    with st.expander("Function Specification & Signature", expanded=True):
        st.code(problem.spec, language="python")
    with st.expander("Candidate Implementation Under Test", expanded=False):
        st.code(code, language="python")

    if not HAS_KEY:
        st.info("💡 Notice: Running in deterministic offline MOCK mode (no API key detected). Canned agent responses enabled.")

    if st.button("🚀 Run Multi-Agent Verification", type="primary"):
        llm = get_llm(mock=not HAS_KEY)
        with st.spinner("Orchestrating agents through LangGraph state machine..."):
            t0 = time.time()
            if system in ("proposed", "proposed_same"):
                w_model = cfg.models_writer
                r_model = cfg.models_writer if system == "proposed_same" else cfg.models_reference
                res, final_state = run_graph(
                    cfg, llm,
                    task_id=problem.task_id, spec=problem.spec, entry_point=problem.entry_point,
                    code_under_test=code,
                    writer_model=w_model, reference_model=r_model,
                    variant=variant
                )
            elif system == "b1":
                res = run_b1(cfg, llm, problem.task_id, problem.spec, problem.entry_point, code, cfg.models_writer, variant)
                final_state = {"outcomes": [], "suite": []}
            elif system == "b2":
                res = run_b2(cfg, llm, problem.task_id, problem.spec, problem.entry_point, code, cfg.models_writer, variant)
                final_state = {"outcomes": [], "suite": []}
            elapsed = time.time() - t0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Defect Flagged?", "⚠️ YES (BUG)" if res.flagged else "✅ NO (CLEAN)")
        c2.metric("Trusted Test Cases", f"{res.n_trusted}/{res.n_cases}")
        c3.metric("Suspected Violations", res.n_suspected)
        c4.metric("LLM API Calls", res.calls)
        st.caption(f"⏱️ Latency: {elapsed:.2f}s  |  Tokens Consumed: {res.tokens}")

        if system in ("proposed", "proposed_same"):
            st.subheader("Synthesized Independent Reference Implementation")
            st.code(final_state.get("reference_code", "# None generated"), language="python")
            st.subheader("Audited Test Suite & Consensus Verdicts")
            suite = final_state.get("suite", [])
            outcomes = final_state.get("outcomes", [])
            render_case_outcomes(outcomes, suite)

def tab_results():
    st.header("📊 Experimental Evaluation Analytics")
    raw_dir = ROOT / cfg.results_dir / "raw"
    if not raw_dir.exists() or not list(raw_dir.glob("*.jsonl")):
        st.warning("No experiment records found in results/raw/. Run `python scripts/03_run_experiments.py` first.")
        return
    records = []
    for f in sorted(raw_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line.strip()))
                except Exception:
                    pass
    if not records:
        st.warning("Records files are currently empty.")
        return
    import pandas as pd
    df = pd.DataFrame(records)
    st.subheader("Execution Matrix Records")
    st.dataframe(df, use_container_width=True)

    st.subheader("Comparative Benchmark Performance")
    agg = df.groupby(["system", "variant"]).agg(
        total_runs=("task_id", "count"),
        flagged_count=("flagged", "sum"),
        avg_calls=("calls", "mean"),
        avg_latency=("seconds", "mean")
    ).reset_index()
    st.dataframe(agg, use_container_width=True)

    fig_dir = ROOT / cfg.results_dir / "figures"
    if fig_dir.exists():
        st.subheader("Publication-Quality Evaluation Figures")
        cols = st.columns(3)
        figs = sorted(fig_dir.glob("*.png"))
        for i, f in enumerate(figs):
            with cols[i % 3]:
                st.image(str(f), caption=f.name)

def tab_about():
    st.header("📖 System Architecture & Course Documentation")
    st.markdown("""
### Course Details
- **Course**: 2026-27 Odd - 22MDCEL11 AI Systems Engineering for Agentic Workflows Laboratory CAT II Project
- **Department**: Department of Computing - Decision and Computing Sciences
- **Institution**: Coimbatore Institute of Technology, Coimbatore - 14

### Problem Statement & Solution Overview
In autonomous software engineering, validating generated or modified code without human-written unit tests suffers from the **test oracle problem** and **test hallucination**. Single-agent LLMs incorrectly flag correct code as defective (false alarm rate > 30%).

**SpecOracle** solves this by establishing a multi-agent consensus verification oracle:
1. **Test Writer Agent**: Formulates input test cases solely by reasoning through the natural language specification.
2. **Reference Implementer Agent**: Synthesizes an independent reference solution using standard libraries.
3. **Consensus Auditor**: Validates agreement ($E = R$) inside a sandboxed runner. Test cases that disagree are pruned. If an implementation under test contradicts a trusted case ($E = R \neq C$), a bug is confirmed.
    """)

def main():
    st.title("🛡️ SpecOracle: Autonomous Agentic Code Verification")
    st.caption(f"Writer Architecture: `{cfg.models_writer}` | Reference Architecture: `{cfg.models_reference}`")
    tabs = st.tabs(["🚀 Live Verification", "📊 Benchmark Analytics", "📖 Documentation"])
    with tabs[0]:
        tab_run_single()
    with tabs[1]:
        tab_results()
    with tabs[2]:
        tab_about()

if __name__ == "__main__":
    main()
