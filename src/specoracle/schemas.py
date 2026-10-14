from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field
from enum import Enum

class AuditorLabel(str, Enum):
    SUSPECTED_BUG = "SUSPECTED_BUG"
    CONFIRMED_PASS = "CONFIRMED_PASS"
    DROPPED_REF_DISAGREE = "DROPPED_REF_DISAGREE"
    DROPPED_AMBIGUOUS = "DROPPED_AMBIGUOUS"

class TestCase(BaseModel):
    args: List[Any]
    expected: Any

class TestSuite(BaseModel):
    cases: List[TestCase] = Field(default_factory=list)

class CaseOutcome(BaseModel):
    case_idx: int
    args: List[Any]
    expected: Any
    ref_val: Optional[Any] = None
    code_val: Optional[Any] = None
    ref_status: str = "ok"
    code_status: str = "ok"
    label: AuditorLabel
    error: Optional[str] = None

class Problem(BaseModel):
    task_id: str
    entry_point: str
    spec: str
    canonical_code: str
    buggy_code: str
    bug_type: str = "unknown"
    official_test: str = ""

class ProblemResult(BaseModel):
    task_id: str
    system: str
    variant: str  # "buggy" or "canonical"
    flagged: bool
    n_cases: int
    n_trusted: int
    n_suspected: int
    labels: List[str] = Field(default_factory=list)
    calls: int = 0
    tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    bug_type: str = "unknown"

class LLMResult(BaseModel):
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency: float = 0.0
    cached: bool = False
