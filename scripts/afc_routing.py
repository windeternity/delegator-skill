#!/usr/bin/env python3
"""Deterministic delegation routing policy shared by AFC tools."""

DIRECT_MINUTES_FOR_FULL = 240
PARALLEL_TOTAL_MINUTES_FOR_FULL = 180
MIN_WORKSTREAM_MINUTES_FOR_FULL = 60
LITE_MINUTES = 15
# MOA (multi-agent / multi-model collaboration) economic floor. Deliberately
# far below the 240-minute token-economy gate: cross-checking substantive work
# across >=2 distinct models is worth it from 20 minutes up. This is a soft
# floor, not a precision scale; the hard gates are the value (A) and feasibility
# (B) layers of the MOA condition in evaluate_route.
MOA_MIN_MINUTES = 20
MAX_FULL_CONTEXT_BYTES = 4 * 1024
MAX_EXPECTED_ROUNDS = 2
# blast_radius tiers. "unknown" is the default and means the coordinator has
# NOT supplied evidence (did not run afc-blast-radius.py). It is a legal value
# but never satisfies moa_value, so the MOA value layer does real filtering
# work instead of being decorative -- a FULL route requires actual evidence.
BLAST_RADIUS_TIERS = ("low", "medium", "high")
BLAST_RADIUS_UNKNOWN = "unknown"

YES_VALUES = {"yes", "true", "1", "approved"}


def as_bool(value):
    return str(value or "").strip().lower() in YES_VALUES


def as_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def normalize_inputs(values):
    estimated = as_int(values.get("estimated_direct_minutes"), -1)
    streams = as_int(values.get("independent_workstreams"), 1)
    smallest = as_int(
        values.get("smallest_workstream_minutes"),
        estimated if streams <= 1 else 0,
    )
    return {
        "estimated_direct_minutes": estimated,
        "independent_workstreams": streams,
        "smallest_workstream_minutes": smallest,
        "specialized_capability": as_bool(values.get("specialized_capability")),
        "high_risk_independent_review": as_bool(
            values.get("high_risk_independent_review")
        ),
        "external_worker_required": as_bool(values.get("external_worker_required")),
        "semantic_change": as_bool(values.get("semantic_change")),
        "expected_rounds": as_int(values.get("expected_rounds"), 1),
        "context_bytes": as_int(values.get("context_bytes"), 0),
        "requested_mode": str(values.get("requested_mode") or "auto").strip().lower(),
        "override": as_bool(values.get("override")),
        "override_reason": str(values.get("override_reason") or "").strip(),
        # MOA inputs. available_distinct_models defaults to 1 so the MOA gate
        # stays dormant unless the coordinator declares its roster (>=2) -- this
        # is the safety valve that prevents the router from collapsing to
        # always-FULL. blast_radius defaults to "unknown" (no evidence supplied);
        # run afc-blast-radius.py and pass the result so the value layer filters.
        "available_distinct_models": as_int(
            values.get("available_distinct_models"), 1
        ),
        "blast_radius": str(values.get("blast_radius") or BLAST_RADIUS_UNKNOWN).strip().lower(),
    }


def validate_inputs(inputs):
    errors = []
    if inputs["estimated_direct_minutes"] < 0:
        errors.append("estimated_direct_minutes must be >= 0")
    if inputs["independent_workstreams"] < 1:
        errors.append("independent_workstreams must be >= 1")
    if inputs["smallest_workstream_minutes"] < 0:
        errors.append("smallest_workstream_minutes must be >= 0")
    if inputs["expected_rounds"] < 1:
        errors.append("expected_rounds must be >= 1")
    if inputs["context_bytes"] < 0:
        errors.append("context_bytes must be >= 0")
    if inputs["available_distinct_models"] < 1:
        errors.append("available_distinct_models must be >= 1")
    if inputs["blast_radius"] not in BLAST_RADIUS_TIERS and inputs["blast_radius"] != BLAST_RADIUS_UNKNOWN:
        errors.append(
            "blast_radius must be one of {} (or omitted for {})".format(
                ", ".join(BLAST_RADIUS_TIERS), BLAST_RADIUS_UNKNOWN
            )
        )
    if inputs["requested_mode"] not in {"auto", "direct", "lite", "full"}:
        errors.append("requested_mode must be auto, direct, lite, or full")
    if inputs["override"] and len(inputs["override_reason"]) < 12:
        errors.append("override_reason must contain at least 12 characters")
    return errors


