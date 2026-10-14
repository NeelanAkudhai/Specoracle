#!/usr/bin/env python3
"""Generates reports, tables, figures, and error analysis from raw benchmark results."""
import sys
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from specoracle.config import load_config
from specoracle.schemas import ProblemResult
from specoracle.report import generate_tables, generate_figures, generate_error_analysis

def main():
    config = load_config()
    raw_dir = Path(config.paths.raw_results_dir)
    
    system_results = defaultdict(list)
    for f in raw_dir.glob("*.jsonl"):
        sys_name = f.stem
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        data = json.loads(line)
                        system_results[sys_name].append(ProblemResult(**data))
                    except Exception:
                        pass

    if not system_results:
        print("[!] No raw results found in results/raw/. Please run scripts/03_run_experiments.py first.")
        return

    print(f"[*] Aggregating results for systems: {list(system_results.keys())}")
    generate_tables(system_results, config.paths.tables_dir)
    print(f"[+] Tables written to {config.paths.tables_dir}")

    generate_figures(system_results, config.paths.figures_dir)
    print(f"[+] Figures written to {config.paths.figures_dir}")

    generate_error_analysis(system_results, config.paths.error_analysis)
    print(f"[+] Error analysis written to {config.paths.error_analysis}")

if __name__ == "__main__":
    main()
