---
benchmark_case:
  case_id: protocol-dogfood-001
  task_type: schema_change_review
  decision_surface: validation script coordination_mode handling
  route: AFC_MOA
  coordination_mode: moa_synthesis
  direct_estimate_minutes: 60
  coordinator_input_tokens: 1200
  coordinator_output_tokens: 380
  worker_total_tokens: 3200
  synthesis_tokens: 950
  wall_clock_minutes: 18
  repair_rounds: 1
  defects_caught: 2
  defects_missed: 0
  false_positives: 0
  changed_files: 1
  validation_commands:
    - python scripts/validate-agent-inbox.py examples/moa-synthesis-demo
    - python -B examples/fixtures/afc-shared/run-tests.py
  final_verdict: GO
  confidence_before: 0.65
  confidence_after: 0.98
  notes: |
    MOA dogfood on AFC's own validation protocol.
    Synthesis reviewer caught that moa_synthesis mode required section validation.
    Repair round added the required MOA_SYNTHESIS_REQUIRED_SECTIONS constant.
    Cross-check confirmed no regressions in existing MOA examples.
---
# Protocol Dogfood Benchmark Record

Case: MOA validation review of AFC's own schema handling.

## Repair Round 1

- Issue: No deterministic validation for MOA synthesis report sections
- Fix: Added MOA_SYNTHESIS_REQUIRED_SECTIONS constant and validation
- Files changed: scripts/afc_inbox_validation.py (+10 lines)

## Evidence Quality

| Reviewer | Strength | Key Finding |
|----------|----------|-------------|
| ReviewerA | high | Missing section validation could accept incomplete synthesis |
| ReviewerB | high | Validation gap creates silent regression risk for fixtures |
| Synthesis | high | Both findings orthogonal, both fixes required |

## Result
PASS. MOA caught protocol design gap before it became a regression bug.
