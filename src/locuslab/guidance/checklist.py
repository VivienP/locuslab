"""Guidance-checklist builder and renderer.

Reads a rule pack plus an optional `locus verify` run directory (read-only)
and produces a structured human-review checklist. The output is
intentionally NOT an ECO finding: every item carries
`output_boundary: "not_an_ECO_finding"` and `review_status:
"needs_human_confirmation"`. The renderer never writes to the run directory.

Two output artifacts per call:

- `<out_dir>/guidance_review.json` — machine-readable structured checklist.
- `<out_dir>/guidance_review.md` — human-readable rendering for the reviewer.

See `docs/architecture.md` and `docs/LIMITATIONS.md`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from locuslab.guidance.validate import GuidanceValidationError, validate_rule_pack

CHECKLIST_SCHEMA_VERSION = "guidance.checklist.v1"
REVIEW_STATUS = "needs_human_confirmation"
OUTPUT_BOUNDARY = "not_an_ECO_finding"

_REPORT_JSON_NAME = "report.json"
_OUT_JSON_NAME = "guidance_review.json"
_OUT_MD_NAME = "guidance_review.md"


def _read_report_summary(run_dir: Path) -> dict[str, Any] | None:
    """Read optional `report.json` for run_id and counts. Never writes.

    The Phase 5 report.json nests counts under `artifact_counts`. Fall back
    to top-level keys for forward compatibility if the schema ever flattens.
    """
    report_path = run_dir / _REPORT_JSON_NAME
    if not report_path.is_file():
        return None
    data = json.loads(report_path.read_text(encoding="utf-8"))
    counts_raw = data.get("artifact_counts") or {}
    counts: Mapping[str, Any] = counts_raw if isinstance(counts_raw, Mapping) else {}

    def _pick(name: str, alias: str | None = None) -> Any:
        if name in counts:
            return counts[name]
        if alias is not None and alias in data:
            return data[alias]
        return None

    summary: dict[str, Any] = {
        "run_id": data.get("run_id"),
        "n_claims": _pick("claims", "n_claims"),
        "n_citations": _pick("citations", "n_citations"),
        "n_sources": _pick("sources", "n_sources"),
        "n_evidence_links": _pick("evidence_links", "n_evidence_links"),
        "n_findings": _pick("findings", "n_findings"),
        "n_graph_records": _pick("graph_records", "n_graph_records"),
    }
    return summary


def _build_review_prompt(rule: Mapping[str, Any]) -> str:
    paraphrase = str(rule.get("paraphrase") or "").strip()
    target = str(rule.get("target_document_type") or "the target document")
    modal = str(rule.get("modal_strength") or "")
    base = (
        f"Confirm whether the {target} satisfies this rule"
        f"{(f' ({modal})' if modal else '')}: {paraphrase}"
    )
    notes = str(rule.get("notes") or "").strip()
    if notes:
        base = f"{base}\n\nReviewer notes: {notes}"
    return base


def _build_evidence_pointer(
    rule: Mapping[str, Any],
    report_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    pointer: dict[str, Any] = {
        "target_document_type": rule.get("target_document_type"),
        "source_id": rule.get("source_id"),
        "source_excerpt_pending": bool(rule.get("source_excerpt_pending") or False),
    }
    for key in (
        "exact_excerpt",
        "source_hash",
        "source_url_or_local_path",
        "source_version",
    ):
        value = rule.get(key)
        if value not in (None, ""):
            pointer[key] = value
    if report_summary is not None and report_summary.get("run_id") is not None:
        pointer["verify_run_id"] = report_summary.get("run_id")
    return pointer


def build_checklist(
    *,
    rule_pack: Mapping[str, Any],
    report_summary: Mapping[str, Any] | None = None,
    document_family: str = "SSCP",
    evaluations: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a checklist dict from a rule pack.

    `report_summary` is an optional mapping previously extracted from
    `report.json` via `_read_report_summary`; pass `None` if no verify run
    is referenced. `evaluations` is an optional Phase 6D mapping from
    `rule_id` to an evaluation dict containing `evaluation_status`,
    `evaluation_method`, and `evidence_matches`; when supplied, each
    matching review item carries those fields. Rules not present in
    `evaluations` get `evaluation_status: not_evaluated` by default.
    """
    items: list[dict[str, Any]] = []
    for rule in rule_pack.get("rules", []) or []:
        if not isinstance(rule, Mapping):
            continue
        rule_id = rule.get("rule_id")
        item: dict[str, Any] = {
            "rule_id": rule_id,
            "document_family": rule_pack.get("document_family"),
            "target_document_type": rule.get("target_document_type"),
            "modal_strength": rule.get("modal_strength"),
            "automation_readiness": rule.get("automation_readiness"),
            "RA_review_status": rule.get("RA_review_status"),
            "review_status": REVIEW_STATUS,
            "source_id": rule.get("source_id"),
            "source_excerpt_pending": bool(rule.get("source_excerpt_pending") or False),
            "exact_excerpt": rule.get("exact_excerpt"),
            "source_hash": rule.get("source_hash"),
            "source_url_or_local_path": rule.get("source_url_or_local_path"),
            "source_version": rule.get("source_version"),
            "review_prompt": _build_review_prompt(rule),
            "evidence_to_review": _build_evidence_pointer(rule, report_summary),
            "output_boundary": OUTPUT_BOUNDARY,
        }
        if evaluations is not None and isinstance(rule_id, str):
            evaluation = evaluations.get(rule_id)
            if isinstance(evaluation, Mapping):
                item["evaluation_status"] = evaluation.get("evaluation_status")
                item["evaluation_method"] = evaluation.get("evaluation_method")
                item["evidence_matches"] = evaluation.get("evidence_matches")
                # Phase 6E proper: surface the per-rule source .md anchor.
                item["source_anchor"] = evaluation.get("source_anchor")
            else:
                item["evaluation_status"] = "not_evaluated"
                item["evaluation_method"] = "human_review_only"
                item["evidence_matches"] = None
                item["source_anchor"] = None
        items.append(item)

    checklist: dict[str, Any] = {
        "_schema_description": (
            "SSCP guidance review checklist. Each item is a structured "
            "prompt for a human reviewer; nothing in this file is an ECO "
            "finding. Optional evaluation_status / evaluation_method / "
            "evidence_matches fields apply to the four RA_approved "
            "deterministic rules. See docs/architecture.md and "
            "docs/LIMITATIONS.md."
        ),
        "_schema_version": CHECKLIST_SCHEMA_VERSION,
        "document_family": document_family,
        "pack_id": rule_pack.get("pack_id"),
        "pack_version": rule_pack.get("pack_version"),
        "pack_status": rule_pack.get("pack_status"),
        "n_review_items": len(items),
        "output_boundary": OUTPUT_BOUNDARY,
        "review_status_default": REVIEW_STATUS,
        "run_reference": report_summary,
        "review_items": items,
    }
    return checklist


