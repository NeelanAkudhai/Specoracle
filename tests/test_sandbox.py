import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from specoracle.sandbox import run_cases, run_official_test

def test_sandbox_normal_execution():
    code = """
def add(a, b):
    return a + b
"""
    res = run_cases(code, "add", [[1, 2], [10, -5], [0, 0]])
    assert len(res) == 3
    assert res[0]["status"] == "ok" and res[0]["value"] == 3
    assert res[1]["status"] == "ok" and res[1]["value"] == 5
    assert res[2]["status"] == "ok" and res[2]["value"] == 0

def test_sandbox_exception_handling():
    code = """
def bad_div(a, b):
    return a // b
"""
    res = run_cases(code, "bad_div", [[10, 0]])
    assert len(res) == 1
    assert res[0]["status"] == "error"
    assert "ZeroDivisionError" in res[0]["error"]

def test_sandbox_timeout_handling():
    code = """
def hang_fn(x):
    while True:
        pass
    return x
"""
    res = run_cases(code, "hang_fn", [[42]], total_timeout=2, case_timeout=1)
    assert len(res) == 1
    assert res[0]["status"] in ("timeout", "error")

def test_sandbox_stdout_isolation():
    code = """
def noisy_fn(x):
    print("THIS SHOULD NOT CORRUPT JSON OUTPUT!")
    return x * 2
"""
    res = run_cases(code, "noisy_fn", [[21]])
    assert len(res) == 1
    assert res[0]["status"] == "ok"
    assert res[0]["value"] == 42

def test_sandbox_mutation_isolation():
    code = """
def mutating_fn(lst):
    lst.append(999)
    return len(lst)
"""
    args = [1, 2, 3]
    res = run_cases(code, "mutating_fn", [[args], [args]])
    assert len(res) == 2
    assert res[0]["value"] == 4
    assert res[1]["value"] == 4

def test_official_test_pass_and_fail():
    code_pass = "def add(a, b):\n    return a + b\n"
    code_fail = "def add(a, b):\n    return a * b\n"
    test = "def check(fn):\n    assert fn(2, 3) == 5\n    assert fn(-1, 1) == 0\n"
    assert run_official_test(code_pass, test, "add")
    assert not run_official_test(code_fail, test, "add")
