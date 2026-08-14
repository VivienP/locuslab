"""Unit tests for CitationParser - written before implementation (TDD)."""

from __future__ import annotations

import pytest

from locuslab.models import Span, SpanLocation, SpanLocationKind


def _make_span(
    span_id: str,
    document_id: str,
    text: str,
    kind: SpanLocationKind = SpanLocationKind.PARAGRAPH,
    index: int = 0,
    section: str | None = None,
) -> Span:
    return Span(
        span_id=span_id,
        document_id=document_id,
        location=SpanLocation(kind=kind, index=index),
        text=text,
        section=section,
    )


PIVOTAL_SPAN_ID = "span_b0fecd4907e13acc"
BENEFIT_RISK_SPAN_ID = "span_05f0a0e4c6224e9f"
TABLE_CITATION_SPAN_ID = "span_f806d14a167a8098"
TABLE_CITATION_SPAN2_ID = "span_b4c87ceb0705b8d7"

DOC_ID_CER = "doc_1dd5a3cd674157b5"

PIVOTAL_TEXT = (
    "The primary endpoint response rate of 87.4% (95% CI: 82.1-91.6) "
    "was achieved in (n=412) participants (Smith et al., 2023)."
)
BENEFIT_RISK_TEXT = (
    "The benefit-risk profile of DemoDevice X100 is considered acceptable [1]."
)
TABLE_CITATION_TEXT = "Smith 2023"


@pytest.fixture()
def parser():  # type: ignore[return]
    from locuslab.extract.citation_parser import CitationParser

    return CitationParser()


