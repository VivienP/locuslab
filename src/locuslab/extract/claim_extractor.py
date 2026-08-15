"""Deterministic regex + structural claim extraction from spans.

Engine-domain note: numeric, citation, percent/CI, and count extractors are
domain-agnostic. The classification extractor (Class I/IIa/IIb/III) and the
GSPR-row completeness extractor (extractor_id ``extract.completeness.gspr:v1``)
are MDR/IVDR-specific and should migrate into a rule pack
(``src/locuslab/rules/mdr/``) when pharma extractors are added. See
docs/architecture.md "Engine Domain Discipline".
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from locuslab.extract.citation_parser import CitationParser
from locuslab.extract.noise_gates import (
    POST_HEADER_STRIP_CP_KEYWORDS,
    is_foreshortening_table_span,
    is_sscp_boilerplate_cp_context,
    strip_sscp_page_header,
)
from locuslab.extract.patterns import (
    _MRI_CONTEXT,
    _VALUE_UNIT_RBP,
    BASIC_UDI_DI,
    CI_RANGE,
    CLASS_I,
    CLASS_IIA,
    CLASS_III,
    CLINICAL_PERFORMANCE_KEYWORDS,
    COUNT_N,
    EMDN_CODE,
    EMDN_LABEL,
    HARMONIZED_STANDARD,
    MR_CONDITIONAL,
    NB_NUMBER_INLINE,
    PERCENTAGE_DECIMAL,
    PERCENTAGE_WITH_CI,
    UDI_DI_LABEL,
    VALUE_UNIT_DRIFT,
    VALUE_UNIT_MEAN_SD,
    VALUE_UNIT_RANGE,
    VALUE_UNIT_SINGLE,
    VALUE_UNIT_TESLA,
    VALUE_UNIT_THRESHOLD,
    VALUE_UNIT_THRESHOLD_WORDS,
)
from locuslab.extract.span_filters import is_non_claim_noise_span
from locuslab.ingest.ids import make_claim_id
from locuslab.models import (
    Claim,
    ClaimType,
    ConfidenceLabel,
    Document,
    DocumentKind,
    Span,
    SpanLocationKind,
)

# Section pattern indicating a GSPR Evidence_Document column cell
_GSPR_EVIDENCE_DOC_SECTION = re.compile(r"D=Evidence_Document", re.IGNORECASE)
_GSPR_REQUIREMENT_SECTION = re.compile(r"B=Requirement", re.IGNORECASE)
_GSPR_APPLICABLE_SECTION = re.compile(r"C=Applicable", re.IGNORECASE)
_GSPR_STATUS_SECTION = re.compile(r"E=Status", re.IGNORECASE)

_GSPR_APPLICABLE_VALUES = frozenset({"yes", "y", "true", "1", "applicable"})
_GSPR_NOT_APPLICABLE_VALUES = frozenset(
    {"no", "n", "false", "0", "not applicable", "n/a", "na"}
)

# Parse the trailing row number from a GSPR cell label, e.g. "GSPR:B5" -> 5.
_GSPR_ROW_FROM_LABEL = re.compile(r"^[^:]+:[A-Z](\d+)$")

# Extractor version IDs - changing these changes all downstream claim IDs.
_EXTRACTOR_NUMERIC_PCT = "extract.numeric.percentage:v1"
_EXTRACTOR_NUMERIC_CI = "extract.numeric.ci:v1"
_EXTRACTOR_NUMERIC_COUNT = "extract.numeric.count:v1"
_EXTRACTOR_NUMERIC_VALUE_UNIT = "extract.numeric.value_unit:v1"
_EXTRACTOR_CLASSIFICATION = "extract.classification:v1"
_EXTRACTOR_CLINICAL_PERFORMANCE = "extract.clinical_performance:v1"
_EXTRACTOR_CITATION = "extract.citation.author_year:v1"

# P3 entity/classification extractor IDs.
_EXTRACTOR_MR_CONDITIONAL = "extract.classification.mr_conditional:v1"
_EXTRACTOR_NB_NUMBER = "extract.classification.nb_number:v1"
_EXTRACTOR_BASIC_UDI_DI = "extract.classification.basic_udi_di:v1"
_EXTRACTOR_EMDN_CODE = "extract.classification.emdn_code:v1"
_EXTRACTOR_HARMONIZED_STANDARD = "extract.classification.harmonized_standard:v1"

# Tesla context guard — match window (chars) around the Tesla value.
_TESLA_CONTEXT_CHARS = 200

# RBP context gate — (atm) must appear within this many chars of an RBP match.
_RBP_ATM_WINDOW_CHARS = 500

# Pattern for "percent" spelled out after a decimal number, capturing up to
# 40 characters of trailing context (e.g. "87.4 percent at 12 months").
# Stops at sentence-ending punctuation or parenthetical.
_PERCENT_WORD = re.compile(
    r"(?<!\d)(?P<value>\d{1,3}\.\d+)\s+percent(?P<ctx>[^.()\[\]]{0,40})?",
    re.IGNORECASE,
)

# Contextual window for clinical performance claims (characters around keyword)
_CP_CONTEXT_CHARS = 120


def _normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip."""
    return " ".join(text.lower().split())


