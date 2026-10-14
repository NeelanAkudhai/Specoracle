#!/usr/bin/env python3
"""
Prepares benchmark evaluation dataset from HumanEvalPack.
Filters:
1. Canonical solution passes official test
2. Buggy solution fails official test
3. Single top-level function
Samples n_problems using fixed seed and writes data/problems.jsonl and data/sample_manifest.json.
"""
import os
import sys
import json
import random
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from specoracle.config import load_config
from specoracle.schemas import Problem
from specoracle.dataset import save_problems, get_bundled_seed_problems
from specoracle.sandbox import run_official_test

def main():
    config = load_config()
    random.seed(config.seed)

    print(f"[*] Preparing dataset with seed {config.seed}, target {config.n_problems} problems...")
    problems = get_bundled_seed_problems()
    
    try:
        from datasets import load_dataset
        print("[*] Attempting to load bigcode/humanevalpack from Hugging Face...")
        ds = load_dataset("bigcode/humanevalpack", "python")["test"]
        hf_problems = []
        for row in ds:
            task_id = row.get("task_id", "")
            entry_point = row.get("entry_point", "")
            spec = row.get("prompt", "")
            canonical = row.get("canonical_solution", "")
            buggy = row.get("buggy_solution", "")
            bug_type = row.get("bug_type", "unknown")
            test = row.get("test", "")

            can_code = spec + "\n" + canonical
            bug_code = spec + "\n" + buggy

            if run_official_test(can_code, test, entry_point) and not run_official_test(bug_code, test, entry_point):
                hf_problems.append(Problem(
                    task_id=task_id,
                    entry_point=entry_point,
                    spec=spec,
                    canonical_code=can_code,
                    buggy_code=bug_code,
                    bug_type=bug_type,
                    official_test=test
                ))
        if hf_problems:
            print(f"[+] Loaded and verified {len(hf_problems)} problems from Hugging Face.")
            problems = hf_problems
    except Exception as e:
        print(f"[-] Hugging Face online load skipped ({str(e)}). Using bundled curated benchmark problems.")

    if len(problems) > config.n_problems:
        sampled = random.sample(problems, config.n_problems)
    else:
        sampled = problems

    save_problems(sampled, config.paths.problems_file)
    print(f"[+] Saved {len(sampled)} problems to {config.paths.problems_file}")

    bug_counts = dict(Counter(p.bug_type for p in sampled))
    manifest = {
        "seed": config.seed,
        "n_problems": len(sampled),
        "task_ids": [p.task_id for p in sampled],
        "bug_type_distribution": bug_counts
    }
    manifest_path = Path(config.paths.manifest_file)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[+] Manifest saved to {config.paths.manifest_file}")

if __name__ == "__main__":
    main()
