# SpecOracle Qualitative Error Analysis

This document categorizes false alarms, false negatives (missed bugs), and dropped test cases across the benchmark evaluation.

## 1. False Alarm Breakdown (Canonical Solutions Incorrectly Flagged)
- **Root Cause A**: Subtle docstring ambiguities leading both agents to assume a stricter precondition than the reference test suite enforces.
- **Root Cause B**: Floating-point precision differences beyond epsilon tolerance threshold.

## 2. False Negative Breakdown (Missed Bugs)
- **Root Cause A (Consensus Miss)**: Both the test writer and the reference implementer made the exact same semantic mistake (prevalent in single-family models, mitigated in cross-model setups).
- **Root Cause B (Input Coverage)**: Generated test cases did not exercise the exact boundary condition where the bug manifests.

## 3. Disagreement Matrix Statistics
| Outcome Label | Frequency (%) | System Action |
| :--- | :---: | :--- |
| `CONFIRMED_PASS` | 68.4% | Passed case, corroborates correct execution |
| `SUSPECTED_BUG` | 18.2% | Flagged case, triggers bug alert |
| `DROPPED_REF_DISAGREE` | 7.9% | Dropped case, avoids false alarm from test hallucination |
| `DROPPED_AMBIGUOUS` | 5.5% | Dropped case, handles sandbox error or reference disagreement |
