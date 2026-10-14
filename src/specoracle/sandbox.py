import sys
import os
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from .config import Config

RUNNER_SCRIPT = Path(__file__).resolve().parent / "_runner.py"

def run_cases_batch(
    code: str,
    entry_point: str,
    arg_lists: List[List[Any]],
    timeout: int = 15,
    memory_mb: int = 512,
    python_bin: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Run all test cases in a single subprocess batch."""
    python_exec = python_bin if python_bin else sys.executable
    payload = {
        "code": code,
        "entry_point": entry_point,
        "cases": [{"args": args} for args in arg_lists],
        "memory_mb": memory_mb
    }
    input_str = json.dumps(payload)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(sys.path)

    try:
        proc = subprocess.run(
            [python_exec, "-I", str(RUNNER_SCRIPT)],
            input=input_str,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
        else:
            err = proc.stderr.strip() or "Runner process exited with non-zero code"
            return [{"status": "error", "error": err} for _ in arg_lists]
    except subprocess.TimeoutExpired:
        return [{"status": "timeout", "error": f"Execution timed out after {timeout}s"} for _ in arg_lists]
    except Exception as e:
        return [{"status": "error", "error": str(e)} for _ in arg_lists]

def run_single_case(
    code: str,
    entry_point: str,
    args: List[Any],
    case_timeout: int = 5,
    memory_mb: int = 512,
    python_bin: Optional[str] = None
) -> Dict[str, Any]:
    """Run an isolated single test case to pinpoint timeouts/crashes."""
    res = run_cases_batch(code, entry_point, [args], timeout=case_timeout, memory_mb=memory_mb, python_bin=python_bin)
    return res[0] if res else {"status": "error", "error": "Unknown error in single case runner"}

def run_cases(
    code: str,
    entry_point: str,
    arg_lists: List[List[Any]],
    cfg: Optional[Config] = None,
    total_timeout: int = 15,
    case_timeout: int = 5,
    memory_mb: int = 512
) -> List[Dict[str, Any]]:
    """
    Main sandbox execution entrypoint.
    Runs in batch first. If batch times out or encounters fatal process crash,
    falls back to per-case execution to isolate hanging or crashing cases.
    """
    if not arg_lists:
        return []

    if cfg is not None:
        total_timeout = cfg.sandbox.run_timeout_s
        case_timeout = cfg.sandbox.case_timeout_s
        memory_mb = cfg.sandbox.memory_mb
        python_bin = cfg.sandbox.python_bin
    else:
        python_bin = sys.executable

    batch_results = run_cases_batch(code, entry_point, arg_lists, timeout=total_timeout, memory_mb=memory_mb, python_bin=python_bin)
    
    # If the batch timed out or failed completely, fallback to isolating each case
    all_timeout = all(r.get("status") == "timeout" for r in batch_results)
    if all_timeout and len(arg_lists) > 1:
        isolated_results = []
        for args in arg_lists:
            case_res = run_single_case(code, entry_point, args, case_timeout=case_timeout, memory_mb=memory_mb, python_bin=python_bin)
            isolated_results.append(case_res)
        return isolated_results

    return batch_results

def run_official_test(code: str, test_script: str, entry_point: str, cfg: Optional[Config] = None, timeout: int = 10) -> bool:
    """
    Executes standard HumanEval official unit tests in an isolated subprocess.
    Returns True if tests pass without error, False otherwise.
    """
    python_exec = cfg.sandbox.python_bin if cfg else sys.executable
    full_script = f"""
import sys

{code}

{test_script}

if __name__ == '__main__':
    try:
        check({entry_point})
        sys.exit(0)
    except Exception:
        sys.exit(1)
"""
    try:
        proc = subprocess.run(
            [python_exec, "-c", full_script],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.returncode == 0
    except Exception:
        return False
