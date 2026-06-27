---
benchmark_case:
  case_id: semantic-moa-review-001
  task_type: security_review
  decision_surface: input validation schema
  route: AFC_MOA
  coordination_mode: moa_review
  direct_estimate_minutes: 45
  coordinator_input_tokens: 850
  coordinator_output_tokens: 220
  worker_total_tokens: 2400
  synthesis_tokens: 680
  wall_clock_minutes: 12
  repair_rounds: 0
  defects_caught: 3
  defects_missed: 0
  false_positives: 1
  changed_files: 0
  validation_commands:
    - python -m pytest tests/test_validation.py
  final_verdict: PARTIAL
  confidence_before: 0.7
  confidence_after: 0.95
  notes: |
    MOA review caught 3 security-relevant edge cases that direct review missed.
    One false positive about regex performance was discarded during synthesis.
    Independent reviews agreed on 2 critical issues, disagreed on 1.
    Synthesis resolved disagreement by cross-referencing with threat model docs.
---
# Semantic MOA Review Benchmark Record

Case: Security review of input validation schema.

## Defects Found

| ID | Severity | Found By | Description |
|----|----------|----------|-------------|
| D1 | critical | Both | Missing length constraint on user_id field |
| D2 | high | ReviewerA | Regex catastrophic backtracking vector |
| D3 | medium | ReviewerB | Email validation allows local-only domains |

## False Positives

ReviewerB flagged "potential performance issue" in phone regex — confirmed not exploitable.

## Result
PASS. MOA improved confidence from 0.7 to 0.95. Independent reviewers caught issues direct execution would have missed.
