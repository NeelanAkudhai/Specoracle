#!/usr/bin/env python3
"""
Executes the full evaluation matrix across:
Systems: [b1, b2, proposed_same, proposed]
Variants: [buggy, canonical]
Problems: dataset loaded from data/problems.jsonl
Saves raw jsonl runs to results/raw/<system>.jsonl with resume support.
"""
import os
import sys
import json
from pathlib import Path
from typing import Set

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from specoracle.config import load_config
from specoracle.dataset import load_problems, get_bundled_seed_problems
from specoracle.llm import LLMClient
from specoracle.baselines import (
    run_baseline_b1,
    run_baseline_b2,
    run_proposed_same,
    run_proposed_cross
)

def get_completed_keys(file_path: Path) -> Set[str]:
    keys = set()
    if file_path.is_file():
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        d = json.loads(line)
                        keys.add(f"{d['task_id']}_{d['variant']}")
                    except Exception:
                        pass
    return keys

def main():
    config = load_config()
    problems = load_problems(config.paths.problems_file)
    if not problems:
        print("[!] No problems found in file. Using bundled seed problems.")
        problems = get_bundled_seed_problems()

    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    use_mock = not bool(api_key)
    if use_mock:
        print("[*] No API key detected. Running in deterministic mock mode.")
    else:
        print("[*] Live inference enabled via configured API key.")

    llm = LLMClient(
        base_url=config.base_url,
        api_key=api_key,
        cache_db=config.paths.cache_db,
        rpm=config.rpm,
        mock=use_mock
    )

    systems = ["b1", "b2", "proposed_same", "proposed"]
    variants = ["buggy", "canonical"]
    raw_dir = Path(config.paths.raw_results_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting benchmark matrix across {len(systems)} systems, {len(problems)} problems, {len(variants)} variants...")

    for sys_name in systems:
        out_file = raw_dir / f"{sys_name}.jsonl"
        completed = get_completed_keys(out_file)
        
        with open(out_file, "a", encoding="utf-8") as f:
            for prob in problems:
                for variant in variants:
                    key = f"{prob.task_id}_{variant}"
                    if key in completed:
                        continue
                    
                    if sys_name == "b1":
                        res = run_baseline_b1(prob, variant, llm, config, model=config.models_writer)
                    elif sys_name == "b2":
                        res = run_baseline_b2(prob, variant, llm, config, model=config.models_writer)
                    elif sys_name == "proposed_same":
                        res = run_proposed_same(prob, variant, llm, config)
                    elif sys_name == "proposed":
                        res = run_proposed_cross(prob, variant, llm, config)

                    f.write(json.dumps(res.dict()) + "\n")
                    f.flush()
                    completed.add(key)
                    print(f"  [{sys_name}] {prob.task_id} ({variant}): Flagged={res.flagged}, Suspected={res.n_suspected}")

    print(f"[+] Benchmark execution complete. Results saved in {raw_dir}")

if __name__ == "__main__":
    main()
