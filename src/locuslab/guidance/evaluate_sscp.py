"""Deterministic evaluation of the four RA_approved SSCP rules.

Pure Python, no LLM, no embedding, no network. Each evaluator scans dossier
spans for case-insensitive substring matches against a small, conservative
pattern list. The output classifies each rule as `observed_evidence`,
`missing_candidate`, or `not_evaluated`. None of those statuses is a
compliance verdict. The six RA_pending rules in the SSCP pack are always
`not_evaluated` in v0.3.0 — promotion requires fixture-backed regression
tests and explicit `implementation_status: implemented` on the rule.

See `docs/architecture.md` and `docs/LIMITATIONS.md`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

from locuslab.guidance.excerpt_anchor import locate_excerpt
from locuslab.models import Document, DocumentKind, Span

EVALUATION_STATUS_OBSERVED = "observed_evidence"
EVALUATION_STATUS_MISSING = "missing_candidate"
EVALUATION_STATUS_NOT_EVALUATED = "not_evaluated"

EVALUATION_METHOD_DETERMINISTIC = "deterministic_keyword_match"
EVALUATION_METHOD_HUMAN = "human_review_only"

_MAX_EVIDENCE_MATCHES = 5
_PREVIEW_CHARS = 200

# Conservative pattern set per RA_approved rule. Pattern strings are
# case-insensitive substring matches on Span.text. Patterns mirror the
# verbatim MDCG 2019-9 excerpt language without broad semantic inference.
_DETERMINISTIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "guidance.sscp.required_section.intended_purpose": (
        "intended purpose",
        "intended use",
    ),
    "guidance.sscp.required_section.device_description": (
        "device description",
        "description of the device",
        "operating principles",
        "mode of action",
        "mode(s) of action",
    ),
    "guidance.sscp.metadata.basic_udi_di_present": (
        "basic udi-di",
        "basic udi di",
    ),
    "guidance.sscp.metadata.notified_body_identifier": (
        "notified body",
        "nb's name",
        "nb’s name",  # curly apostrophe (matches MDCG 2019-9 PDF text)
        "single identification number",
    ),
}

DETERMINISTIC_RULE_IDS: frozenset[str] = frozenset(_DETERMINISTIC_PATTERNS)


def is_sscp_run(documents: Sequence[Document]) -> bool:
    """Return True if at least one document in the dossier is kind=SSCP.

    Filename-token based per `src/locuslab/ingest/loader.py`. Conservative
    trigger: a CER + GSPR_mapping dossier with no SSCP file returns False
    and the pipeline skips guidance review.
    """
    return any(doc.kind == DocumentKind.SSCP for doc in documents)


def _preview(text: str) -> str:
    """Normalize newlines, trim, truncate to _PREVIEW_CHARS."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= _PREVIEW_CHARS:
        return cleaned
    return cleaned[:_PREVIEW_CHARS]


def _evaluate_rule(
    rule_id: str, patterns: tuple[str, ...], spans: Sequence[Span]
) -> dict[str, Any]:
    """Return evaluation dict for a single deterministic rule."""
    matches: list[dict[str, Any]] = []
    for span in spans:
        text_lower = span.text.lower()
        for pattern in patterns:
            if pattern in text_lower:
                matches.append(
                    {
                        "document_id": span.document_id,
                        "span_id": span.span_id,
                        "span_text_preview": _preview(span.text),
                        "matched_pattern": pattern,
                    }
                )
                break  # one match per span; do not multiply-count
        if len(matches) >= _MAX_EVIDENCE_MATCHES:
            break
    if matches:
        return {
            "evaluation_status": EVALUATION_STATUS_OBSERVED,
            "evaluation_method": EVALUATION_METHOD_DETERMINISTIC,
            "evidence_matches": matches,
        }
    return {
        "evaluation_status": EVALUATION_STATUS_MISSING,
        "evaluation_method": EVALUATION_METHOD_DETERMINISTIC,
        "evidence_matches": [],
    }


def evaluate_sscp_rules(
    *,
    rule_pack: Mapping[str, Any],
    spans: Sequence[Span],
    md_text_by_source_id: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Evaluate each rule in the pack; return rule_id -> evaluation dict.

    Rules NOT in `_DETERMINISTIC_PATTERNS` are marked `not_evaluated` (the
    6 RA_pending SSCP rules in v0.3.0 fall here). Phase 6D scope is bounded
    to the 4 RA_approved deterministic rules.

    Phase 6E proper: when `md_text_by_source_id` is supplied as a mapping
    of `source_id -> (md_path, md_text)`, each rule with a non-null
    `exact_excerpt` and an entry in the mapping receives a `source_anchor`
    field on its evaluation dict (`dataclasses.asdict` of `SourceAnchor`).
    Rules without an excerpt or without a corresponding .md remain
    `source_anchor: None`.
    """
    results: dict[str, dict[str, Any]] = {}
    for rule in rule_pack.get("rules", []) or []:
        if not isinstance(rule, Mapping):
            continue
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            continue
        patterns = _DETERMINISTIC_PATTERNS.get(rule_id)
        if patterns is None:
            evaluation: dict[str, Any] = {
                "evaluation_status": EVALUATION_STATUS_NOT_EVALUATED,
                "evaluation_method": EVALUATION_METHOD_HUMAN,
                "evidence_matches": None,
            }
        else:
            evaluation = _evaluate_rule(rule_id, patterns, spans)

        # Phase 6E proper: attach source_anchor when an .md is available
        # for the rule's source AND the rule carries an exact_excerpt.
        evaluation["source_anchor"] = _resolve_source_anchor(
            rule, md_text_by_source_id
        )
        results[rule_id] = evaluation
    return results


def _resolve_source_anchor(
    rule: Mapping[str, Any],
    md_text_by_source_id: Mapping[str, tuple[str, str]] | None,
) -> dict[str, Any] | None:
    """Locate the rule's exact_excerpt inside the derived .md of the
    rule's source, if both are available. Returns the dataclass-as-dict
    representation of the resulting SourceAnchor, or None when the rule
    has no excerpt, no source mapping is supplied, or the excerpt cannot
    be located."""
    if md_text_by_source_id is None:
        return None
    excerpt = rule.get("exact_excerpt")
    if not isinstance(excerpt, str) or not excerpt.strip():
        return None
    source_id = rule.get("source_id")
    if not isinstance(source_id, str):
        return None
    md_entry = md_text_by_source_id.get(source_id)
    if md_entry is None:
        return None
    md_path, md_text = md_entry
    anchor = locate_excerpt(excerpt=excerpt, md_text=md_text, md_path=md_path)
    if anchor is None:
        return None
    return dataclasses.asdict(anchor)
