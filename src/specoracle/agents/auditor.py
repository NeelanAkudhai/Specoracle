from typing import List, Dict, Any, Tuple
from ..schemas import TestCase, TestSuite, CaseOutcome, AuditorLabel
from ..compare import values_equal

def label_case(
    expected: Any,
    ref_out: Dict[str, Any],
    code_out: Dict[str, Any]
) -> Tuple[str, bool]:
    """
    Label an individual case outcome according to the consensus matrix.
    Returns (label_str, is_trusted).
    """
    r_ok = (ref_out.get("status") == "ok")
    c_ok = (code_out.get("status") == "ok")
    r_val = ref_out.get("value")
    c_val = code_out.get("value")

    if r_ok and values_equal(expected, r_val):
        # Trusted case
        if c_ok and values_equal(expected, c_val):
            return "CONFIRMED_PASS", True
        else:
            return "SUSPECTED_BUG", True
    elif r_ok and not values_equal(expected, r_val) and c_ok and values_equal(expected, c_val):
        return "DROPPED_REF_DISAGREE", False
    else:
        return "DROPPED_AMBIGUOUS", False

def audit_problem(
    suite: TestSuite | List[TestCase],
    ref_outputs: List[Dict[str, Any]],
    code_outputs: List[Dict[str, Any]]
) -> List[CaseOutcome]:
    """
    Deterministic consensus auditor.
    Evaluates each test case using the consensus matrix:
    E: Writer Expected Value
    R: Reference Output
    C: Code Under Test Output
    """
    cases = suite.cases if isinstance(suite, TestSuite) else suite
    outcomes: List[CaseOutcome] = []
    
    n = min(len(cases), len(ref_outputs), len(code_outputs))
    for i in range(n):
        tc = cases[i]
        r_out = ref_outputs[i]
        c_out = code_outputs[i]

        label_str, is_trusted = label_case(tc.expected, r_out, c_out)
        label = AuditorLabel(label_str)

        outcomes.append(CaseOutcome(
            case_idx=i,
            args=tc.args,
            expected=tc.expected,
            ref_val=r_out.get("value"),
            code_val=c_out.get("value"),
            ref_status=r_out.get("status", "unknown"),
            code_status=c_out.get("status", "unknown"),
            label=label,
            error=c_out.get("error") if c_out.get("status") != "ok" else None
        ))

    return outcomes

# Legacy alias
audit = audit_problem
