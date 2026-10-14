import math
from typing import Any

def _normalize(v: Any) -> Any:
    """Normalize sequences and dicts recursively for clean comparison."""
    if isinstance(v, tuple):
        return [_normalize(x) for x in v]
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    if isinstance(v, dict):
        return {k: _normalize(x) for k, x in v.items()}
    return v

def values_equal(a: Any, b: Any) -> bool:
    """
    Compares two arbitrary Python data structures for semantic equality:
    1. Bool vs Int: strictly checks types so True != 1 and False != 0.
    2. Floats: uses math.isclose with rel_tol=1e-6, abs_tol=1e-9 (and NaN/Inf handling).
    3. Sequences: normalizes tuples and lists to comparable sequences.
    4. Mappings: recursively compares dictionary keys and values.
    5. Sets: compares set membership with deep equality.
    """
    # Strict boolean vs numeric check
    if isinstance(a, bool) or isinstance(b, bool):
        if not (isinstance(a, bool) and isinstance(b, bool)):
            return False
        return a is b

    # Float comparison
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        if isinstance(a, float) or isinstance(b, float):
            try:
                af = float(a)
                bf = float(b)
                if math.isnan(af) and math.isnan(bf):
                    return True
                if math.isinf(af) and math.isinf(bf):
                    return (af > 0) == (bf > 0)
                return math.isclose(af, bf, rel_tol=1e-6, abs_tol=1e-9)
            except (TypeError, ValueError):
                return False
        return a == b

    a = _normalize(a)
    b = _normalize(b)

    # Sequence normalization
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(values_equal(x, y) for x, y in zip(a, b))

    # Dictionary comparison
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(values_equal(a[k], b[k]) for k in a)

    # Set comparison
    if isinstance(a, (set, frozenset)) and isinstance(b, (set, frozenset)):
        if len(a) != len(b):
            return False
        b_remaining = list(b)
        for x in a:
            matched = False
            for idx, y in enumerate(b_remaining):
                if values_equal(x, y):
                    b_remaining.pop(idx)
                    matched = True
                    break
            if not matched:
                return False
        return True

    try:
        return a == b
    except Exception:
        return False
