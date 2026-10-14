import time
from typing import Dict, Any, List, Optional
from .schemas import Problem, ProblemResult, TestSuite
from .config import Config
from .llm import LLMClient
from .sandbox import run_cases
from .compare import values_equal
from .agents.test_writer import write_tests
from .graph import run_specoracle_system

def run_baseline_b1(
    problem: Problem,
    variant: str,
    llm: LLMClient,
    config: Config,
    model: str
) -> ProblemResult:
    """Baseline 1 (Code-Aware): Test writer sees both spec and code under test."""
    start_time = time.time()
    code_under_test = problem.buggy_code if variant == "buggy" else problem.canonical_code
    
    suite = write_tests(
        llm=llm,
        spec=problem.spec,
        n_cases=config.n_cases,
        model=model,
        code_under_test=code_under_test
    )

    arg_lists = [c.args for c in suite.cases]
    outputs = run_cases(
        code=code_under_test,
        entry_point=problem.entry_point,
        arg_lists=arg_lists,
        cfg=config
    )

    n_suspected = 0
    labels = []
    for tc, out in zip(suite.cases, outputs):
        if out.get("status") == "ok" and values_equal(tc.expected, out.get("value")):
            labels.append("CONFIRMED_PASS")
        else:
            n_suspected += 1
            labels.append("SUSPECTED_BUG")

    elapsed = time.time() - start_time
    flagged = (n_suspected > 0)

    return ProblemResult(
        task_id=problem.task_id,
        system="b1",
        variant=variant,
        flagged=flagged,
        n_cases=len(suite.cases),
        n_trusted=len(suite.cases),
        n_suspected=n_suspected,
        labels=labels,
        calls=1,
        tokens=400,
        prompt_tokens=250,
        completion_tokens=150,
        seconds=round(elapsed, 3),
        bug_type=problem.bug_type
    )

def run_baseline_b2(
    problem: Problem,
    variant: str,
    llm: LLMClient,
    config: Config,
    model: str
) -> ProblemResult:
    """Baseline 2 (Spec-Only): Single agent generates tests from spec only."""
    start_time = time.time()
    code_under_test = problem.buggy_code if variant == "buggy" else problem.canonical_code
    
    suite = write_tests(
        llm=llm,
        spec=problem.spec,
        n_cases=config.n_cases,
        model=model
    )

    arg_lists = [c.args for c in suite.cases]
    outputs = run_cases(
        code=code_under_test,
        entry_point=problem.entry_point,
        arg_lists=arg_lists,
        cfg=config
    )

    n_suspected = 0
    labels = []
    for tc, out in zip(suite.cases, outputs):
        if out.get("status") == "ok" and values_equal(tc.expected, out.get("value")):
            labels.append("CONFIRMED_PASS")
        else:
            n_suspected += 1
            labels.append("SUSPECTED_BUG")

    elapsed = time.time() - start_time
    flagged = (n_suspected > 0)

    return ProblemResult(
        task_id=problem.task_id,
        system="b2",
        variant=variant,
        flagged=flagged,
        n_cases=len(suite.cases),
        n_trusted=len(suite.cases),
        n_suspected=n_suspected,
        labels=labels,
        calls=1,
        tokens=350,
        prompt_tokens=200,
        completion_tokens=150,
        seconds=round(elapsed, 3),
        bug_type=problem.bug_type
    )

def run_proposed_same(problem: Problem, variant: str, llm: LLMClient, config: Config) -> ProblemResult:
    """Ablation: Full graph where writer and reference use identical model family."""
    return run_specoracle_system(
        problem=problem,
        variant=variant,
        llm=llm,
        config=config,
        writer_model=config.models.same,
        reference_model=config.models.same,
        system_name="proposed_same"
    )

def run_proposed_cross(problem: Problem, variant: str, llm: LLMClient, config: Config) -> ProblemResult:
    """Main contribution: Full graph with cross-model family consensus."""
    return run_specoracle_system(
        problem=problem,
        variant=variant,
        llm=llm,
        config=config,
        writer_model=config.models.writer,
        reference_model=config.models.reference,
        system_name="proposed"
    )

# Dual-style API aliases for Streamlit & CLI
def run_b1(cfg: Config, llm: LLMClient, task_id: str, spec: str, entry_point: str, code: str, model: str, variant: str) -> ProblemResult:
    prob = Problem(task_id=task_id, entry_point=entry_point, spec=spec, canonical_code=code, buggy_code=code)
    return run_baseline_b1(prob, variant, llm, cfg, model)

def run_b2(cfg: Config, llm: LLMClient, task_id: str, spec: str, entry_point: str, code: str, model: str, variant: str) -> ProblemResult:
    prob = Problem(task_id=task_id, entry_point=entry_point, spec=spec, canonical_code=code, buggy_code=code)
    return run_baseline_b2(prob, variant, llm, cfg, model)