class ClaimExtractor:
    """Deterministic regex + structural claim extraction from spans."""

    _citation_parser: CitationParser
    _gspr_rows_with_evidence_doc: frozenset[tuple[str, int]]
    _gspr_applicable_rows: frozenset[tuple[str, int]]

    def __init__(self) -> None:
        self._citation_parser = CitationParser()
        self._gspr_rows_with_evidence_doc = frozenset()
        self._gspr_applicable_rows = frozenset()

    def extract_claims(
        self,
        spans: Sequence[Span],
        documents: Sequence[Document],
    ) -> list[Claim]:
        """Extract candidate claims from all spans.

        Returns claims sorted by claim_id for deterministic output.
        """
        doc_map = {d.document_id: d for d in documents}
        self._gspr_rows_with_evidence_doc = _compute_gspr_rows_with_evidence_doc(spans)
        self._gspr_applicable_rows = _compute_gspr_applicable_rows(spans)
        claims: list[Claim] = []
        for span in spans:
            doc = doc_map.get(span.document_id)
            claims.extend(self._extract_from_span(span, doc))
        claims.sort(key=lambda c: c.claim_id)
        return claims

    def _extract_from_span(self, span: Span, doc: Document | None) -> list[Claim]:
        if is_non_claim_noise_span(span, doc):
            return []
        claims: list[Claim] = []
        claims.extend(self._extract_numeric(span))
        claims.extend(self._extract_value_unit(span))
        claims.extend(self._extract_classification(span))
        claims.extend(self._extract_clinical_performance(span))
        claims.extend(self._extract_completeness(span, doc))
        claims.extend(self._extract_citation_claims(span))
        return claims

    # ---- Numeric extraction ----

    def _extract_numeric(self, span: Span) -> list[Claim]:
        claims: list[Claim] = []
        text = span.text

        occurrence_counters: dict[tuple[str, str], int] = {}

        def _make(normalized: str, raw_text: str, extractor_id: str) -> Claim:
            key = (extractor_id, normalized)
            occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
            occurrence_index = occurrence_counters[key]
            claim_id = make_claim_id(
                span.document_id,
                span.span_id,
                normalized,
                extractor_id,
                occurrence_index,
            )
            return Claim(
                claim_id=claim_id,
                document_id=span.document_id,
                span_id=span.span_id,
                text=raw_text,
                claim_type=ClaimType.NUMERIC,
                extraction_method=extractor_id,
                confidence_label=ConfidenceLabel.HIGH,
            )

        # Track character ranges consumed by PERCENTAGE_WITH_CI so we don't
        # double-count the percentage value or the CI range separately.
        consumed_ranges: list[tuple[int, int]] = []

        # Compound percentage+CI pattern (e.g. "87.4% (95% CI: 82.1-91.6)")
        for m in PERCENTAGE_WITH_CI.finditer(text):
            raw = (m.group("pct") + " " + m.group("ci_paren")).strip()
            consumed_ranges.append((m.start(), m.end()))
            normalized = _normalize_text(raw)
            claims.append(_make(normalized, raw, _EXTRACTOR_NUMERIC_PCT))

        def _in_consumed(start: int, end: int) -> bool:
            return any(cs <= start < ce or cs < end <= ce for cs, ce in consumed_ranges)

        # FM-IFU-2: suppress bare-percentage extraction for IFU foreshortening
        # table spans.  Detection is text-based — no span.location.kind or
        # DocumentKind dependency.  PERCENTAGE_WITH_CI and CI_RANGE loops are
        # not affected (they continue below regardless).
        _skip_pct_decimal = is_foreshortening_table_span(text)

        # Bare percentage with % symbol
        if not _skip_pct_decimal:
            for m in PERCENTAGE_DECIMAL.finditer(text):
                if _in_consumed(m.start(), m.end()):
                    continue
                raw = m.group(0).strip()
                normalized = _normalize_text(raw)
                claims.append(_make(normalized, raw, _EXTRACTOR_NUMERIC_PCT))

        # "percent" spelled out (for PDF text like "87.4 percent")
        if not _skip_pct_decimal:
            for m in _PERCENT_WORD.finditer(text):
                if _in_consumed(m.start(), m.end()):
                    continue
                raw = m.group(0).strip()
                normalized = _normalize_text(raw)
                claims.append(_make(normalized, raw, _EXTRACTOR_NUMERIC_PCT))

        # CI ranges not already consumed by PERCENTAGE_WITH_CI
        for m in CI_RANGE.finditer(text):
            if _in_consumed(m.start(), m.end()):
                continue
            raw = m.group("ci").strip()
            normalized = _normalize_text(raw)
            claims.append(_make(normalized, raw, _EXTRACTOR_NUMERIC_CI))

        # Count (n=NNN)
        for m in COUNT_N.finditer(text):
            raw = m.group(0).strip()
            normalized = _normalize_text(raw)
            claims.append(_make(normalized, raw, _EXTRACTOR_NUMERIC_COUNT))

        return claims

    # ---- Value-Unit extraction (Phase 2D) ----

    def _extract_value_unit(self, span: Span) -> list[Claim]:
        """Extract physical measurement claims with explicit unit tokens.

        Emits ClaimType.NUMERIC claims with extraction_method
        "extract.numeric.value_unit:v1".  Runs after _extract_numeric so the
        _skip_pct_decimal foreshortening gate (P1) remains scoped to that method
        only and does not suppress atm/mmHg claims from the same span (R-2).

        Dedup: consumed_ranges tracks character spans already emitted so that a
        range match like "-40 to +400 mmHg" does not also produce a separate
        single-value claim for "+400 mmHg".
        """
        text = span.text
        claims: list[Claim] = []
        consumed_ranges: list[tuple[int, int]] = []
        occurrence_counters: dict[tuple[str, str], int] = {}

        def _in_consumed(start: int, end: int) -> bool:
            return any(
                cs <= start < ce or cs < end <= ce
                for cs, ce in consumed_ranges
            )

        def _emit(raw_text: str, start: int, end: int) -> None:
            if _in_consumed(start, end):
                return
            consumed_ranges.append((start, end))
            normalized = _normalize_text(raw_text)
            key = (_EXTRACTOR_NUMERIC_VALUE_UNIT, normalized)
            occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
            occurrence_index = occurrence_counters[key]
            claim_id = make_claim_id(
                span.document_id,
                span.span_id,
                normalized,
                _EXTRACTOR_NUMERIC_VALUE_UNIT,
                occurrence_index,
            )
            claims.append(
                Claim(
                    claim_id=claim_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    text=raw_text,
                    claim_type=ClaimType.NUMERIC,
                    extraction_method=_EXTRACTOR_NUMERIC_VALUE_UNIT,
                    confidence_label=ConfidenceLabel.HIGH,
                )
            )

        # 1. Range: "-40 to +400 mmHg" — single claim, verbatim raw match.
        for m in VALUE_UNIT_RANGE.finditer(text):
            _emit(m.group(0), m.start(), m.end())

        # 2. Mean ± SD: "24 ± 26 mmHg".
        for m in VALUE_UNIT_MEAN_SD.finditer(text):
            _emit(m.group(0), m.start(), m.end())

        # 3. Drift: "3.0 mmHg drift in 100 h".
        for m in VALUE_UNIT_DRIFT.finditer(text):
            _emit(m.group(0), m.start(), m.end())

        # 4. Spelled-out threshold: "up to 29 days", "less than 2 °C".
        for m in VALUE_UNIT_THRESHOLD_WORDS.finditer(text):
            _emit(m.group(0), m.start(), m.end())

        # 5. Operator threshold: "≥ 12 years", "< 2 °C".
        for m in VALUE_UNIT_THRESHOLD.finditer(text):
            _emit(m.group(0), m.start(), m.end())

        # 6. Single value + unit: "2500 gauss/cm", "2.0 W/kg", "25 °C".
        for m in VALUE_UNIT_SINGLE.finditer(text):
            _emit(m.group(0), m.start(), m.end())

        # 7. Tesla (T) — tight context guard (R-1): require MRI context within
        # ±200 chars.  Fires only when the span contains recognizable MRI
        # vocabulary near the Tesla value.
        for m in VALUE_UNIT_TESLA.finditer(text):
            pos = m.start()
            window_start = max(0, pos - _TESLA_CONTEXT_CHARS)
            window_end = min(len(text), m.end() + _TESLA_CONTEXT_CHARS)
            window = text[window_start:window_end]
            if _MRI_CONTEXT.search(window):
                _emit(m.group(0), m.start(), m.end())

        # 8. RBP context gate (D-1 Option B — owner-validated):
        # Emit ALL RBP matches when "(atm)" appears within ±500 chars of each
        # match in the same span.  First emitted match uses a wider excerpt
        # text[atm_pos : m.end()] so the (atm) header appears in claim.text,
        # satisfying test_rbp_7_atm_extracted_from_foreshortening_span.
        # Subsequent matches use the raw match text (e.g. "RBP = 6.0").
        # consumed_ranges always tracks (m.start(), m.end()) — the actual match
        # span — so later matches are never incorrectly blocked.
        atm_pos = text.find("(atm)")
        if atm_pos != -1:
            first_emitted = False
            for m in _VALUE_UNIT_RBP.finditer(text):
                dist = abs(m.start() - atm_pos)
                if dist <= _RBP_ATM_WINDOW_CHARS:
                    if not first_emitted:
                        # Verbatim excerpt from (atm) through end of match.
                        claim_text = text[atm_pos : m.end()]
                        first_emitted = True
                    else:
                        # Raw match only for subsequent values.
                        claim_text = text[m.start() : m.end()]
                    _emit(claim_text, m.start(), m.end())

        return claims

    # ---- Classification extraction ----

    def _extract_classification(self, span: Span) -> list[Claim]:
        claims: list[Claim] = []
        text = span.text

        for pattern in (CLASS_IIA, CLASS_III, CLASS_I):
            m = pattern.search(text)
            if m:
                raw = m.group(0).strip()
                normalized = _normalize_text(raw)
                claim_id = make_claim_id(
                    span.document_id,
                    span.span_id,
                    normalized,
                    _EXTRACTOR_CLASSIFICATION,
                    1,
                )
                claims.append(
                    Claim(
                        claim_id=claim_id,
                        document_id=span.document_id,
                        span_id=span.span_id,
                        text=raw,
                        claim_type=ClaimType.CLASSIFICATION,
                        extraction_method=_EXTRACTOR_CLASSIFICATION,
                        confidence_label=ConfidenceLabel.HIGH,
                    )
                )

        # P3 family 1 — MR Conditional.
        claims.extend(self._extract_mr_conditional(span, text))

        # P3 family 2 — NB number.
        claims.extend(self._extract_nb_number(span, text))

        # P3 family 3 — Basic UDI-DI.
        claims.extend(self._extract_basic_udi_di(span, text))

        # P3 family 4 — EMDN code.
        claims.extend(self._extract_emdn_code(span, text))

        # P3 family 5 — Harmonized standards.
        claims.extend(self._extract_harmonized_standard(span, text))

        return claims

    def _make_entity_claim(
        self,
        span: Span,
        raw: str,
        extractor_id: str,
        occurrence_index: int,
        *,
        claim_type: ClaimType = ClaimType.CLASSIFICATION,
    ) -> Claim:
        normalized = _normalize_text(raw)
        claim_id = make_claim_id(
            span.document_id,
            span.span_id,
            normalized,
            extractor_id,
            occurrence_index,
        )
        return Claim(
            claim_id=claim_id,
            document_id=span.document_id,
            span_id=span.span_id,
            text=raw,
            claim_type=claim_type,
            extraction_method=extractor_id,
            confidence_label=ConfidenceLabel.HIGH,
        )

    def _extract_mr_conditional(self, span: Span, text: str) -> list[Claim]:
        """Extract 'MR Conditional' / 'MR conditional' label claims."""
        claims: list[Claim] = []
        occurrence_counters: dict[str, int] = {}
        for m in MR_CONDITIONAL.finditer(text):
            raw = m.group(0).strip()
            occurrence_counters[raw] = occurrence_counters.get(raw, 0) + 1
            claims.append(
                self._make_entity_claim(
                    span, raw, _EXTRACTOR_MR_CONDITIONAL, occurrence_counters[raw]
                )
            )
        return claims

    def _extract_nb_number(self, span: Span, text: str) -> list[Claim]:
        """Extract Notified Body 4-digit numbers with mandatory label prefix."""
        claims: list[Claim] = []
        occurrence_counters: dict[str, int] = {}
        for m in NB_NUMBER_INLINE.finditer(text):
            raw = m.group(0).strip()
            occurrence_counters[raw] = occurrence_counters.get(raw, 0) + 1
            claims.append(
                self._make_entity_claim(
                    span, raw, _EXTRACTOR_NB_NUMBER, occurrence_counters[raw]
                )
            )
        return claims

    def _extract_basic_udi_di(self, span: Span, text: str) -> list[Claim]:
        """Extract Basic UDI-DI codes anchored to label presence."""
        if not UDI_DI_LABEL.search(text):
            return []
        claims: list[Claim] = []
        occurrence_counters: dict[str, int] = {}
        for m in BASIC_UDI_DI.finditer(text):
            raw = m.group("code").strip()
            occurrence_counters[raw] = occurrence_counters.get(raw, 0) + 1
            claims.append(
                self._make_entity_claim(
                    span, raw, _EXTRACTOR_BASIC_UDI_DI, occurrence_counters[raw]
                )
            )
        return claims

    def _extract_emdn_code(self, span: Span, text: str) -> list[Claim]:
        """Extract EMDN codes anchored to 'EMDN' keyword presence."""
        if not EMDN_LABEL.search(text):
            return []
        claims: list[Claim] = []
        occurrence_counters: dict[str, int] = {}
        for m in EMDN_CODE.finditer(text):
            raw = m.group("code").strip()
            occurrence_counters[raw] = occurrence_counters.get(raw, 0) + 1
            claims.append(
                self._make_entity_claim(
                    span, raw, _EXTRACTOR_EMDN_CODE, occurrence_counters[raw]
                )
            )
        return claims

    def _extract_harmonized_standard(self, span: Span, text: str) -> list[Claim]:
        """Extract harmonized standard references (EN ISO, ISO, IEC, ASTM, EN, USP-NF)."""
        claims: list[Claim] = []
        occurrence_counters: dict[str, int] = {}
        for m in HARMONIZED_STANDARD.finditer(text):
            body = m.group("body")
            code = m.group("code").strip()
            # Validate: code must contain at least one digit and be ≥3 chars total.
            if not any(ch.isdigit() for ch in code):
                continue
            if len(code) < 3:
                continue
            raw = f"{body} {code}"
            occurrence_counters[raw] = occurrence_counters.get(raw, 0) + 1
            claims.append(
                self._make_entity_claim(
                    span,
                    raw,
                    _EXTRACTOR_HARMONIZED_STANDARD,
                    occurrence_counters[raw],
                    claim_type=ClaimType.STANDARD_REFERENCE,
                )
            )
        return claims

    # ---- Clinical performance extraction ----

    def _extract_clinical_performance(self, span: Span) -> list[Claim]:
        """Extract clinical performance claims from keyword-bearing spans.

        A clinical_performance claim is anchored to the keyword match and
        carries a context window of surrounding text as its claim text.
        Spans are skipped if they are table cells (table values are captured
        by numeric extractors instead).

        FM-PHASE2-2 gate: for PAGE spans, strip any SSCP/RAUMEDIC running
        page header prefix from the working text before keyword matching.
        The original span.text, span_id, and document_id are never mutated;
        all emitted claims carry the original provenance.
        """
        if span.location.kind == SpanLocationKind.TABLE_CELL:
            return []

        claims: list[Claim] = []
        # FM-PHASE2-2: use header-stripped text for keyword search on PAGE spans.
        # span.text is never mutated; the stripped version is a local variable.
        if span.location.kind == SpanLocationKind.PAGE:
            search_text = strip_sscp_page_header(span.text)
        else:
            search_text = span.text
        # value equality: True iff strip_sscp_page_header removed a header prefix.
        # strip_sscp_page_header must return the exact input string when no header
        # is recognized; if a future change normalizes whitespace here, the
        # supplementary keyword loop below would fire incorrectly.
        header_was_stripped = search_text != span.text
        seen_normalized: set[str] = set()

        def _emit_cp_match(m: re.Match[str]) -> None:
            start = max(0, m.start() - _CP_CONTEXT_CHARS)
            end = min(len(search_text), m.end() + _CP_CONTEXT_CHARS)
            raw = search_text[start:end].strip()
            # FM-PHASE2-2: suppress keyword matches whose context window is the
            # SSCP standard boilerplate intro paragraph ("intended to provide
            # public access…").  That text is a document self-description, not
            # an evidence claim.
            if is_sscp_boilerplate_cp_context(raw):
                return
            normalized = _normalize_text(raw)
            # Two keywords whose context windows yield the same normalized text
            # collapse into one claim; the claim's identity is the normalized
            # text, not the triggering keyword position.  Deduplication is
            # shared across both regex passes so a range matched by the global
            # set is not re-emitted by the supplementary set.
            if normalized in seen_normalized:
                return
            seen_normalized.add(normalized)

            claim_id = make_claim_id(
                span.document_id,
                span.span_id,
                normalized,
                _EXTRACTOR_CLINICAL_PERFORMANCE,
                1,
            )
            claims.append(
                Claim(
                    claim_id=claim_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    text=raw,
                    claim_type=ClaimType.CLINICAL_PERFORMANCE,
                    extraction_method=_EXTRACTOR_CLINICAL_PERFORMANCE,
                    confidence_label=ConfidenceLabel.HIGH,
                )
            )

        for m in CLINICAL_PERFORMANCE_KEYWORDS.finditer(search_text):
            _emit_cp_match(m)

        # Supplementary keywords (outcome, incidence) apply only when a header
        # was actually stripped — recall expansion is gated on SSCP page context.
        if header_was_stripped:
            for m in POST_HEADER_STRIP_CP_KEYWORDS.finditer(search_text):
                _emit_cp_match(m)

        return claims

    # ---- Citation claim extraction ----

    def _extract_citation_claims(self, span: Span) -> list[Claim]:
        """Emit CITATION-type claims for detected author-year citation markers.

        Each author-year citation marker (parenthetical or table-cell) in a span
        is surfaced as a Claim with claim_type=CITATION. This allows citation
        mentions to participate in evidence linking as first-class claim records.
        Bracketed-numeric citations are NOT emitted as CITATION claims since they
        cannot be normalized to an author-year key without a references list.
        """
        mentions = self._citation_parser.parse_citations([span])
        claims: list[Claim] = []
        occurrence_counters: dict[str, int] = {}

        for m in mentions:
            if m["marker_form"] == "numeric_bracketed":
                continue  # numeric markers cannot resolve; do not emit CITATION claim
            marker = m["marker_text"].strip()
            normalized = _normalize_text(marker)
            occurrence_counters[normalized] = occurrence_counters.get(normalized, 0) + 1
            occurrence_index = occurrence_counters[normalized]

            claim_id = make_claim_id(
                span.document_id,
                span.span_id,
                normalized,
                _EXTRACTOR_CITATION,
                occurrence_index,
            )
            claims.append(
                Claim(
                    claim_id=claim_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    text=marker,
                    claim_type=ClaimType.CITATION,
                    extraction_method=_EXTRACTOR_CITATION,
                    confidence_label=ConfidenceLabel.HIGH,
                )
            )
        return claims

    # ---- Completeness extraction (GSPR evidence document references) ----

    _EXTRACTOR_COMPLETENESS = "extract.completeness.gspr:v1"

    def _extract_completeness(self, span: Span, doc: Document | None) -> list[Claim]:
        """Extract completeness claims for GSPR rows with no Evidence_Document cell.

        Fires only on a Requirement (column B) whose row is explicitly applicable
        (column C), is not marked Not Applicable in Status (column E), and has no
        Evidence_Document (column D). The xlsx_reader drops empty cells, so an
        absent D-column on an eligible B-column row is the signal. Rows with a
        declared Evidence_Document — even an unresolvable one — are handled by
        the source-availability checker.
        """
        if doc is None or doc.kind != DocumentKind.GSPR_MAPPING:
            return []
        section = span.section or ""
        if not _GSPR_REQUIREMENT_SECTION.search(section):
            return []
        text = span.text.strip()
        if not text:
            return []
        row_number = _row_number_from_label(span.location.label)
        if row_number is None:
            return []
        row_key = (span.document_id, row_number)
        if row_key not in self._gspr_applicable_rows:
            return []
        if row_key in self._gspr_rows_with_evidence_doc:
            return []
        normalized = _normalize_text(text)
        claim_id = make_claim_id(
            span.document_id,
            span.span_id,
            normalized,
            self._EXTRACTOR_COMPLETENESS,
            1,
        )
        return [
            Claim(
                claim_id=claim_id,
                document_id=span.document_id,
                span_id=span.span_id,
                text=text,
                claim_type=ClaimType.COMPLETENESS,
                extraction_method=self._EXTRACTOR_COMPLETENESS,
                confidence_label=ConfidenceLabel.HIGH,
            )
        ]