def evaluate_route(values):
    """Return a JSON-serializable routing decision."""
    inputs = normalize_inputs(values)
    errors = validate_inputs(inputs)
    if errors:
        return {
            "decision": "INVALID",
            "eligible": False,
            "reason_codes": ["INVALID_INPUT"],
            "reasons": errors,
            "inputs": inputs,
        }

    reasons = []
    reason_codes = []

    if inputs["context_bytes"] > MAX_FULL_CONTEXT_BYTES:
        return {
            "decision": "SPLIT",
            "eligible": False,
            "reason_codes": ["CONTEXT_OVER_BUDGET"],
            "reasons": [
                "inline context exceeds {} bytes; use pointers or split the task".format(
                    MAX_FULL_CONTEXT_BYTES
                )
            ],
            "inputs": inputs,
            "max_workers": 0,
        }

    if inputs["expected_rounds"] > MAX_EXPECTED_ROUNDS:
        return {
            "decision": "SPLIT",
            "eligible": False,
            "reason_codes": ["ROUND_BUDGET_EXCEEDED"],
            "reasons": [
                "expected report/verdict rounds exceed {}; tighten or split the task".format(
                    MAX_EXPECTED_ROUNDS
                )
            ],
            "inputs": inputs,
            "max_workers": 0,
        }

    if inputs["requested_mode"] == "direct":
        return {
            "decision": "DIRECT",
            "eligible": True,
            "reason_codes": ["DIRECT_REQUESTED"],
            "reasons": ["direct execution was explicitly requested"],
            "inputs": inputs,
            "max_workers": 0,
        }

    long_running = inputs["estimated_direct_minutes"] >= DIRECT_MINUTES_FOR_FULL
    real_parallel = (
        inputs["independent_workstreams"] >= 2
        and inputs["estimated_direct_minutes"] >= PARALLEL_TOTAL_MINUTES_FOR_FULL
        and inputs["smallest_workstream_minutes"] >= MIN_WORKSTREAM_MINUTES_FOR_FULL
    )
    specialized = inputs["specialized_capability"]
    high_risk = inputs["high_risk_independent_review"]
    # MOA collaboration value gate (three-layer AND):
    #   A value:      substantive semantic change AND non-trivial blast radius
    #   B feasibility: the roster can actually bring >=2 distinct models
    #   C economy:     enough minutes that the coordination tax is worth paying
    # Defaults keep MOA dormant (models=1) unless the coordinator declares a
    # roster, so this never collapses the router into always-FULL on its own.
    moa_value = (
        inputs["semantic_change"]
        and inputs["blast_radius"] in ("medium", "high")
    )
    moa_feasible = inputs["available_distinct_models"] >= 2
    moa_economic = inputs["estimated_direct_minutes"] >= MOA_MIN_MINUTES
    moa_collaboration = moa_value and moa_feasible and moa_economic
    full_eligible = (
        long_running or real_parallel or specialized or high_risk or moa_collaboration
    )

    if long_running:
        reason_codes.append("LONG_RUNNING")
        reasons.append("estimated direct effort is at least four hours")
    if real_parallel:
        reason_codes.append("REAL_PARALLELISM")
        reasons.append("at least two independent workstreams each justify delegation")
    if specialized:
        reason_codes.append("SPECIALIZED_CAPABILITY")
        reasons.append("a required capability is unavailable to the coordinator")
    if high_risk:
        reason_codes.append("HIGH_RISK_REVIEW")
        reasons.append("independent review is justified by risk")
    if moa_collaboration:
        reason_codes.append("MOA_COLLABORATION_VALUE")
        reasons.append(
            "substantive change with non-trivial blast radius is worth "
            "cross-checking across {} distinct models".format(
                inputs["available_distinct_models"]
            )
        )

    if inputs["requested_mode"] == "full" and not full_eligible:
        if inputs["override"]:
            return {
                "decision": "FULL",
                "eligible": True,
                "reason_codes": ["EXPLICIT_OVERRIDE"],
                "reasons": [inputs["override_reason"]],
                "inputs": inputs,
                "max_workers": max(1, min(inputs["independent_workstreams"], 3)),
                "override_used": True,
            }
        return {
            "decision": "DIRECT",
            "eligible": False,
            "reason_codes": ["FULL_NOT_JUSTIFIED"],
            "reasons": [
                "full delegation was requested but no ROI condition was met"
            ],
            "inputs": inputs,
            "max_workers": 0,
        }

    if full_eligible:
        max_workers = 1
        if real_parallel:
            max_workers = min(inputs["independent_workstreams"], 3)
        elif moa_collaboration:
            # MOA-only FULL defaults to a small cross-check set; do not inflate
            # worker count toward 3 unless real parallelism is also present.
            max_workers = 2
        return {
            "decision": "FULL",
            "eligible": True,
            "reason_codes": reason_codes,
            "reasons": reasons,
            "inputs": inputs,
            "max_workers": max_workers,
            "override_used": False,
        }

    lite_eligible = (
        inputs["external_worker_required"]
        and not inputs["semantic_change"]
        and inputs["expected_rounds"] == 1
        and inputs["estimated_direct_minutes"] >= LITE_MINUTES
        and inputs["independent_workstreams"] == 1
    )
    # Note: if moa_collaboration held, full_eligible would already be True and
    # the `if full_eligible` branch above would have returned FULL -- so by the
    # time we reach here, an unsafe-LITE request with substantive semantic value
    # has already promoted to FULL (collaboration outranks a lite preference).
    # The DIRECT fallback below only fires for non-MOA unsafe-LITE requests.
    if inputs["requested_mode"] == "lite" and not lite_eligible:
        return {
            "decision": "DIRECT",
            "eligible": False,
            "reason_codes": ["LITE_NOT_SAFE"],
            "reasons": [
                "lite mode requires a low-risk non-semantic single-worker task"
            ],
            "inputs": inputs,
            "max_workers": 0,
        }
    if lite_eligible:
        return {
            "decision": "LITE",
            "eligible": True,
            "reason_codes": ["EXTERNAL_WORKER_REQUIRED", "LOW_RISK_SINGLE_ROUND"],
            "reasons": [
                "the user requires an external worker for a low-risk single-round task"
            ],
            "inputs": inputs,
            "max_workers": 1,
        }

    return {
        "decision": "DIRECT",
        "eligible": True,
        "reason_codes": ["DELEGATION_OVERHEAD_EXCEEDS_EXPECTED_BENEFIT"],
        "reasons": [
            "task is below the full-delegation threshold and no safe lite exception applies"
        ],
        "inputs": inputs,
        "max_workers": 0,
    }


def routing_values_from_spec(spec):
    prefix = "routing."
    return {
        key[len(prefix):]: value
        for key, value in spec.items()
        if key.startswith(prefix)
    }

