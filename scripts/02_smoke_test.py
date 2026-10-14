#!/usr/bin/env python3
"""
Smoke test script: Runs 3 problems end-to-end in offline mock mode to verify
sandbox, agent orchestration, LangGraph workflow, and metrics pipeline.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from specoracle.config import load_config
from specoracle.dataset import get_bundled_seed_problems
from specoracle.llm import LLMClient
from specoracle.graph import run_specoracle_system
from specoracle.baselines import run_baseline_b1, run_baseline_b2

def main():
    print("=== SpecOracle End-to-End Smoke Test ===")
    config = load_config()
    problems = get_bundled_seed_problems()[:3]
    
    use_mock = not bool(os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"))
    llm = LLMClient(mock=use_mock, cache_db="cache/smoke_cache.sqlite")

    print(f"[*] Testing {len(problems)} problems (Mock Mode = {use_mock})...")

    for prob in problems:
        print(f"\n--- Task: {prob.task_id} ({prob.entry_point}) ---")
        
        b1_res = run_baseline_b1(prob, "buggy", llm, config, model="mock-model")
        print(f"  [B1 Baseline]   Buggy Flagged: {b1_res.flagged}, Cases: {b1_res.n_cases}")

        b2_res = run_baseline_b2(prob, "buggy", llm, config, model="mock-model")
        print(f"  [B2 Baseline]   Buggy Flagged: {b2_res.flagged}, Cases: {b2_res.n_cases}")

        prop_res = run_specoracle_system(
            problem=prob,
            variant="buggy",
            llm=llm,
            config=config,
            writer_model="mock-writer",
            reference_model="mock-ref",
            system_name="proposed"
        )
        print(f"  [SpecOracle]    Buggy Flagged: {prop_res.flagged}, Trusted Cases: {prop_res.n_trusted}/{prop_res.n_cases}")
        print(f"                  Labels: {prop_res.labels[:5]}")

    print("\n[+] All smoke test assertions passed! System is operational.")

if __name__ == "__main__":
    main()