def _row_number_from_label(label: str | None) -> int | None:
    if not label:
        return None
    match = _GSPR_ROW_FROM_LABEL.match(label)
    if not match:
        return None
    return int(match.group(1))


def _compute_gspr_rows_with_evidence_doc(
    spans: Sequence[Span],
) -> frozenset[tuple[str, int]]:
    rows: set[tuple[str, int]] = set()
    for span in spans:
        section = span.section or ""
        if not _GSPR_EVIDENCE_DOC_SECTION.search(section):
            continue
        row_number = _row_number_from_label(span.location.label)
        if row_number is None:
            continue
        rows.add((span.document_id, row_number))
    return frozenset(rows)


def _compute_gspr_applicable_rows(
    spans: Sequence[Span],
) -> frozenset[tuple[str, int]]:
    applicability_by_row: dict[tuple[str, int], str] = {}
    status_by_row: dict[tuple[str, int], str] = {}
    for span in spans:
        row_number = _row_number_from_label(span.location.label)
        if row_number is None:
            continue
        row_key = (span.document_id, row_number)
        section = span.section or ""
        value = _normalize_text(span.text)
        if _GSPR_APPLICABLE_SECTION.search(section):
            applicability_by_row[row_key] = value
        elif _GSPR_STATUS_SECTION.search(section):
            status_by_row[row_key] = value

    return frozenset(
        row_key
        for row_key, value in applicability_by_row.items()
        if value in _GSPR_APPLICABLE_VALUES
        and status_by_row.get(row_key) not in _GSPR_NOT_APPLICABLE_VALUES
    )
