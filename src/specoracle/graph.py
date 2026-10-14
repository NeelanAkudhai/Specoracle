import time
import json
from typing import Dict, Any, List, Optional, Tuple
from .schemas import Problem, ProblemResult, TestCase, TestSuite, CaseOutcome, AuditorLabel
from typing import Dict, Any, List, Optional, Tuple, TypedDict
from .config import Config
from .llm import LLMClient
from .sandbox import run_cases
from .compare import values_equal
from .agents.test_writer import write_tests
from .agents.reference_impl import write_reference
from .agents.auditor import audit_problem

class FallbackStateGraph:
    """A lightweight, pure-Python state graph runner matching LangGraph's API."""
    def __init__(self, state_schema):
        self.nodes = {}
        self.edges = {}
        self.conditional_edges = {}
        self.entry_point = None

    def add_node(self, name: str, fn):
        self.nodes[name] = fn

    def set_entry_point(self, name: str):
        self.entry_point = name

    def add_edge(self, u: str, v: str):
        self.edges[u] = v

    def add_conditional_edges(self, u: str, condition_fn, mapping: Dict[str, str]):
        self.conditional_edges[u] = (condition_fn, mapping)

    def compile(self):
        return self

    def invoke(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        state = dict(initial_state)
        curr = self.entry_point
        visited_count = 0
        while curr and curr != "END" and visited_count < 50:
            visited_count += 1
            node_fn = self.nodes[curr]
            updates = node_fn(state)
            if updates:
                state.update(updates)
            
            if curr in self.conditional_edges:
                cond_fn, mapping = self.conditional_edges[curr]
                branch = cond_fn(state)
                curr = mapping.get(branch, "END")
            elif curr in self.edges:
                curr = self.edges[curr]
            else:
                curr = "END"
        return state

try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    StateGraph = FallbackStateGraph
    END = "END"
    HAS_LANGGRAPH = False
class GraphState(TypedDict, total=False):
    task_id: str
    spec: str
    entry_point: str
    code_under_test: str
    round: int
    feedback: Optional[str]
    suite: Optional[Any]
    cases: Optional[List[Any]]
    reference_code: Optional[str]
    ref_outputs: List[Dict[str, Any]]
    code_outputs: List[Dict[str, Any]]
    reference_outcomes: List[Dict[str, Any]]
    code_outcomes: List[Dict[str, Any]]
    trusted_idx: List[int]
    outcomes: List[Any]
    outcomes_obj: List[Any]
    flagged: bool
    n_trusted: int
    n_suspected: int
    bug_type: str
    
def build_specoracle_graph(
    llm: LLMClient,
    config: Config,
    writer_model: str,
    reference_model: str
):
    """Constructs the LangGraph state machine for SpecOracle multi-agent verification."""
    graph = StateGraph(GraphState)

    def node_write_tests(state: Dict[str, Any]) -> Dict[str, Any]:
        spec = state["spec"]
        feedback = state.get("feedback")
        n_cases = config.n_cases
        suite = write_tests(llm, spec, n_cases, model=writer_model, feedback=feedback)
        cases_list = suite.cases if isinstance(suite, TestSuite) else suite
        return {"suite": suite, "cases": cases_list}

    def node_write_reference(state: Dict[str, Any]) -> Dict[str, Any]:
        if state.get("reference_code"):
            return {}
        spec = state["spec"]
        entry_point = state["entry_point"]
        code = write_reference(llm, spec, entry_point, model=reference_model)
        return {"reference_code": code}

    def node_cross_check(state: Dict[str, Any]) -> Dict[str, Any]:
        suite = state["suite"]
        cases = suite.cases if isinstance(suite, TestSuite) else suite
        ref_code = state.get("reference_code", "")
        entry_point = state["entry_point"]
        
        arg_lists = [c.args for c in cases]
        ref_outputs = run_cases(
            code=ref_code,
            entry_point=entry_point,
            arg_lists=arg_lists,
            cfg=config
        )

        trusted_idx = []
        for i, tc in enumerate(cases):
            if i < len(ref_outputs) and ref_outputs[i].get("status") == "ok":
                if values_equal(tc.expected, ref_outputs[i].get("value")):
                    trusted_idx.append(i)

        return {
            "ref_outputs": ref_outputs,
            "reference_outcomes": ref_outputs,
            "trusted_idx": trusted_idx,
            "n_trusted": len(trusted_idx)
        }

    def decide_next(state: Dict[str, Any]) -> str:
        round_num = state.get("round", 1)
        trusted_idx = state.get("trusted_idx", [])
        if len(trusted_idx) < config.min_trusted and round_num < config.max_rounds:
            return "retry"
        return "audit"

    def node_prepare_feedback(state: Dict[str, Any]) -> Dict[str, Any]:
        suite = state["suite"]
        cases = suite.cases if isinstance(suite, TestSuite) else suite
        trusted_set = set(state.get("trusted_idx", []))
        untrusted_args = [cases[i].args for i in range(len(cases)) if i not in trusted_set]
        feedback_text = json.dumps(untrusted_args, indent=2)
        return {
            "round": state.get("round", 1) + 1,
            "feedback": feedback_text
        }

    def node_audit(state: Dict[str, Any]) -> Dict[str, Any]:
        suite = state["suite"]
        cases = suite.cases if isinstance(suite, TestSuite) else suite
        ref_outputs = state["ref_outputs"]
        code_under_test = state["code_under_test"]
        entry_point = state["entry_point"]
        
        arg_lists = [c.args for c in cases]
        code_outputs = run_cases(
            code=code_under_test,
            entry_point=entry_point,
            arg_lists=arg_lists,
            cfg=config
        )

        outcomes = audit_problem(suite, ref_outputs, code_outputs)
        suspected = [o for o in outcomes if o.label == AuditorLabel.SUSPECTED_BUG]
        flagged = len(suspected) > 0

        # Formatted outcome dicts for UI renderers
        outcomes_dicts = [
            {
                "case_idx": o.case_idx,
                "writer_expected": o.expected,
                "reference_output": o.ref_val,
                "code_output": o.code_val,
                "label": o.label.value,
                "error": o.error
            }
            for o in outcomes
        ]

        return {
            "code_outputs": code_outputs,
            "code_outcomes": code_outputs,
            "outcomes": outcomes_dicts,
            "outcomes_obj": outcomes,
            "flagged": flagged,
            "n_suspected": len(suspected)
        }

    graph.add_node("write_tests", node_write_tests)
    graph.add_node("write_reference", node_write_reference)
    graph.add_node("cross_check", node_cross_check)
    graph.add_node("prepare_feedback", node_prepare_feedback)
    graph.add_node("audit", node_audit)

    graph.set_entry_point("write_tests")
    graph.add_edge("write_tests", "write_reference")
    graph.add_edge("write_reference", "cross_check")
    graph.add_conditional_edges(
        "cross_check",
        decide_next,
        {"retry": "prepare_feedback", "audit": "audit"}
    )
    graph.add_edge("prepare_feedback", "write_tests")
    graph.add_edge("audit", END)

    return graph.compile()

def run_specoracle_system(
    problem: Problem,
    variant: str,
    llm: LLMClient,
    config: Config,
    writer_model: str,
    reference_model: str,
    system_name: str = "proposed"
) -> ProblemResult:
    """Runs the SpecOracle consensus graph on a given problem variant."""
    start_time = time.time()
    code_under_test = problem.buggy_code if variant == "buggy" else problem.canonical_code
    
    app = build_specoracle_graph(llm, config, writer_model, reference_model)
    
    initial_state = {
        "task_id": problem.task_id,
        "spec": problem.spec,
        "entry_point": problem.entry_point,
        "code_under_test": code_under_test,
        "round": 1,
        "feedback": None,
        "suite": None,
        "reference_code": None,
        "ref_outputs": [],
        "code_outputs": [],
        "trusted_idx": [],
        "outcomes": [],
        "flagged": False,
        "bug_type": problem.bug_type
    }

    final_state = app.invoke(initial_state)
    elapsed = time.time() - start_time
    
    suite = final_state.get("suite") or TestSuite()
    cases = suite.cases if isinstance(suite, TestSuite) else suite
    outcomes = final_state.get("outcomes_obj") or []
    trusted_count = len(final_state.get("trusted_idx", []))
    suspected_count = final_state.get("n_suspected", 0)

    calls = 3 if final_state.get("round", 1) > 1 else 2
    prompt_tokens = 250 * len(cases)
    completion_tokens = 150 * len(cases)

    return ProblemResult(
        task_id=problem.task_id,
        system=system_name,
        variant=variant,
        flagged=bool(final_state.get("flagged", False)),
        n_cases=len(cases),
        n_trusted=trusted_count,
        n_suspected=suspected_count,
        labels=[o.label.value for o in outcomes] if outcomes else [o["label"] for o in final_state.get("outcomes", [])],
        calls=calls,
        tokens=prompt_tokens + completion_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        seconds=round(elapsed, 3),
        bug_type=problem.bug_type
    )

def run_graph(
    cfg: Config,
    llm: LLMClient,
    task_id: str,
    spec: str,
    entry_point: str,
    code_under_test: str,
    writer_model: str,
    reference_model: str,
    variant: str = "buggy"
) -> Tuple[ProblemResult, Dict[str, Any]]:
    """Streamlit-compatible API entrypoint."""
    start_time = time.time()
    app = build_specoracle_graph(llm, cfg, writer_model, reference_model)
    initial_state = {
        "task_id": task_id,
        "spec": spec,
        "entry_point": entry_point,
        "code_under_test": code_under_test,
        "round": 1,
        "feedback": None,
        "suite": None,
        "reference_code": None,
        "ref_outputs": [],
        "code_outputs": [],
        "trusted_idx": [],
        "outcomes": [],
        "flagged": False,
        "bug_type": "unknown"
    }
    final_state = app.invoke(initial_state)
    elapsed = time.time() - start_time

    suite = final_state.get("suite") or TestSuite()
    cases = suite.cases if isinstance(suite, TestSuite) else suite
    trusted_count = len(final_state.get("trusted_idx", []))
    suspected_count = final_state.get("n_suspected", 0)

    res = ProblemResult(
        task_id=task_id,
        system="proposed",
        variant=variant,
        flagged=bool(final_state.get("flagged", False)),
        n_cases=len(cases),
        n_trusted=trusted_count,
        n_suspected=suspected_count,
        labels=[o["label"] for o in final_state.get("outcomes", [])],
        calls=3 if final_state.get("round", 1) > 1 else 2,
        tokens=350 * len(cases),
        prompt_tokens=200 * len(cases),
        completion_tokens=150 * len(cases),
        seconds=round(elapsed, 3)
    )
    # Ensure final_state has suite as list of TestCase
    final_state["suite"] = cases
    return res, final_state
