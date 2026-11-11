"""Handler contract wrappers: each receives the tool-call argument mapping and
returns a JSON string on success AND on error. No uncaught exceptions ever
leave this module (DEV-04)."""

from __future__ import annotations

import json
from typing import Any, Dict

try:
    from . import core
except ImportError:  # pragma: no cover - direct (non-package) import path for tests/tools
    import core  # type: ignore


def _error_json(exc: Exception, **extra: Any) -> str:
    payload: Dict[str, Any] = {"error": str(exc), "explanation": str(exc)}
    payload.update(extra)
    return json.dumps(payload)


def verify_claim(args: Dict[str, Any], **_kwargs: Any) -> str:
    try:
        result = core.verify_claim_core(
            claim=args.get("claim", ""),
            metric=args.get("metric", ""),
            evidence=args.get("evidence"),
            calculation=args.get("calculation"),
            tolerance=args.get("tolerance"),
        )
        return json.dumps(result, allow_nan=False)
    except Exception as exc:  # defensive: handlers never raise
        return _error_json(exc, verdict="unverifiable", claimed_value=None,
                           recomputed_value=None, metric=None)


def evaluate_difference(args: Dict[str, Any], **_kwargs: Any) -> str:
    try:
        result = core.evaluate_difference_core(
            data_a=args.get("data_a"),
            data_b=args.get("data_b"),
            paired=args.get("paired", False),
            alpha=args.get("alpha"),
            correction=args.get("correction"),
        )
        return json.dumps(result, allow_nan=False)
    except Exception as exc:  # defensive: handlers never raise
        return _error_json(exc, verdict="inconclusive", p_value=None, effect_size=None,
                           confidence_interval=None, test_used=None)


def qualify_conclusion(args: Dict[str, Any], **_kwargs: Any) -> str:
    try:
        result = core.qualify_conclusion_core(
            conclusion=args.get("conclusion", ""),
            evidence=args.get("evidence"),
            prior_result=args.get("prior_result"),
        )
        return json.dumps(result, allow_nan=False)
    except Exception as exc:  # defensive: handlers never raise
        return _error_json(exc, supported_conclusion=None, epistemic_status="unverifiable",
                           overclaim=True)
