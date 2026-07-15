# Benchmark Cases

Evidence-backed benchmark results for Delegator coordination paths.

## Summary

| Case | Route | Coordination Mode | Coordinator Time vs Direct | Defects Caught | Would Repeat |
| --- | --- | --- | --- | --- | --- |
| [001: Tiny Fix](case-001-tiny-fix-direct.md) | DIRECT | direct | 50% faster | 0 | No — task too small |
| [002: Docs Review](case-002-docs-review-lite.md) | LITE | lite-single-worker | 70% of direct time | 1 | Yes |
| [003: Multi-Worker Optimization](case-003-multi-worker-optimization.md) | FULL | multi-parallel-worker | 40% of direct time | 2 | Yes |
| [004: MOA Schema Review](case-004-moa-review-bug-catch.md) | FULL | moa-parallel-review | 60% of direct time | 1 | Yes — high risk tasks |
| [005: Delegation Loss](case-005-delegation-loss.md) | FULL (attempted) | multi-parallel-worker | 150% of direct time | 0 | No — tightly coupled work |
| [006: CAL Boundary Crossing](case-006-cal-boundary.md) | FULL | mixed-mode-cal2-to-cal3 | 45% of direct time | 1 | Yes — boundary is safe |

## Key Findings

1. **DIRECT is always best for tiny tasks.** Any task < 5 estimated minutes should stay direct. The routing gate correctly enforces this.

2. **LITE mode is excellent for single-worker documentation.** Low overhead, good results, no inbox bloat.

3. **FULL mode pays off for parallel work.** 3+ independent workstreams show clear wall-clock time reduction.

4. **MOA review is worth it for schema and security.** The caught defect in Case 004 justified the coordination overhead.

5. **Schema-only repairs are rare.** All 4 cases had zero schema-only repair rounds, indicating the current validation is working well.

## Running Benchmarks

Use the existing fixture runners:
```bash
# Run all fixtures
python -B examples/fixtures/run-all-fixtures.py

# Run specific feature tests
python -B examples/fixtures/afc-snapshot/run-tests.py
```

## Adding New Cases

1. Copy `TEMPLATE_CASE.md` (when created) or follow the format of existing cases
2. Include all metrics from the burden budget
3. Be honest about failures — they are the most valuable data points
4. Include lessons learned and whether you would use Delegator again for similar work
5. Do NOT publish model rankings or specific model names

## Publication Rules

- All case data is safe for public export
- No model rankings are published
- No private paths or secrets
- Negative cases are included and valued
- **Cases 005 and 006 are synthetic calibration cases**, not full measured benchmarks — they document important boundary conditions and anti-patterns