def render_markdown(checklist: Mapping[str, Any]) -> str:
    """Render the checklist as a reviewer-facing Markdown document."""
    lines: list[str] = []
    pack_id = checklist.get("pack_id") or "<unknown>"
    pack_version = checklist.get("pack_version") or "<unknown>"
    pack_status = checklist.get("pack_status") or "<unknown>"
    document_family = checklist.get("document_family") or "<unknown>"
    n_items = checklist.get("n_review_items") or 0

    lines.append(f"# {document_family} Guidance Review Checklist (Phase 6B)")
    lines.append("")
    lines.append(f"- **Pack:** `{pack_id}` v{pack_version} ({pack_status})")
    lines.append(f"- **Document family:** {document_family}")
    lines.append(f"- **Review items:** {n_items}")
    lines.append("- **Output boundary:** review aid, not an ECO finding")
    lines.append(
        "- **Review-status default:** every item starts at `needs_human_confirmation`"
    )
    lines.append("")

    run_reference = checklist.get("run_reference")
    if isinstance(run_reference, Mapping) and run_reference:
        lines.append("## Verify-run reference")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        for key in (
            "run_id",
            "n_claims",
            "n_citations",
            "n_sources",
            "n_evidence_links",
            "n_findings",
            "n_graph_records",
        ):
            value = run_reference.get(key)
            if value is not None:
                lines.append(f"| `{key}` | {value} |")
        lines.append("")
    else:
        lines.append("## Verify-run reference")
        lines.append("")
        lines.append("(no verify run referenced)")
        lines.append("")

    lines.append("## Review items")
    lines.append("")
    review_items = checklist.get("review_items") or []
    if not isinstance(review_items, list):
        review_items = []
    for idx, item in enumerate(review_items, start=1):
        if not isinstance(item, Mapping):
            continue
        rule_id = item.get("rule_id") or "<unknown>"
        lines.append(f"### {idx}. `{rule_id}`")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|---|---|")
        for key in (
            "document_family",
            "target_document_type",
            "modal_strength",
            "automation_readiness",
            "RA_review_status",
            "review_status",
            "source_id",
            "source_excerpt_pending",
            "source_version",
            "source_url_or_local_path",
            "source_hash",
            "evaluation_status",
            "evaluation_method",
            "output_boundary",
        ):
            value = item.get(key)
            if value is None:
                continue
            lines.append(f"| `{key}` | `{value}` |")
        lines.append("")
        source_excerpt = item.get("exact_excerpt")
        if isinstance(source_excerpt, str) and source_excerpt.strip():
            lines.append("**Source excerpt**")
            lines.append("")
            lines.append(source_excerpt.strip())
            lines.append("")
        anchor = item.get("source_anchor")
        if isinstance(anchor, Mapping):
            md_path = anchor.get("md_path") or "<unknown>"
            line_no = anchor.get("line_number")
            page = anchor.get("page_anchor")
            matched_via = anchor.get("matched_via") or "?"
            page_part = f", page {page}" if page is not None else ""
            lines.append("**Source anchor (Phase 6E spine consumer)**")
            lines.append("")
            lines.append(
                f"- File: `{md_path}` (line {line_no}{page_part}, matched via "
                f"`{matched_via}`)"
            )
            preview = str(anchor.get("preview") or "").strip()
            if preview:
                # Show only the first non-blank line of the preview to keep
                # the markdown readable.
                first_line = next(
                    (p for p in preview.split("\n") if p.strip()), preview[:120]
                )
                lines.append(f"- Excerpt context: {first_line.strip()[:200]}")
            lines.append("")
        evidence_matches = item.get("evidence_matches")
        if isinstance(evidence_matches, list) and evidence_matches:
            lines.append("**Evidence matches (Phase 6D deterministic)**")
            lines.append("")
            for match in evidence_matches:
                if not isinstance(match, Mapping):
                    continue
                doc_id = match.get("document_id") or "<unknown>"
                span_id = match.get("span_id") or "<unknown>"
                pattern = match.get("matched_pattern") or "<unknown>"
                preview = match.get("span_text_preview") or ""
                lines.append(
                    f"- `{doc_id}` / `{span_id}` (pattern `{pattern}`): {preview}"
                )
            lines.append("")
        lines.append("**Review prompt**")
        lines.append("")
        prompt = str(item.get("review_prompt") or "").strip()
        for paragraph in prompt.split("\n\n"):
            lines.append(paragraph)
            lines.append("")
        lines.append("**Evidence to review**")
        lines.append("")
        evidence = item.get("evidence_to_review")
        if isinstance(evidence, Mapping):
            for ekey, evalue in evidence.items():
                lines.append(f"- `{ekey}`: `{evalue}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_checklist_outputs(
    *,
    rule_pack: Mapping[str, Any],
    inventory: Mapping[str, Any],
    run_dir: Path | None,
    document_family: str,
    out_dir: Path,
    evaluations: Mapping[str, Mapping[str, Any]] | None = None,
    report_summary_override: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    """Validate the rule pack, build the checklist, write both output files.

    `evaluations` (Phase 6D): optional rule_id -> evaluation mapping that
    surfaces deterministic evaluation status alongside each item.
    `report_summary_override`: when the caller already has the run summary
    (e.g. the pipeline knows artifact_counts before report.json is written),
    pass it directly to avoid re-reading the file from disk.

    Raises GuidanceValidationError if the rule pack does not validate.
    """
    issues = validate_rule_pack(rule_pack, inventory)
    if issues:
        raise GuidanceValidationError(issues)

    if report_summary_override is not None:
        report_summary: Mapping[str, Any] | None = report_summary_override
    else:
        report_summary = _read_report_summary(run_dir) if run_dir is not None else None
    checklist = build_checklist(
        rule_pack=rule_pack,
        report_summary=report_summary,
        document_family=document_family,
        evaluations=evaluations,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / _OUT_JSON_NAME
    md_path = out_dir / _OUT_MD_NAME
    json_path.write_text(
        json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(checklist), encoding="utf-8")
    return {"json": json_path, "md": md_path}