class TestAuthorYearParenthetical:
    def test_author_year_parenthetical(self, parser):
        """GOLD-CITE-001: detect (Smith et al., 2023) in pivotal span."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        mentions = parser.parse_citations([span])
        paren_mentions = [m for m in mentions if m["marker_form"] == "author_year_parenthetical"]
        assert paren_mentions, f"No author_year_parenthetical found; all={mentions}"
        m = paren_mentions[0]
        assert m["document_id"] == DOC_ID_CER
        assert m["span_id"] == PIVOTAL_SPAN_ID
        assert "Smith" in m["marker_text"]
        assert "2023" in m["marker_text"]
        assert m["normalized_key"] == "smith_2023"

    def test_no_false_positive_on_statistics(self, parser):
        """(n=412) must NOT be detected as a citation."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        mentions = parser.parse_citations([span])
        texts = [m["marker_text"] for m in mentions]
        assert not any("n=412" in t for t in texts), f"(n=412) falsely detected: {texts}"

    def test_no_false_positive_on_ci_range(self, parser):
        """(95% CI: 82.1-91.6) must NOT be detected as a citation."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        mentions = parser.parse_citations([span])
        texts = [m["marker_text"] for m in mentions]
        assert not any("CI" in t and "82.1" in t for t in texts), (
            f"(95% CI) falsely detected: {texts}"
        )


class TestAuthorYearTableCell:
    def test_author_year_table_cell(self, parser):
        """GOLD-CITE-003: detect Smith 2023 in TABLE_CELL span."""
        span = _make_span(
            TABLE_CITATION_SPAN_ID,
            DOC_ID_CER,
            TABLE_CITATION_TEXT,
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions, f"No author_year_table_cell found; all={mentions}"
        m = table_mentions[0]
        assert m["span_id"] == TABLE_CITATION_SPAN_ID
        assert m["normalized_key"] == "smith_2023"

    def test_author_year_table_cell_second_occurrence(self, parser):
        """GOLD-CITE-004: detect Smith 2023 in second TABLE_CELL span."""
        span = _make_span(
            TABLE_CITATION_SPAN2_ID,
            DOC_ID_CER,
            TABLE_CITATION_TEXT,
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions, f"No author_year_table_cell for second span; all={mentions}"
        assert table_mentions[0]["span_id"] == TABLE_CITATION_SPAN2_ID

    def test_table_cell_pattern_not_applied_to_body_paragraph(self, parser):
        """Table-cell pattern must NOT fire on non-TABLE_CELL spans."""
        # "Smith 2023" as full paragraph text - must use parenthetical match not table match
        span = _make_span(
            "span_some_para",
            DOC_ID_CER,
            "Smith 2023",
            kind=SpanLocationKind.PARAGRAPH,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert not table_mentions, f"author_year_table_cell fired on paragraph: {table_mentions}"


class TestBracketedNumeric:
    def test_bracketed_numeric(self, parser):
        """GOLD-CITE-002: detect [1] in benefit-risk span."""
        span = _make_span(BENEFIT_RISK_SPAN_ID, DOC_ID_CER, BENEFIT_RISK_TEXT)
        mentions = parser.parse_citations([span])
        bracket_mentions = [m for m in mentions if m["marker_form"] == "numeric_bracketed"]
        assert bracket_mentions, f"No numeric_bracketed found; all={mentions}"
        m = bracket_mentions[0]
        assert m["span_id"] == BENEFIT_RISK_SPAN_ID
        assert "[1]" in m["marker_text"]
        assert m["normalized_key"] is None


class TestCitationIdStability:
    def test_citation_ids_are_stable(self, parser):
        """Stability invariant: two identical calls produce identical mention IDs."""
        span = _make_span(PIVOTAL_SPAN_ID, DOC_ID_CER, PIVOTAL_TEXT)
        mentions1 = parser.parse_citations([span])
        mentions2 = parser.parse_citations([span])
        ids1 = {m["mention_id"] for m in mentions1}
        ids2 = {m["mention_id"] for m in mentions2}
        assert ids1 == ids2, "Mention IDs differ across identical calls"


class TestRefIdNumeric:
    """REF-NNN proprietary citation marker support (cardiopatch-x1 dogfood FM-1)."""

    def test_ref_id_numeric_inline_body(self, parser):
        text = "As shown in REF-012, sensitivity was 94.8% in the pivotal study."
        span = _make_span(
            "span_ref_inline_body",
            DOC_ID_CER,
            text,
            section="6. Clinical performance evidence",
        )
        mentions = parser.parse_citations([span])
        ref_mentions = [m for m in mentions if m["marker_form"] == "ref_id_numeric"]
        assert len(ref_mentions) == 1, f"Expected 1 ref_id_numeric; got: {mentions}"
        m = ref_mentions[0]
        assert m["marker_text"] == "REF-012"
        assert m["normalized_key"] == "ref_012"
        assert m["occurrence_index"] == 1

    def test_ref_id_numeric_multiple_in_one_span(self, parser):
        text = "Contradicted by REF-018 but supported by REF-001 and REF-012."
        span = _make_span(
            "span_ref_multi",
            DOC_ID_CER,
            text,
            section="6. Clinical performance evidence",
        )
        mentions = parser.parse_citations([span])
        ref_mentions = [m for m in mentions if m["marker_form"] == "ref_id_numeric"]
        keys = sorted(m["normalized_key"] for m in ref_mentions if m["normalized_key"])
        assert keys == ["ref_001", "ref_012", "ref_018"], (
            f"Expected three distinct REF mentions; got: {keys}"
        )

    def test_ref_id_numeric_in_table_cell(self, parser):
        span = _make_span(
            "span_ref_table_cell",
            DOC_ID_CER,
            "REF-010",
            kind=SpanLocationKind.TABLE_CELL,
            section="Evidence",
        )
        mentions = parser.parse_citations([span])
        ref_mentions = [m for m in mentions if m["marker_form"] == "ref_id_numeric"]
        assert len(ref_mentions) == 1, f"Expected 1 ref_id_numeric; got: {mentions}"
        assert ref_mentions[0]["normalized_key"] == "ref_010"

    def test_ref_id_numeric_suppressed_in_bibliography_span_by_section(self, parser):
        """REF-001. line in 'References' section -> 0 mentions (bibliography filter)."""
        text = "REF-001. Martin A. Ambulatory ECG patch validation. 2023."
        span = _make_span(
            "span_ref_bib_section",
            DOC_ID_CER,
            text,
            section="References used in this synthetic dossier",
        )
        mentions = parser.parse_citations([span])
        assert mentions == [], (
            f"Bibliography section should suppress all citations; got: {mentions}"
        )

    def test_ref_id_numeric_suppressed_in_bibliography_span_by_prefix(self, parser):
        """REF-001. line with no section -> 0 mentions (prefix filter)."""
        text = "REF-001. Martin A. Ambulatory ECG patch validation. 2023."
        span = _make_span("span_ref_bib_prefix", DOC_ID_CER, text)
        mentions = parser.parse_citations([span])
        assert mentions == [], (
            f"REF-NNN. prefix should suppress all citations; got: {mentions}"
        )

    def test_ref_id_numeric_rejects_word_reference(self, parser):
        text = "See REFERENCE 1 for context (no REF-style ID present here)."
        span = _make_span("span_ref_word", DOC_ID_CER, text)
        mentions = parser.parse_citations([span])
        ref_mentions = [m for m in mentions if m["marker_form"] == "ref_id_numeric"]
        assert ref_mentions == [], (
            f"'REFERENCE 1' must not match REF-NNN; got: {ref_mentions}"
        )

    def test_ref_id_numeric_accepts_four_digits(self, parser):
        text = "Cross-check with REF-1234 in the audit log."
        span = _make_span("span_ref_4digit", DOC_ID_CER, text)
        mentions = parser.parse_citations([span])
        ref_mentions = [m for m in mentions if m["marker_form"] == "ref_id_numeric"]
        assert len(ref_mentions) == 1
        assert ref_mentions[0]["normalized_key"] == "ref_1234"

    def test_ref_id_numeric_rejects_five_digits(self, parser):
        text = "Audit log entry REF-12345 should NOT match REF-NNN."
        span = _make_span("span_ref_5digit", DOC_ID_CER, text)
        mentions = parser.parse_citations([span])
        ref_mentions = [m for m in mentions if m["marker_form"] == "ref_id_numeric"]
        # REF-12345: REF_ID_NUMERIC requires \d{1,4}\b. It will match REF-1234 then
        # \b fails before '5'. So we expect zero matches for an all-digit suffix > 4.
        assert ref_mentions == [], (
            f"5-digit REF-NNNNN must not match; got: {ref_mentions}"
        )
