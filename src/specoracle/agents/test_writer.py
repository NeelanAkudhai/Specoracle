import json
from typing import Optional, List, Dict, Any
from ..schemas import TestCase, TestSuite
from ..parsing import extract_json
from ..prompts import (
    WRITER_SYSTEM,
    WRITER_USER_TMPL,
    WRITER_FEEDBACK_TMPL,
    B1_SYSTEM,
    B1_USER_TMPL
)
from ..llm import LLMClient

def write_tests(
    llm: LLMClient,
    spec: str,
    n_cases: int,
    model: str,
    feedback: Optional[str] = None,
    code_under_test: Optional[str] = None
) -> TestSuite:
    """
    Generates structured test cases from specification.
    If code_under_test is provided, runs in B1 mode (implementation-aware).
    """
    if code_under_test:
        system_prompt = B1_SYSTEM
        user_prompt = B1_USER_TMPL.format(spec=spec, code=code_under_test, n_cases=n_cases)
    elif feedback:
        system_prompt = WRITER_SYSTEM
        user_prompt = WRITER_FEEDBACK_TMPL.format(conflicts=feedback, n_cases=n_cases)
    else:
        system_prompt = WRITER_SYSTEM
        user_prompt = WRITER_USER_TMPL.format(spec=spec, n_cases=n_cases)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    llm_res = llm.chat(model=model, messages=messages, temperature=0.0)
    parsed = extract_json(llm_res.text)

    # Retry once on invalid JSON with repair message
    if not isinstance(parsed, list):
        repair_messages = messages + [
            {"role": "assistant", "content": llm_res.text},
            {"role": "user", "content": "Your previous response was not a valid JSON array. Please output ONLY the raw JSON array conforming to [{'args': [...], 'expected': ...}]."}
        ]
        retry_res = llm.chat(model=model, messages=repair_messages, temperature=0.0)
        parsed = extract_json(retry_res.text)

    if not isinstance(parsed, list):
        return TestSuite(cases=[])

    cases = []
    seen_args = set()
    for item in parsed:
        if isinstance(item, dict) and "args" in item and "expected" in item:
            args = item["args"]
            if not isinstance(args, list):
                args = [args]
            try:
                args_repr = json.dumps(args, sort_keys=True)
            except Exception:
                args_repr = str(args)
            if args_repr not in seen_args:
                seen_args.add(args_repr)
                cases.append(TestCase(args=args, expected=item["expected"]))

    return TestSuite(cases=cases)
