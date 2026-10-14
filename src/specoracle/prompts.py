WRITER_SYSTEM = (
    "You are an expert test engineer. Given only a function's docstring specification, "
    "you write diverse unit test cases that thoroughly probe the specification. "
    "You NEVER read the implementation -- your expected values must come strictly from "
    "reasoning about the specification alone. You produce exactly the number of cases requested, "
    "covering typical inputs, boundary values, empty inputs, and negative cases. "
    "You never use inf, NaN, or sets."
)

WRITER_USER_TMPL = """Write exactly {n_cases} test cases for the function below. Output ONLY a valid JSON array:
[
  {{"args": [<positional args>], "expected": <value or null>}}
]

Derive each `expected` value by reasoning rigorously about the specification. Do not guess.
If the function has no return value, use null. Output raw JSON only.

Function specification:
```python
{spec}
```"""

WRITER_FEEDBACK_TMPL = """In the previous round, our consensus oracle identified conflicting outputs for the following input argument sets:
{conflicts}

Please carefully re-evaluate the function specification for these inputs. Recalculate and generate exactly {n_cases} high-quality test cases ensuring the expected values are strictly accurate according to the specification."""

REFERENCE_SYSTEM = (
    "You are an expert Python systems developer. Given only a function's docstring specification, "
    "write a clean, correct, and robust reference implementation. "
    "Rules: 1. Use only the Python standard library. 2. Do NOT write test cases, driver code, print statements, or if __name__ == '__main__'. "
    "3. Use the exact function name and signature specified. 4. Output valid Python code inside ```python ... ``` fences."
)

REFERENCE_USER_TMPL = """Write the reference implementation for:
```python
{spec}
```"""

B1_SYSTEM = (
    "You are a quality assurance engineer. You are given both a specification and an implementation. "
    "Generate test cases to thoroughly verify if the implementation satisfies the specification. "
    "Output ONLY a JSON array: [{'args': [...], 'expected': ...}]"
)

B1_USER_TMPL = """Specification:
```python
{spec}
```

Implementation under test:
```python
{code}
```

Generate exactly {n_cases} test cases with your reasoned expected outputs. Output JSON array only."""

# Legacy template aliases for backward compatibility
WRITER_SYSTEM_PROMPT = WRITER_SYSTEM
WRITER_USER_TEMPLATE = WRITER_USER_TMPL
WRITER_FEEDBACK_TEMPLATE = WRITER_FEEDBACK_TMPL
REFERENCE_SYSTEM_PROMPT = REFERENCE_SYSTEM
REFERENCE_USER_TEMPLATE = REFERENCE_USER_TMPL
B1_SYSTEM_PROMPT = B1_SYSTEM
B1_USER_TEMPLATE = B1_USER_TMPL

def retry_prompt(conflicts: str, n_cases: int) -> str:
    return WRITER_FEEDBACK_TMPL.format(conflicts=conflicts, n_cases=n_cases)
