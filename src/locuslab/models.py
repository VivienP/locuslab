"""Shared model vocabulary for LocusLab V1 scaffolding."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class DocumentKind(StrEnum):
    """Supported dossier document categories.

    MDR/IVDR-specific taxonomy. The CER/PMS/PSUR/PMCF/SSCP/GSPR_MAPPING members
    encode the V1 wedge. EVIDENCE_TABLE, SOURCE_PDF, and OTHER are
    domain-agnostic. Per docs/architecture.md "Engine Domain Discipline", the
    MDR-specific members should migrate into a pluggable rule pack
    (e.g. src/locuslab/rules/mdr/) when Stage-2 pharma artifacts (CSR,
    protocol, SAP, biomarker, safety narrative, literature) need their own
    document taxonomy. Engine primitives must not branch on these members;
    only MDR rule packs may.
    """

    CER = "CER"
    PMS = "PMS"
    PSUR = "PSUR"
    PMCF = "PMCF"
    SSCP = "SSCP"
    GSPR_MAPPING = "GSPR_MAPPING"
    EVIDENCE_TABLE = "EVIDENCE_TABLE"
    SOURCE_PDF = "SOURCE_PDF"
    OTHER = "OTHER"


class ParserWarningCode(StrEnum):
    """Ingestion warning categories preserved for auditability."""

    EMPTY_FILE = "empty_file"
    FILE_READ_FAILED = "file_read_failed"
    PARSER_NOT_IMPLEMENTED = "parser_not_implemented"
    UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
    EXTRACTION_NO_TEXT_LAYER = "extraction_no_text_layer"
    EXTRACTION_EMPTY_DOCUMENT = "extraction_empty_document"
    EXTRACTION_UNREADABLE_FILE = "extraction_unreadable_file"
    EXTRACTION_PARTIAL_CONTENT = "extraction_partial_content"


class SpanLocationKind(StrEnum):
    """Initial location vocabulary for extracted spans."""

    FILE = "file"
    LINE = "line"
    PARAGRAPH = "paragraph"
    TABLE_CELL = "table_cell"
    PAGE = "page"


class ClaimType(StrEnum):
    """High-level claim categories."""

    NUMERIC = "numeric"
    CITATION = "citation"
    CLINICAL_PERFORMANCE = "clinical_performance"
    SAFETY = "safety"
    BENEFIT_RISK = "benefit_risk"
    COMPLETENESS = "completeness"
    CLASSIFICATION = "classification"
    OTHER = "other"


class ConfidenceLabel(StrEnum):
    """Extraction confidence buckets."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class FindingSeverity(StrEnum):
    """ECO severity vocabulary."""

    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"
    INFORMATIONAL = "Informational"


class AdjudicationState(StrEnum):
    """Human review state for findings."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED_FALSE_POSITIVE = "rejected_false_positive"
    REJECTED_OUT_OF_SCOPE = "rejected_out_of_scope"
    DEFERRED = "deferred"


@dataclass(frozen=True)
class ParserWarning:
    """Explicit parser limitation or failure recorded during ingestion."""

    code: ParserWarningCode
    message: str
    path: str
    location: str | None = None


@dataclass(frozen=True)
class SpanLocation:
    """Structured provenance location for a span within a document."""

    kind: SpanLocationKind
    index: int | None = None
    label: str | None = None


@dataclass(frozen=True)
class Document:
    """A parsed dossier document."""

    document_id: str
    kind: DocumentKind
    path: str
    sha256: str
    parser: str
    metadata: dict[str, str] = field(default_factory=dict)
    parse_warnings: tuple[ParserWarning, ...] = ()


@dataclass(frozen=True)
class Span:
    """Traceable text or table region extracted from a document."""

    span_id: str
    document_id: str
    location: SpanLocation
    text: str
    section: str | None = None
    extraction_warnings: tuple[ParserWarning, ...] = ()


@dataclass(frozen=True)
class Claim:
    """Candidate claim extracted from a span."""

    claim_id: str
    document_id: str
    span_id: str
    text: str
    claim_type: ClaimType
    extraction_method: str
    confidence_label: ConfidenceLabel


@dataclass(frozen=True)
class Source:
    """Bibliography or local evidence source."""

    source_id: str
    path: str | None
    citation_key: str | None
    availability_status: str
    origin_span_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceLink:
    """Mapping between a claim and a supporting or unresolved source."""

    evidence_link_id: str
    claim_id: str
    source_id: str | None
    status: str
    linking_method: str


@dataclass(frozen=True)
class Finding:
    """RA/QA-readable ECO finding shell."""

    eco_id: str
    severity: FindingSeverity
    checker_id: str
    finding_type: str
    affected_object_ids: tuple[str, ...]
    evidence: str
    remediation_hint: str
    adjudication_state: AdjudicationState = AdjudicationState.PENDING
