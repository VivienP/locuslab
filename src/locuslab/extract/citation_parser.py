"""Citation marker detection producing CitationMention typed-dict records."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TypedDict

from locuslab.extract.patterns import (
    AUTHOR_YEAR_PAREN,
    AUTHOR_YEAR_TABLE,
    BRACKETED_NUMERIC,
    CITATION_BRACKETED_COMPOSITE,
    CITATION_NAMED_GUIDELINE,
    CITATION_NCT_ID,
    CITATION_NUMERIC_PARENTHETICAL,
    REF_ID_NUMERIC,
    normalize_author_year_key,
)
from locuslab.extract.span_filters import is_citation_noise_span
from locuslab.ingest.ids import make_citation_id
from locuslab.models import Span, SpanLocationKind

_logger = logging.getLogger(__name__)

PARSER_ID = "citation_parser:v1"


def derive_document_id_short(document_id: str) -> str:
    """Derive a short, deterministic, document-scoped identifier from document_id.

    Takes the first 8 hex characters after the "doc_" prefix. This produces a
    stable token for use in normalized_key values (e.g., footnote_3b339931_1).

    Must not be derived from filename or any human-readable token — those are
    fragile to renames. Only the document_id hash is stable across runs.

    document_id format: "doc_<16 hex chars>" (from make_document_id in ingest/ids.py).

    Raises:
        ValueError: if the input does not contain at least 8 hex characters after
            the "doc_" prefix.
    """
    if not document_id.startswith("doc_"):
        raise ValueError(
            f"document_id {document_id!r} must contain at least 8 hex characters"
            f" after 'doc_' prefix"
        )
    hex_part = document_id[4:]
    valid_hex = set("0123456789abcdefABCDEF")
    if len(hex_part) < 8 or not all(c in valid_hex for c in hex_part[:8]):
        raise ValueError(
            f"document_id {document_id!r} must contain at least 8 hex characters"
            f" after 'doc_' prefix"
        )
    return hex_part[:8]


class CitationMention(TypedDict):
    """Module-level intermediate record for a detected citation marker."""

    mention_id: str
    document_id: str
    span_id: str
    marker_text: str
    marker_form: str
    # one of: "author_year_parenthetical", "author_year_table_cell",
    # "numeric_bracketed", "ref_id_numeric"
    normalized_key: str | None
    # e.g. "smith_2023" for author_year, "ref_012" for ref_id_numeric,
    # None for numeric_bracketed
    occurrence_index: int
    span_offset_start: int  # provenance only, not in ID
    span_offset_end: int  # provenance only, not in ID


class CitationParser:
    """Detect citation markers in span text."""

    def parse_citations(self, spans: Sequence[Span]) -> list[CitationMention]:
        """Parse all spans for citation markers.

        Returns mentions sorted by mention_id.
        """
        all_mentions: list[CitationMention] = []
        for span in spans:
            all_mentions.extend(self._parse_span(span))
        all_mentions.sort(key=lambda m: m["mention_id"])
        return all_mentions

    def _parse_span(self, span: Span) -> list[CitationMention]:
        if is_citation_noise_span(span):
            return []
        mentions: list[CitationMention] = []
        is_table_cell = span.location.kind == SpanLocationKind.TABLE_CELL
        text = span.text

        if is_table_cell:
            # Try anchored table-cell pattern first (stripped full-cell match)
            stripped = text.strip()
            m = AUTHOR_YEAR_TABLE.match(stripped)
            if m:
                authors = m.group("authors")
                year = m.group("year")
                norm_key = normalize_author_year_key(authors, year)
                # occurrence_index is always 1 for single-cell full matches
                occurrence_index = 1
                normalized_marker = stripped.lower()
                mention_id = make_citation_id(
                    span.document_id,
                    span.span_id,
                    normalized_marker,
                    PARSER_ID,
                    occurrence_index,
                )
                mentions.append(
                    CitationMention(
                        mention_id=mention_id,
                        document_id=span.document_id,
                        span_id=span.span_id,
                        marker_text=stripped,
                        marker_form="author_year_table_cell",
                        normalized_key=norm_key,
                        occurrence_index=occurrence_index,
                        span_offset_start=text.index(stripped) if stripped in text else 0,
                        span_offset_end=(
                            (text.index(stripped) + len(stripped))
                            if stripped in text
                            else len(stripped)
                        ),
                    )
                )
                # If table cell matched author_year_table pattern, stop here
                return mentions

        # For non-table-cell or table cells that didn't match the anchored form,
        # apply parenthetical author-year and bracketed-numeric patterns.

        # Track occurrence per (marker_form, normalized_marker) within this span
        occurrence_counters: dict[tuple[str, str], int] = {}

        # NCT trial IDs — processed before numeric patterns to prevent digit-only
        # fragments from being classified by other patterns.
        # Collect match offsets to exclude them from numeric_parenthetical matching.
        nct_match_spans: list[tuple[int, int]] = []
        for m in CITATION_NCT_ID.finditer(text):
            nct_id = m.group("nct_id")
            marker_text = m.group(0)
            normalized_marker = nct_id.lower()
            # normalized_key: nct_<8digit> (digits after "NCT" prefix, lowercase)
            norm_key = f"nct_{nct_id[3:]}"
            key = ("nct_id", normalized_marker)
            occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
            occurrence_index = occurrence_counters[key]
            mention_id = make_citation_id(
                span.document_id,
                span.span_id,
                normalized_marker,
                PARSER_ID,
                occurrence_index,
            )
            mentions.append(
                CitationMention(
                    mention_id=mention_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    marker_text=marker_text,
                    marker_form="nct_id",
                    normalized_key=norm_key,
                    occurrence_index=occurrence_index,
                    span_offset_start=m.start(),
                    span_offset_end=m.end(),
                )
            )
            nct_match_spans.append((m.start(), m.end()))

        # Named guidelines — SOCIETY YEAR Guidelines
        for m in CITATION_NAMED_GUIDELINE.finditer(text):
            society_raw = m.group("society")
            year = m.group("year")
            marker_text = m.group(0)
            normalized_marker = marker_text.lower().strip()
            # normalized_key: lowercase society tokens joined by "_", then year
            # e.g. "ACC/AHA" -> "acc_aha", "ESC" -> "esc"
            society_tokens = society_raw.lower().replace("/", "_")
            norm_key = f"{society_tokens}_{year}"
            key = ("named_guideline", normalized_marker)
            occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
            occurrence_index = occurrence_counters[key]
            mention_id = make_citation_id(
                span.document_id,
                span.span_id,
                normalized_marker,
                PARSER_ID,
                occurrence_index,
            )
            mentions.append(
                CitationMention(
                    mention_id=mention_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    marker_text=marker_text,
                    marker_form="named_guideline",
                    normalized_key=norm_key,
                    occurrence_index=occurrence_index,
                    span_offset_start=m.start(),
                    span_offset_end=m.end(),
                )
            )

        # Author-year parenthetical
        for m in AUTHOR_YEAR_PAREN.finditer(text):
            authors = m.group("authors")
            year = m.group("year")
            norm_key = normalize_author_year_key(authors, year)
            marker_text = m.group(0)
            normalized_marker = marker_text.lower().strip()
            key = ("author_year_parenthetical", normalized_marker)
            occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
            occurrence_index = occurrence_counters[key]
            mention_id = make_citation_id(
                span.document_id,
                span.span_id,
                normalized_marker,
                PARSER_ID,
                occurrence_index,
            )
            mentions.append(
                CitationMention(
                    mention_id=mention_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    marker_text=marker_text,
                    marker_form="author_year_parenthetical",
                    normalized_key=norm_key,
                    occurrence_index=occurrence_index,
                    span_offset_start=m.start(),
                    span_offset_end=m.end(),
                )
            )

        # Composite bracketed citations — pre-pass BEFORE single BRACKETED_NUMERIC.
        # [2, 3] -> two mentions with marker_text "[2]" and "[3]".
        # Collect composite offsets to exclude them from single-bracket matching.
        composite_match_spans: list[tuple[int, int]] = []
        for m in CITATION_BRACKETED_COMPOSITE.finditer(text):
            composite_match_spans.append((m.start(), m.end()))
            numbers_str = m.group("numbers")
            components = [n.strip() for n in numbers_str.split(",")]
            for number in components:
                component_text = f"[{number}]"
                normalized_marker = component_text.lower().strip()
                key = ("numeric_bracketed", normalized_marker)
                occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
                occurrence_index = occurrence_counters[key]
                mention_id = make_citation_id(
                    span.document_id,
                    span.span_id,
                    normalized_marker,
                    PARSER_ID,
                    occurrence_index,
                )
                mentions.append(
                    CitationMention(
                        mention_id=mention_id,
                        document_id=span.document_id,
                        span_id=span.span_id,
                        marker_text=component_text,
                        marker_form="numeric_bracketed",
                        normalized_key=None,
                        occurrence_index=occurrence_index,
                        span_offset_start=m.start(),
                        span_offset_end=m.end(),
                    )
                )

        # Single bracketed numeric — skip positions already covered by composite brackets
        for m in BRACKETED_NUMERIC.finditer(text):
            # Skip if this match falls inside a composite bracket match
            if any(cs <= m.start() and m.end() <= ce for cs, ce in composite_match_spans):
                continue
            marker_text = m.group(0)
            normalized_marker = marker_text.lower().strip()
            key = ("numeric_bracketed", normalized_marker)
            occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
            occurrence_index = occurrence_counters[key]
            mention_id = make_citation_id(
                span.document_id,
                span.span_id,
                normalized_marker,
                PARSER_ID,
                occurrence_index,
            )
            mentions.append(
                CitationMention(
                    mention_id=mention_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    marker_text=marker_text,
                    marker_form="numeric_bracketed",
                    normalized_key=None,
                    occurrence_index=occurrence_index,
                    span_offset_start=m.start(),
                    span_offset_end=m.end(),
                )
            )

        # Numeric parenthetical footnotes — (1) through (99).
        # Processed after NCT IDs to avoid double-matching.
        try:
            doc_short: str | None = derive_document_id_short(span.document_id)
        except ValueError as exc:
            # Non-conforming document_id (e.g. synthetic test fixture without hex suffix).
            # Skip numeric_parenthetical mentions — normalized_key would have zero entropy.
            # Logged at debug per CLAUDE.md "never swallow silently": production
            # document_ids always conform; only synthetic test IDs hit this path.
            _logger.debug(
                "Skipping numeric_parenthetical extraction for non-conforming document_id: %s",
                exc,
            )
            doc_short = None
        if doc_short is not None:
            for m in CITATION_NUMERIC_PARENTHETICAL.finditer(text):
                # Skip if the match overlaps with an NCT mention (e.g. inside (NCT...))
                if any(ns <= m.start() and m.end() <= ne for ns, ne in nct_match_spans):
                    continue
                number = m.group("number")
                marker_text = m.group(0)
                normalized_marker = marker_text.lower().strip()
                norm_key = f"footnote_{doc_short}_{number}"
                key = ("numeric_parenthetical", normalized_marker)
                occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
                occurrence_index = occurrence_counters[key]
                mention_id = make_citation_id(
                    span.document_id,
                    span.span_id,
                    normalized_marker,
                    PARSER_ID,
                    occurrence_index,
                )
                mentions.append(
                    CitationMention(
                        mention_id=mention_id,
                        document_id=span.document_id,
                        span_id=span.span_id,
                        marker_text=marker_text,
                        marker_form="numeric_parenthetical",
                        normalized_key=norm_key,
                        occurrence_index=occurrence_index,
                        span_offset_start=m.start(),
                        span_offset_end=m.end(),
                    )
                )

        # REF-NNN proprietary marker
        for m in REF_ID_NUMERIC.finditer(text):
            marker_text = m.group(0)
            number = m.group("number")
            normalized_marker = marker_text.lower()
            norm_key = f"ref_{number}"
            key = ("ref_id_numeric", normalized_marker)
            occurrence_counters[key] = occurrence_counters.get(key, 0) + 1
            occurrence_index = occurrence_counters[key]
            mention_id = make_citation_id(
                span.document_id,
                span.span_id,
                normalized_marker,
                PARSER_ID,
                occurrence_index,
            )
            mentions.append(
                CitationMention(
                    mention_id=mention_id,
                    document_id=span.document_id,
                    span_id=span.span_id,
                    marker_text=marker_text,
                    marker_form="ref_id_numeric",
                    normalized_key=norm_key,
                    occurrence_index=occurrence_index,
                    span_offset_start=m.start(),
                    span_offset_end=m.end(),
                )
            )

        return mentions
