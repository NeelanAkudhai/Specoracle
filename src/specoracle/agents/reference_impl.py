import ast
from typing import Optional
from ..prompts import REFERENCE_SYSTEM, REFERENCE_USER_TMPL
from ..parsing import extract_code
from ..llm import LLMClient

def write_reference(
    llm: LLMClient,
    spec: str,
    entry_point: str,
    model: str
) -> str:
    """
    Generates an independent reference implementation for the specified function.
    Verifies that the generated code is syntactically valid Python and defines the entry_point.
    """
    messages = [
        {"role": "system", "content": REFERENCE_SYSTEM},
        {"role": "user", "content": REFERENCE_USER_TMPL.format(spec=spec)}
    ]

    llm_res = llm.chat(model=model, messages=messages, temperature=0.0)
    code = extract_code(llm_res.text)

    try:
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        if entry_point in func_names:
            return code
    except Exception:
        pass

    repair_messages = messages + [
        {"role": "assistant", "content": llm_res.text},
        {"role": "user", "content": f"The code must define the function `{entry_point}` using exact syntax without test code. Output valid Python code only."}
    ]
    retry_res = llm.chat(model=model, messages=repair_messages, temperature=0.0)
    retry_code = extract_code(retry_res.text)
    return retry_code
