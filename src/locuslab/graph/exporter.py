"""Build graph-compatible records from pipeline artifacts.

Pure-Python transform: in-memory typed objects -> ordered list of dicts
ready for serialization to graph.jsonl. Eight record families written in
fixed canonical order, records within a family sorted by stable id.

No LLM, no network, no graph database. See docs/architecture.md.
"""

from __future__ import annotations

from collections.abc import Sequence

from locuslab.extract.citation_parser import CitationMention
from locuslab.models import (
    Claim,
    Document,
    EvidenceLink,
    Finding,
    Source,
    Span,
)

GRAPH_SCHEMA_VERSION = "graph.v1"

GRAPH_FAMILIES: tuple[str, ...] = (
    "audit_run",
    "document",
    "span",
    "claim",
    "citation",
    "source",
    "evidence_link",
    "finding",
)


def _envelope(record_type: str, record_id: str) -> dict[str, object]:
    """Build the common graph-record envelope.

    Callers extend the dict by direct `rec["field"] = value` assignment;
    do NOT use dict merge (`|=` / `dict.update` from an unsorted source),
    which can reorder keys and break the byte-equal determinism contract
    documented in docs/architecture.md.
    """
    return {
        "record_type": record_type,
        "record_id": record_id,
        "schema_version": GRAPH_SCHEMA_VERSION,
    }


def _audit_run_record(
    *,
    run_id: str,
    dossier_path: str,
    artifact_counts: dict[str, int],
) -> dict[str, object]:
    rec = _envelope("audit_run", run_id)
    rec["run_id"] = run_id
    rec["dossier_path"] = dossier_path
    rec["artifact_counts"] = dict(sorted(artifact_counts.items()))
    return rec


def _document_record(doc: Document) -> dict[str, object]:
    rec = _envelope("document", doc.document_id)
    rec["document_id"] = doc.document_id
    rec["kind"] = doc.kind.value
    rec["path"] = doc.path
    rec["sha256"] = doc.sha256
    rec["parser"] = doc.parser
    rec["parse_warning_codes"] = sorted({w.code.value for w in doc.parse_warnings})
    return rec


def _span_record(span: Span) -> dict[str, object]:
    rec = _envelope("span", span.span_id)
    rec["span_id"] = span.span_id
    rec["document_id"] = span.document_id
    rec["text"] = span.text
    rec["section"] = span.section
    rec["location_kind"] = span.location.kind.value
    rec["location_index"] = span.location.index
    rec["location_label"] = span.location.label
    return rec


def _claim_record(claim: Claim) -> dict[str, object]:
    rec = _envelope("claim", claim.claim_id)
    rec["claim_id"] = claim.claim_id
    rec["document_id"] = claim.document_id
    rec["span_id"] = claim.span_id
    rec["text"] = claim.text
    rec["claim_type"] = claim.claim_type.value
    rec["extraction_method"] = claim.extraction_method
    rec["confidence_label"] = claim.confidence_label.value
    return rec


def _citation_record(citation: CitationMention) -> dict[str, object]:
    rec = _envelope("citation", citation["mention_id"])
    rec["mention_id"] = citation["mention_id"]
    rec["document_id"] = citation["document_id"]
    rec["span_id"] = citation["span_id"]
    rec["marker_text"] = citation["marker_text"]
    rec["marker_form"] = citation["marker_form"]
    rec["normalized_key"] = citation["normalized_key"]
    rec["occurrence_index"] = citation["occurrence_index"]
    rec["span_offset_start"] = citation["span_offset_start"]
    rec["span_offset_end"] = citation["span_offset_end"]
    return rec


def _source_record(source: Source) -> dict[str, object]:
    rec = _envelope("source", source.source_id)
    rec["source_id"] = source.source_id
    rec["path"] = source.path
    rec["citation_key"] = source.citation_key
    rec["availability_status"] = source.availability_status
    rec["origin_span_ids"] = list(source.origin_span_ids)
    return rec


def _evidence_link_record(link: EvidenceLink) -> dict[str, object]:
    rec = _envelope("evidence_link", link.evidence_link_id)
    rec["evidence_link_id"] = link.evidence_link_id
    rec["claim_id"] = link.claim_id
    rec["source_id"] = link.source_id
    rec["status"] = link.status
    rec["linking_method"] = link.linking_method
    rec["candidate_source_ids"] = list(link.candidate_source_ids)
    return rec


def _finding_record(finding: Finding) -> dict[str, object]:
    rec = _envelope("finding", finding.eco_id)
    rec["eco_id"] = finding.eco_id
    rec["severity"] = finding.severity.value
    rec["checker_id"] = finding.checker_id
    rec["finding_type"] = finding.finding_type
    rec["affected_object_ids"] = list(finding.affected_object_ids)
    rec["evidence"] = finding.evidence
    rec["remediation_hint"] = finding.remediation_hint
    rec["adjudication_state"] = finding.adjudication_state.value
    return rec


def build_graph_records(
    *,
    run_id: str,
    dossier_path: str,
    documents: Sequence[Document],
    spans: Sequence[Span],
    claims: Sequence[Claim],
    citations: Sequence[CitationMention],
    sources: Sequence[Source],
    evidence_links: Sequence[EvidenceLink],
    findings: Sequence[Finding],
    artifact_counts: dict[str, int],
) -> list[dict[str, object]]:
    """Build graph records in canonical (family, id) order.

    artifact_counts is embedded in the audit_run header record so the
    graph file is self-describing without needing the manifest.
    """
    records: list[dict[str, object]] = []
    records.append(
        _audit_run_record(
            run_id=run_id,
            dossier_path=dossier_path,
            artifact_counts=artifact_counts,
        )
    )

    for doc in sorted(documents, key=lambda d: d.document_id):
        records.append(_document_record(doc))
    for span in sorted(spans, key=lambda s: s.span_id):
        records.append(_span_record(span))
    for claim in sorted(claims, key=lambda c: c.claim_id):
        records.append(_claim_record(claim))
    for cite in sorted(citations, key=lambda c: c["mention_id"]):
        records.append(_citation_record(cite))
    for source in sorted(sources, key=lambda s: s.source_id):
        records.append(_source_record(source))
    for link in sorted(evidence_links, key=lambda lnk: lnk.evidence_link_id):
        records.append(_evidence_link_record(link))
    for finding in sorted(findings, key=lambda f: f.eco_id):
        records.append(_finding_record(finding))

    return records


def collect_record_ids(graph_records: Sequence[dict[str, object]]) -> set[str]:
    """Return the set of all record_id values across the graph."""
    return {str(rec["record_id"]) for rec in graph_records}


def compute_unresolved_affected_ids(
    findings: Sequence[Finding],
    graph_record_ids: set[str],
) -> list[str]:
    """Return sorted ids referenced by findings that have no graph record."""
    referenced: set[str] = set()
    for finding in findings:
        referenced.update(finding.affected_object_ids)
    return sorted(referenced - graph_record_ids)
