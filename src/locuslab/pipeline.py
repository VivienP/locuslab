"""Verification engine pipeline for LocusLab V1."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

from locuslab.audit import build_manifest, derive_run_id, hash_artifact, write_manifest
from locuslab.checkers import run_checkers
from locuslab.extract.citation_parser import CitationParser
from locuslab.extract.claim_extractor import ClaimExtractor
from locuslab.graph import (
    build_graph_records,
    collect_record_ids,
    compute_unresolved_affected_ids,
)
from locuslab.guidance import (
    evaluate_sscp_rules,
    is_sscp_run,
    write_checklist_outputs,
)
from locuslab.guidance.assets import (
    INVENTORY_RELPATH,
    RULE_PACK_RELPATH,
    load_guidance_payload,
)
from locuslab.ingest import DossierLoadError, load_dossier
from locuslab.linking.bibliography_resolver import BibliographyResolver
from locuslab.linking.evidence_linker import EvidenceLinker
from locuslab.models import DocumentKind
from locuslab.output import write_findings_csv, write_jsonl
from locuslab.report import write_report_package


class VerificationNotImplementedError(RuntimeError):
    """Raised until a future pipeline stage is implemented."""


class OutputDirectoryError(ValueError):
    """Raised when a run output path could overwrite dossier or user data."""


@dataclasses.dataclass(frozen=True)
class VerifyResult:
    """Summary counts from a completed verification run."""

    n_claims: int
    n_citations: int
    n_sources: int
    n_links: int
    n_findings: int
    n_graph_records: int
    output_dir: Path
    n_guidance_review_items: int | None = None
    """Phase 6D: count of guidance review items written; None when skipped."""


def _validate_output_path(dossier_dir: Path, output_dir: Path) -> None:
    dossier_path = dossier_dir.resolve()
    output_path = output_dir.resolve()
    if (
        dossier_path == output_path
        or dossier_path.is_relative_to(output_path)
        or output_path.is_relative_to(dossier_path)
    ):
        raise OutputDirectoryError(
            "Dossier and output directories must not overlap: "
            f"dossier={dossier_path}, output={output_path}"
        )
    if output_path.exists() and not output_path.is_dir():
        raise OutputDirectoryError(f"Output path is not a directory: {output_path}")


def verify_dossier(dossier_dir: Path, output_dir: Path) -> VerifyResult:
    """Verify a dossier and write pipeline artifacts.

    Phase 2 artifacts: claims.jsonl, citations.jsonl, sources.jsonl,
    evidence_links.jsonl.
    Phase 3 artifacts: findings.jsonl (canonical), findings.csv (buyer-facing).
    Phase 4 artifacts: graph.jsonl (graph-compatible event stream),
    audit_manifest.json (run reproducibility manifest).

    Raises DossierLoadError if the dossier directory cannot be loaded.
    """
    _validate_output_path(dossier_dir, output_dir)
    result = load_dossier(dossier_dir)
    if not result.spans:
        warning_codes = sorted({warning.code.value for warning in result.warnings})
        warning_detail = (
            f" Parser warnings: {', '.join(warning_codes)}."
            if warning_codes
            else ""
        )
        raise DossierLoadError(
            "Dossier yielded no usable content spans from supported inputs."
            f"{warning_detail}"
        )

    documents = list(result.documents)
    spans = list(result.spans)

    claims = ClaimExtractor().extract_claims(spans, documents)
    citations = CitationParser().parse_citations(spans)

    sources = BibliographyResolver().resolve(documents, spans, citations)
    evidence_links = EvidenceLinker().link(claims, citations, sources, spans=spans)

    findings = run_checkers(claims, citations, sources, evidence_links)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(claims, output_dir / "claims.jsonl")
    write_jsonl(citations, output_dir / "citations.jsonl")
    write_jsonl(sources, output_dir / "sources.jsonl")
    write_jsonl(evidence_links, output_dir / "evidence_links.jsonl")
    write_jsonl(findings, output_dir / "findings.jsonl")
    write_findings_csv(findings, output_dir / "findings.csv")

    # Phase 4 — graph + audit manifest.
    # graph_records count = audit_run header (1) + every typed object.
    graph_records_count = (
        1
        + len(documents)
        + len(spans)
        + len(claims)
        + len(citations)
        + len(sources)
        + len(evidence_links)
        + len(findings)
    )
    artifact_counts: dict[str, int] = {
        "documents": len(documents),
        "spans": len(spans),
        "claims": len(claims),
        "citations": len(citations),
        "sources": len(sources),
        "evidence_links": len(evidence_links),
        "findings": len(findings),
        "graph_records": graph_records_count,
    }

    # Phase 6D — pre-compute SSCP guidance evaluation (in-memory only).
    # The pipeline writes guidance artifacts AFTER deriving run_id (so the
    # checklist can carry the run_id) but BEFORE computing artifact_hashes
    # (so the manifest includes guidance hashes when SSCP).
    # Phase 6E proper: also load the derived .md for each rule's source so
    # the evaluator can attach a source_anchor (line/page in the .md) to
    # each RA_approved rule.
    guidance_rule_pack: dict[str, Any] | None = None
    guidance_inventory: dict[str, Any] | None = None
    guidance_evaluations: dict[str, dict[str, Any]] | None = None
    if is_sscp_run(documents):
        guidance_payload = load_guidance_payload()
        if guidance_payload is not None:
            guidance_rule_pack, guidance_inventory, md_text_by_source_id = (
                guidance_payload
            )
            guidance_evaluations = evaluate_sscp_rules(
                rule_pack=guidance_rule_pack,
                spans=spans,
                allowed_document_ids=frozenset(
                    document.document_id
                    for document in documents
                    if document.kind == DocumentKind.SSCP
                ),
                md_text_by_source_id=md_text_by_source_id,
            )
            artifact_counts["guidance_review_items"] = len(guidance_evaluations)
        else:
            # Phase 6D W-1: SSCP detected but guidance assets unreachable.
            # Surface the reason on stderr while keeping guidance optional
            # (no exception, no non-zero exit).
            sys.stderr.write(
                "Warning: SSCP dossier detected but packaged guidance "
                f"({RULE_PACK_RELPATH.as_posix()}) or inventory "
                f"({INVENTORY_RELPATH.as_posix()}) could not be located. "
                "Guidance review will be skipped for this run.\n"
            )

    run_id = derive_run_id(documents, artifact_counts)

    graph_records = build_graph_records(
        run_id=run_id,
        dossier_path=str(dossier_dir),
        documents=documents,
        spans=spans,
        claims=claims,
        citations=citations,
        sources=sources,
        evidence_links=evidence_links,
        findings=findings,
        artifact_counts=artifact_counts,
    )
    write_jsonl(graph_records, output_dir / "graph.jsonl")

    # Phase 6D — write guidance artifacts now that run_id is known.
    if (
        guidance_evaluations is not None
        and guidance_rule_pack is not None
        and guidance_inventory is not None
    ):
        guidance_report_summary: dict[str, Any] = {
            "run_id": run_id,
            "n_claims": len(claims),
            "n_citations": len(citations),
            "n_sources": len(sources),
            "n_evidence_links": len(evidence_links),
            "n_findings": len(findings),
            "n_graph_records": graph_records_count,
        }
        write_checklist_outputs(
            rule_pack=guidance_rule_pack,
            inventory=guidance_inventory,
            run_dir=None,
            document_family="SSCP",
            out_dir=output_dir,
            evaluations=guidance_evaluations,
            report_summary_override=guidance_report_summary,
        )

    hashed_artifacts: list[str] = [
        "claims.jsonl",
        "citations.jsonl",
        "sources.jsonl",
        "evidence_links.jsonl",
        "findings.jsonl",
        "findings.csv",
        "graph.jsonl",
    ]
    if guidance_evaluations is not None:
        hashed_artifacts.extend(["guidance_review.json", "guidance_review.md"])
    artifact_hashes = {
        name: hash_artifact(output_dir / name) for name in hashed_artifacts
    }

    extraction_methods = [c.extraction_method for c in claims]
    checker_ids = [f.checker_id for f in findings]
    linking_methods = [link.linking_method for link in evidence_links]
    unresolved_affected_ids = compute_unresolved_affected_ids(
        findings, collect_record_ids(graph_records)
    )

    manifest = build_manifest(
        run_id=run_id,
        documents=documents,
        artifact_counts=artifact_counts,
        artifact_hashes=artifact_hashes,
        extraction_methods=extraction_methods,
        checker_ids=checker_ids,
        linking_methods=linking_methods,
        unresolved_affected_ids=unresolved_affected_ids,
    )
    write_manifest(manifest, output_dir / "audit_manifest.json")

    # Phase 5 — buyer-facing report package (report.json, findings.xlsx, report.docx).
    # Quotes Phase 4 manifest fields (run_id, artifact_hashes, known_limitations)
    # rather than re-deriving them, keeping the Phase 4 audit_manifest.json
    # byte-equal across runs.
    write_report_package(
        documents=documents,
        claims=claims,
        evidence_links=evidence_links,
        findings=findings,
        audit_manifest=manifest,
        dossier_path=str(dossier_dir),
        artifact_counts=artifact_counts,
        output_dir=output_dir,
        sources=sources,
    )

    return VerifyResult(
        n_claims=len(claims),
        n_citations=len(citations),
        n_sources=len(sources),
        n_links=len(evidence_links),
        n_findings=len(findings),
        n_graph_records=len(graph_records),
        output_dir=output_dir,
        n_guidance_review_items=(
            len(guidance_evaluations) if guidance_evaluations is not None else None
        ),
    )
