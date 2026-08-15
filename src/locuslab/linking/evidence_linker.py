"""Emit EvidenceLink records with deterministic status assignment.

Engine-domain note: the link status vocabulary and explicit-citation /
filename-reference rules are domain-agnostic. Rule 4 (COMPLETENESS-claim
pairing on GSPR row layout) is MDR/IVDR-specific and should migrate into an
MDR rule pack when pharma completeness rules (e.g. CSR appendix pairing,
protocol-SAP cross-reference) need their own linker logic. See
docs/architecture.md "Engine Domain Discipline".
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from locuslab.extract.citation_parser import CitationMention
from locuslab.ingest.ids import make_evidence_link_id
from locuslab.models import Claim, ClaimType, EvidenceLink, Source, Span, SpanLocationKind

# Linking method labels
_METHOD_EXPLICIT_CITATION = "explicit_citation"
_METHOD_EXPLICIT_CITATION_AMBIGUOUS = "explicit_citation_ambiguous"
_METHOD_FILENAME_REFERENCE = "filename_reference"
_METHOD_NO_LINK_FOUND = "no_link_found"

# GSPR column section patterns
_GSPR_REQUIREMENT_COL = re.compile(r"B=Requirement", re.IGNORECASE)
_GSPR_EVIDENCE_DOC_COL = re.compile(r"D=Evidence_Document", re.IGNORECASE)

# Row number from an xlsx_reader span label of the form `<sheet>:<col><row>` (e.g. `GSPR:B5`).
# Anchored on the trailing col+row segment to tolerate colons in sheet names.
_LABEL_ROW = re.compile(r":[A-Z]+(?P<row>\d+)$")


def _row_number_from_label(label: str | None) -> int | None:
    if not label:
        return None
    match = _LABEL_ROW.search(label)
    if not match:
        return None
    return int(match.group("row"))


def _build_gspr_req_to_evidence_doc(spans: Sequence[Span]) -> dict[str, str | None]:
    """Map each GSPR requirement span_id -> Evidence_Document filename for the same row.

    Pairing is keyed on `(document_id, row_number)` parsed from
    `SpanLocation.label`. Label-based pairing tolerates sparse rows
    where the xlsx_reader skips empty intermediate cells and tolerates
    non-contiguous row numbers. Keying on `document_id` prevents
    cross-document collisions when multiple GSPR documents share a row
    number.

    Returns a dict of {requirement_span_id: evidence_doc_filename_or_None}.
    """
    req_spans_by_row: dict[tuple[str, int], Span] = {}
    evdoc_text_by_row: dict[tuple[str, int], str] = {}

    for span in spans:
        if span.location.kind != SpanLocationKind.TABLE_CELL:
            continue
        row_number = _row_number_from_label(span.location.label)
        if row_number is None:
            continue
        key = (span.document_id, row_number)
        section = span.section or ""
        if _GSPR_REQUIREMENT_COL.search(section):
            req_spans_by_row[key] = span
        elif _GSPR_EVIDENCE_DOC_COL.search(section):
            evdoc_text_by_row[key] = span.text.strip()

    result: dict[str, str | None] = {}
    for key, req_span in req_spans_by_row.items():
        result[req_span.span_id] = evdoc_text_by_row.get(key)
    return result


class EvidenceLinker:
    """Emit EvidenceLink records with deterministic status assignment."""

    def link(
        self,
        claims: Sequence[Claim],
        citations: Sequence[CitationMention],
        sources: Sequence[Source],
        spans: Sequence[Span] | None = None,
    ) -> list[EvidenceLink]:
        """Link claims to sources via citation resolution.

        Returns links sorted by evidence_link_id.

        ``spans`` supplies span provenance used to pair GSPR requirement
        cells with their row's `Evidence_Document` cell. It is required
        when COMPLETENESS claims are passed in; callers that only link
        CITATION / CLINICAL_PERFORMANCE / CLASSIFICATION claims may omit
        it. GSPR row pairing is keyed on `(document_id, row_number)`
        parsed from `SpanLocation.label`, so sparse rows and empty
        intermediate cells stay aligned.

        Status assignment rules (in precedence order per spec Table 5.6):
        1. Claim span has an author-year citation resolving to local_fulltext source
           -> status=resolved, method=explicit_citation
        2. Claim span has a bracketed-numeric citation with no numbered references list
           -> status=source_unresolved, method=no_link_found
        3. Claim type is CLASSIFICATION with no citation
           -> status=manual_review_required, method=no_link_found
        4. Claim type is COMPLETENESS and the GSPR evidence-doc filename is a missing_file source
           -> status=source_missing, method=filename_reference
        5. No citation markers and no structural reference
           -> status=manual_review_required, method=no_link_found
        """
        # Build lookup indexes
        cites_by_span: dict[str, list[CitationMention]] = {}
        for cite in citations:
            cites_by_span.setdefault(cite["span_id"], []).append(cite)

        sources_by_key: dict[str, list[Source]] = {}
        sources_by_path: dict[str, Source] = {}
        for src in sources:
            if src.citation_key:
                sources_by_key.setdefault(src.citation_key, []).append(src)
            if src.path:
                sources_by_path[src.path] = src

        # GSPR row relationship map (requirement span_id -> evidence doc filename)
        gspr_req_to_evdoc: dict[str, str | None] = {}
        if spans is not None:
            gspr_req_to_evdoc = _build_gspr_req_to_evidence_doc(spans)

        links: list[EvidenceLink] = []
        for claim in claims:
            link = self._link_claim(
                claim, cites_by_span, sources_by_key, sources_by_path, gspr_req_to_evdoc
            )
            links.append(link)

        links.sort(key=lambda lk: lk.evidence_link_id)
        return links

    def _link_claim(
        self,
        claim: Claim,
        cites_by_span: dict[str, list[CitationMention]],
        sources_by_key: dict[str, list[Source]],
        sources_by_path: dict[str, Source],
        gspr_req_to_evdoc: dict[str, str | None],
    ) -> EvidenceLink:
        span_cites = cites_by_span.get(claim.span_id, [])
        ambiguous_source_ids: set[str] = set()

        # Rule 1: explicit author-year citation resolving to local_fulltext source
        for cite in span_cites:
            if cite["marker_form"] in ("author_year_parenthetical", "author_year_table_cell"):
                key = cite["normalized_key"]
                if key and key in sources_by_key:
                    local_sources = [
                        source
                        for source in sources_by_key[key]
                        if source.availability_status == "local_fulltext"
                    ]
                    if len(local_sources) == 1:
                        src = local_sources[0]
                        return self._make_link(
                            claim.claim_id,
                            src.source_id,
                            "resolved",
                            _METHOD_EXPLICIT_CITATION,
                        )
                    if len(local_sources) > 1:
                        ambiguous_source_ids.update(
                            source.source_id for source in local_sources
                        )

        if ambiguous_source_ids:
            return self._make_link(
                claim.claim_id,
                None,
                "source_ambiguous",
                _METHOD_EXPLICIT_CITATION_AMBIGUOUS,
                candidate_source_ids=tuple(sorted(ambiguous_source_ids)),
            )

        # Rule 2: bracketed-numeric citation with no numbered references resolution
        bracket_cites = [c for c in span_cites if c["marker_form"] == "numeric_bracketed"]
        if bracket_cites:
            return self._make_link(
                claim.claim_id,
                None,
                "source_unresolved",
                _METHOD_NO_LINK_FOUND,
            )

        # Rule 3: CLASSIFICATION claim with no citation
        if claim.claim_type == ClaimType.CLASSIFICATION:
            return self._make_link(
                claim.claim_id,
                None,
                "manual_review_required",
                _METHOD_NO_LINK_FOUND,
            )

        # Rule 4: COMPLETENESS claim from a GSPR row
        if claim.claim_type == ClaimType.COMPLETENESS:
            evdoc_filename = gspr_req_to_evdoc.get(claim.span_id)
            if evdoc_filename and evdoc_filename in sources_by_path:
                src = sources_by_path[evdoc_filename]
                if src.availability_status == "missing_file":
                    return self._make_link(
                        claim.claim_id,
                        src.source_id,
                        "source_missing",
                        _METHOD_FILENAME_REFERENCE,
                    )
            # Requirement row with no Evidence_Document cell at all: source_missing, no anchor.
            if claim.span_id in gspr_req_to_evdoc and gspr_req_to_evdoc[claim.span_id] is None:
                return self._make_link(
                    claim.claim_id,
                    None,
                    "source_missing",
                    _METHOD_NO_LINK_FOUND,
                )

        # Rule 5: no citation markers and no structural reference
        return self._make_link(
            claim.claim_id,
            None,
            "manual_review_required",
            _METHOD_NO_LINK_FOUND,
        )

    def _make_link(
        self,
        claim_id: str,
        source_id: str | None,
        status: str,
        linking_method: str,
        candidate_source_ids: tuple[str, ...] = (),
    ) -> EvidenceLink:
        sorted_candidate_ids = tuple(sorted(candidate_source_ids))
        link_id = make_evidence_link_id(
            claim_id, source_id, status, sorted_candidate_ids
        )
        return EvidenceLink(
            evidence_link_id=link_id,
            claim_id=claim_id,
            source_id=source_id,
            status=status,
            linking_method=linking_method,
            candidate_source_ids=sorted_candidate_ids,
        )
