"""Build the canonical report.json dict and write it deterministically.

report.json is the machine-readable companion to report.docx; it quotes the
Phase 4 audit_manifest fields (artifact_hashes, known_limitations) verbatim
rather than re-deriving them, which keeps Phase 4 artifacts unmodified.

Determinism contract: identical input → byte-equal report.json. Enforced via
sort_keys=True on the top-level dump and stable sorting of nested lists.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from locuslab.models import Claim, Document, EvidenceLink, Finding, FindingSeverity
from locuslab.report.language import assert_no_forbidden_language

REPORT_SCHEMA_VERSION = "report.v1"

_SEVERITY_ORDER: tuple[str, ...] = (
    FindingSeverity.CRITICAL.value,
    FindingSeverity.MAJOR.value,
    FindingSeverity.MINOR.value,
    FindingSeverity.INFORMATIONAL.value,
)


def _document_summary(doc: Document) -> dict[str, object]:
    return {
        "document_id": doc.document_id,
        "path": doc.path,
        "kind": doc.kind.value,
        "sha256": doc.sha256,
        "parser": doc.parser,
        "parse_warning_codes": sorted({w.code.value for w in doc.parse_warnings}),
    }


def _finding_detail(finding: Finding) -> dict[str, object]:
    return {
        "eco_id": finding.eco_id,
        "severity": finding.severity.value,
        "checker_id": finding.checker_id,
        "finding_type": finding.finding_type,
        "affected_object_ids": list(finding.affected_object_ids),
        "evidence": finding.evidence,
        "remediation_hint": finding.remediation_hint,
        "adjudication_state": finding.adjudication_state.value,
    }


def _findings_summary(findings: Sequence[Finding]) -> dict[str, object]:
    by_severity: dict[str, int] = {sev: 0 for sev in _SEVERITY_ORDER}
    by_finding_type: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity.value] += 1
        by_finding_type[f.finding_type] = by_finding_type.get(f.finding_type, 0) + 1
    return {
        "by_severity": dict(by_severity),
        "by_finding_type": dict(sorted(by_finding_type.items())),
    }


def build_report_dict(
    *,
    documents: Sequence[Document],
    claims: Sequence[Claim],
    evidence_links: Sequence[EvidenceLink],
    findings: Sequence[Finding],
    audit_manifest: dict[str, object],
    dossier_path: str,
    artifact_counts: dict[str, int],
) -> dict[str, object]:
    """Build the canonical report.json dict.

    `audit_manifest` is the in-memory manifest dict already built in the
    Phase 4 stage; we quote its `artifact_hashes` and `known_limitations`
    rather than re-hashing or re-deriving.
    """
    report = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "run_id": audit_manifest["run_id"],
        "dossier_path": dossier_path,
        "artifact_counts": dict(sorted(artifact_counts.items())),
        "input_documents": [
            _document_summary(d) for d in sorted(documents, key=lambda x: x.document_id)
        ],
        "findings_summary": _findings_summary(findings),
        "findings_detail": [
            _finding_detail(f) for f in sorted(findings, key=lambda x: x.eco_id)
        ],
        "observed_methods": {
            "extraction_methods": sorted({c.extraction_method for c in claims}),
            "checker_ids": sorted({f.checker_id for f in findings}),
            "linking_methods": sorted({link.linking_method for link in evidence_links}),
        },
        "known_limitations": list(cast(Sequence[str], audit_manifest["known_limitations"])),
        "source_artifact_hashes": dict(
            cast(dict[str, str], audit_manifest["artifact_hashes"])
        ),
    }

    for finding_detail in cast(list[dict[str, object]], report["findings_detail"]):
        assert_no_forbidden_language(
            str(finding_detail["evidence"]), f"report.json finding {finding_detail['eco_id']}"
        )
        assert_no_forbidden_language(
            str(finding_detail["remediation_hint"]),
            f"report.json finding {finding_detail['eco_id']}",
        )

    return report


def write_report_json(report: dict[str, object], path: Path) -> None:
    """Write report.json with sorted top-level keys and trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
