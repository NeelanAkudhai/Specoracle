import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from specoracle.schemas import TestCase, TestSuite, AuditorLabel
from specoracle.agents.auditor import audit_problem, label_case

def test_label_case_matrix():
    label, trusted = label_case(5, {"status": "ok", "value": 5}, {"status": "ok", "value": 5})
    assert label == "CONFIRMED_PASS" and trusted is True

    label, trusted = label_case(5, {"status": "ok", "value": 5}, {"status": "ok", "value": 6})
    assert label == "SUSPECTED_BUG" and trusted is True

    label, trusted = label_case(5, {"status": "ok", "value": 6}, {"status": "ok", "value": 5})
    assert label == "DROPPED_REF_DISAGREE" and trusted is False

    label, trusted = label_case(5, {"status": "ok", "value": 6}, {"status": "ok", "value": 7})
    assert label == "DROPPED_AMBIGUOUS" and trusted is False

    # Crash on code when reference matches
    label, trusted = label_case(5, {"status": "ok", "value": 5}, {"status": "error", "error": "ZeroDivisionError"})
    assert label == "SUSPECTED_BUG" and trusted is True

    # Crash on reference
    label, trusted = label_case(5, {"status": "error", "error": "SyntaxError"}, {"status": "ok", "value": 5})
    assert label == "DROPPED_AMBIGUOUS" and trusted is False

def test_auditor_full():
    suite = TestSuite(cases=[
        TestCase(args=[1], expected=10),
        TestCase(args=[2], expected=20),
        TestCase(args=[3], expected=30),
        TestCase(args=[4], expected=40),
    ])
    ref_outputs = [
        {"status": "ok", "value": 10},
        {"status": "ok", "value": 20},
        {"status": "ok", "value": 99},
        {"status": "ok", "value": 50},
    ]
    code_outputs = [
        {"status": "ok", "value": 99},
        {"status": "ok", "value": 20},
        {"status": "ok", "value": 30},
        {"status": "ok", "value": 60},
    ]
    outcomes = audit_problem(suite, ref_outputs, code_outputs)
    assert len(outcomes) == 4
    assert outcomes[0].label == AuditorLabel.SUSPECTED_BUG
    assert outcomes[1].label == AuditorLabel.CONFIRMED_PASS
    assert outcomes[2].label == AuditorLabel.DROPPED_REF_DISAGREE
    assert outcomes[3].label == AuditorLabel.DROPPED_AMBIGUOUS
