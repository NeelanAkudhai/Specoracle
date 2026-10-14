import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Union, Optional
import pandas as pd
from .schemas import ProblemResult

def wilson_interval(successes: int, total: int, confidence: float = 0.95, z: float = 1.96) -> Tuple[float, float]:
    """
    Computes the Wilson score confidence interval for a binomial proportion.
    Returns (lower_bound, upper_bound).
    """
    if total <= 0:
        return 0.0, 0.0
    
    p = successes / total
    denom = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denom
    margin = (z / denom) * math.sqrt((p * (1.0 - p) / total) + (z * z / (4.0 * total * total)))
    
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper

def exact_mcnemar_test(b: int, c: int) -> float:
    """Exact two-sided McNemar test on discordant pairs (b, c)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    try:
        from scipy.stats import binomtest
        res = binomtest(k, n, p=0.5, alternative='two-sided')
        return float(res.pvalue)
    except Exception:
        p_val = 0.0
        for i in range(k + 1):
            p_val += math.comb(n, i) * (0.5 ** n)
        return min(1.0, 2.0 * p_val)

@dataclass
class SystemMetrics:
    system: str
    n_buggy: int
    n_canonical: int
    tp: int
    fn: int
    fp: int
    tn: int
    detection_rate: float
    false_alarm_rate: float
    precision: float
    f1: float
    detection_ci: Tuple[float, float]
    false_alarm_ci: Tuple[float, float]
    trusted_yield: float
    avg_calls: float
    avg_tokens: float
    avg_seconds: float

    def __getitem__(self, item):
        return getattr(self, item)

def compute_system_metrics(data: Union[List[ProblemResult], pd.DataFrame], system: Optional[str] = None) -> Dict[str, Any]:
    """Aggregates performance metrics across buggy and canonical problem variants."""
    if isinstance(data, pd.DataFrame):
        df = data if system is None else data[data["system"] == system]
        buggy = df[df["variant"] == "buggy"]
        canon = df[df["variant"] == "canonical"]
        tp = int((buggy["flagged"] == True).sum())
        fn = int(len(buggy) - tp)
        fp = int((canon["flagged"] == True).sum())
        tn = int(len(canon) - fp)
        n_buggy = len(buggy)
        n_canonical = len(canon)
        avg_calls = float(df["calls"].mean()) if "calls" in df and len(df) else 0.0
        avg_tokens = float(df["tokens"].mean()) if "tokens" in df and len(df) else 0.0
        avg_seconds = float(df["seconds"].mean()) if "seconds" in df and len(df) else 0.0
        avg_cases = float(df["n_cases"].mean()) if "n_cases" in df and len(df) else 1.0
        avg_trusted = float(df["n_trusted"].mean()) if "n_trusted" in df and len(df) else 0.0
    else:
        results = data if system is None else [r for r in data if r.system == system]
        buggy_runs = [r for r in results if r.variant == "buggy"]
        canonical_runs = [r for r in results if r.variant == "canonical"]
        tp = sum(1 for r in buggy_runs if r.flagged)
        fn = len(buggy_runs) - tp
        fp = sum(1 for r in canonical_runs if r.flagged)
        tn = len(canonical_runs) - fp
        n_buggy = len(buggy_runs)
        n_canonical = len(canonical_runs)
        avg_calls = sum(r.calls for r in results) / len(results) if results else 0.0
        avg_tokens = sum(r.tokens for r in results) / len(results) if results else 0.0
        avg_seconds = sum(r.seconds for r in results) / len(results) if results else 0.0
        avg_cases = sum(r.n_cases for r in results) / len(results) if results else 1.0
        avg_trusted = sum(r.n_trusted for r in results) / len(results) if results else 0.0

    det_rate = tp / n_buggy if n_buggy > 0 else 0.0
    fa_rate = fp / n_canonical if n_canonical > 0 else 0.0
    det_low, det_high = wilson_interval(tp, n_buggy)
    fa_low, fa_high = wilson_interval(fp, n_canonical)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2 * precision * det_rate / (precision + det_rate) if (precision + det_rate) > 0 else 0.0
    trusted_yield = avg_trusted / avg_cases if avg_cases > 0 else 0.0

    return {
        "system": system or "system",
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "n_buggy": n_buggy, "n_canonical": n_canonical,
        "detection_rate": det_rate, "detection_ci": (det_low, det_high),
        "false_alarm_rate": fa_rate, "false_alarm_ci": (fa_low, fa_high),
        "precision": precision,
        "f1": f1,
        "trusted_yield": trusted_yield,
        "avg_calls": avg_calls,
        "avg_tokens": avg_tokens,
        "avg_seconds": avg_seconds
    }
