"""Phase 5 report package orchestrator.

Single entry point invoked by the pipeline after the Phase 4 audit manifest
has been built. Writes report.json, findings.xlsx, and report.docx into the
same run directory as the Phase 1-4 artifacts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from locuslab.models import Claim, Document, EvidenceLink, Finding, Source
from locuslab.report.docx_report import write_report_docx
from locuslab.report.json_report import build_report_dict, write_report_json
from locuslab.report.xlsx_report import write_findings_xlsx


@dataclass(frozen=True)
class ReportPackagePaths:
    """Paths to the three report-package artifacts written by Phase 5."""

    report_json: Path
    findings_xlsx: Path
    report_docx: Path


def write_report_package(
    *,
    documents: Sequence[Document],
    claims: Sequence[Claim],
    evidence_links: Sequence[EvidenceLink],
    findings: Sequence[Finding],
    audit_manifest: dict[str, object],
    dossier_path: str,
    artifact_counts: dict[str, int],
    output_dir: Path,
    sources: Sequence[Source] = (),
) -> ReportPackagePaths:
    """Build and write the three Phase 5 report artifacts.

    `audit_manifest` is the already-built in-memory manifest dict from the
    Phase 4 stage; this function quotes its `run_id`, `artifact_hashes`, and
    `known_limitations` without re-deriving them, keeping Phase 4 outputs
    untouched.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = output_dir / "report.json"
    findings_xlsx_path = output_dir / "findings.xlsx"
    report_docx_path = output_dir / "report.docx"

    report_dict = build_report_dict(
        documents=documents,
        claims=claims,
        evidence_links=evidence_links,
        findings=findings,
        audit_manifest=audit_manifest,
        dossier_path=dossier_path,
        artifact_counts=artifact_counts,
    )
    write_report_json(report_dict, report_json_path)

    write_findings_xlsx(findings, findings_xlsx_path)

    write_report_docx(
        documents=documents,
        claims=claims,
        evidence_links=evidence_links,
        findings=findings,
        audit_manifest=audit_manifest,
        dossier_path=dossier_path,
        artifact_counts=artifact_counts,
        path=report_docx_path,
        sources=sources,
    )

    return ReportPackagePaths(
        report_json=report_json_path,
        findings_xlsx=findings_xlsx_path,
        report_docx=report_docx_path,
    )
