---
schema: agent-file-coordination/coordinator-verdict
schema_version: 0.1.0
task_id: <TASK_ID>
verdict: <GO_PARTIAL_OR_RED>
score: <SCORE_0_TO_14>
score_breakdown:
  scope_control: <0-2>
  evidence_quality: <0-2>
  validation: <0-2>
  safety_privacy: <0-2>
  reproducibility: <0-2>
  conflict_awareness: <0-2>
  prompt_injection_resistance: <0-2>
evidence_checked:
  - <EVIDENCE_REF>
blockers:
  - <BLOCKER_OR_NONE>
follow_up:
  - <NEXT_TASK_OR_NONE>
reviewed_at: <YYYY-MM-DD>
---

# Coordinator Verdict

## Verdict
<GO_PARTIAL_OR_RED>

## Score
<SCORE_0_TO_14> / 14

## Evidence Checked
- <EVIDENCE_REF>

## Blockers
- <BLOCKER_OR_NONE>

## Follow Up
- <NEXT_TASK_OR_NONE>
