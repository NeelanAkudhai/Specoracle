import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from specoracle.metrics import wilson_interval, exact_mcnemar_test, compute_system_metrics
from specoracle.schemas import ProblemResult

def test_wilson_interval_bounds():
    lo, hi = wilson_interval(10, 10)
    assert 0.5 < lo < 1.0 and hi == 1.0

    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and 0.0 <= hi < 0.5

    lo, hi = wilson_interval(5, 10)
    assert 0.20 < lo < 0.30
    assert 0.70 < hi < 0.80

    lo, hi = wilson_interval(0, 0)
    assert lo == 0.0 and hi == 0.0

def test_exact_mcnemar_test():
    assert exact_mcnemar_test(5, 5) == 1.0
    p_val = exact_mcnemar_test(0, 12)
    assert p_val < 0.01

def test_compute_system_metrics():
    runs = [
        ProblemResult(task_id="1", system="test", variant="buggy", flagged=True, n_cases=5, n_trusted=4, n_suspected=1, labels=[]),
        ProblemResult(task_id="2", system="test", variant="buggy", flagged=False, n_cases=5, n_trusted=4, n_suspected=0, labels=[]),
        ProblemResult(task_id="1", system="test", variant="canonical", flagged=False, n_cases=5, n_trusted=4, n_suspected=0, labels=[]),
        ProblemResult(task_id="2", system="test", variant="canonical", flagged=True, n_cases=5, n_trusted=4, n_suspected=1, labels=[]),
    ]
    m = compute_system_metrics(runs)
    assert m["tp"] == 1 and m["fn"] == 1
    assert m["fp"] == 1 and m["tn"] == 1
    assert m["detection_rate"] == 0.5
    assert m["false_alarm_rate"] == 0.5
    assert m["precision"] == 0.5
