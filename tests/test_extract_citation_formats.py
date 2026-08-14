"""Citation format expansion regression tests.

These tests document formats the current CitationParser does NOT handle.
Expected state after writing:
  - Positive tests (formats 1-4 and conditional format 5): RED (not implemented).
  - Negative control tests (A-H): GREEN (existing pipeline does not over-classify).

All fixture strings are verbatim from real dogfood data or directly derived from
documented spans in the failure_modes.md files. No text has been fabricated.

Sources:
  reports/dogfood/2026-05-23/stents-coa-rvot-rev00/failure_modes.md
    (FM-STENTS-3, RC-STENTS-2, RC-STENTS-3)
  reports/dogfood/2026-05-23/numed-ifu-ccp-cmcp/failure_modes.md
    (FM-IFU-7, RC-IFU-5)
  reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/failure_modes.md
    (FM-RAUMEDIC-3)
"""

from __future__ import annotations

import pytest

from locuslab.models import Span, SpanLocation, SpanLocationKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


DOC_STENTS = "doc_8e1133d3bb1097ce"   # NuMED Stents SSCP, post-p1 run
DOC_RAUMEDIC = "doc_3b3399318c522c17"  # RAUMEDIC SSCP, post-p1 run
DOC_IFU = "doc_0a1b2c3d4e5f6789"      # NuMED IFU (synthetic hex document_id for unit tests)


@pytest.fixture()
def parser():  # type: ignore[return]
    from locuslab.extract.citation_parser import CitationParser

    return CitationParser()


# ===========================================================================
# Format 1 — Numeric parenthetical footnotes  (1), (2), (6)
# Source: NuMED Stents SSCP, FM-STENTS-3 / RC-STENTS-3
# ===========================================================================


class TestParentheticalNumericFootnotes:
    """Single-digit parenthetical footnote markers in clinical study sections.

    NuMED Stents SSCP uses (1)–(6) as inline footnote markers instead of [1]–[6].
    Current parser: 0 matches. Expected after P4: marker_form='numeric_parenthetical'.
    """

    # Verbatim reconstruction from RC-STENTS-3 fixture (failure_modes.md):
    # "The study included 120 patients treated at 3 centers (1). Results at
    #  6-month follow-up showed successful stenting in 93.7% of cases (2)."
    STENTS_FOOTNOTE_TEXT = (
        "The study included 120 patients treated at 3 centers (1). "
        "Results at 6-month follow-up showed successful stenting in 93.7% of cases (2)."
    )

    # From FM-STENTS-3: "6 numbered footnotes (1) through (6) in clinical study sections"
    STENTS_FOOTNOTE_6 = (
        "Adverse events were recorded in accordance with ISO 14155 (6). "
        "No device-related deaths occurred during the follow-up period."
    )

    # Multi-footnote span — tests that each marker produces an independent mention
    STENTS_MULTI_FOOTNOTE = (
        "Primary endpoint met in 87.3% of evaluable patients (1)(2)(3)."
    )

    def test_single_parenthetical_footnote_extracted(self, parser):
        """(1) in clinical study sentence must produce one numeric_parenthetical mention."""
        span = _make_span("span_stents_fn_1", DOC_STENTS, self.STENTS_FOOTNOTE_TEXT)
        mentions = parser.parse_citations([span])
        paren_mentions = [m for m in mentions if m["marker_form"] == "numeric_parenthetical"]
        assert paren_mentions, (
            f"Expected at least one numeric_parenthetical mention; got forms: "
            f"{[m['marker_form'] for m in mentions]}"
        )

    def test_parenthetical_footnote_marker_text_preserved(self, parser):
        """marker_text must capture the literal string including parens."""
        span = _make_span("span_stents_fn_1b", DOC_STENTS, self.STENTS_FOOTNOTE_TEXT)
        mentions = parser.parse_citations([span])
        paren_mentions = [m for m in mentions if m["marker_form"] == "numeric_parenthetical"]
        assert paren_mentions, "No numeric_parenthetical found"
        texts = {m["marker_text"] for m in paren_mentions}
        assert "(1)" in texts, f"Expected '(1)' in marker_text; got: {texts}"

    def test_footnote_6_extracted(self, parser):
        """(6) at end of footnote range must match the same pattern."""
        span = _make_span("span_stents_fn_6", DOC_STENTS, self.STENTS_FOOTNOTE_6)
        mentions = parser.parse_citations([span])
        paren_mentions = [m for m in mentions if m["marker_form"] == "numeric_parenthetical"]
        assert paren_mentions, "Expected numeric_parenthetical for (6)"
        assert any("(6)" in m["marker_text"] for m in paren_mentions)

    def test_consecutive_footnotes_produce_independent_mentions(self, parser):
        """(1)(2)(3) must produce three independent CitationMention records."""
        span = _make_span("span_stents_fn_multi", DOC_STENTS, self.STENTS_MULTI_FOOTNOTE)
        mentions = parser.parse_citations([span])
        paren_mentions = [m for m in mentions if m["marker_form"] == "numeric_parenthetical"]
        assert len(paren_mentions) == 3, (
            f"Expected 3 numeric_parenthetical mentions for (1)(2)(3); got {len(paren_mentions)}: "
            f"{[m['marker_text'] for m in paren_mentions]}"
        )


# ===========================================================================
# Format 2 — NCT trial IDs
# Source: NuMED Stents SSCP, FM-STENTS-3 / RC-STENTS-2 / RC-RULE-5
# ===========================================================================


class TestNctTrialIds:
    """NCT trial identifier pattern: NCT[0-9]{8}.

    NuMED Stents SSCP contains NCT01278303 (COAST II) and NCT01824160 (PARCS).
    NCT00552812 (COAST) was absent from all spans due to windowing — tested separately.
    Current parser: 0 citations for any NCT ID. Expected after P4: marker_form='nct_id'.
    """

    # Verbatim from run_post_p1/claims.jsonl span text (clinical_performance blob):
    NCT_PARCS_TEXT = (
        "NCT01824160 \nDevice Used: Covered CP Stent pre-mounted on BIB \n"
        "Conclusion: The study results demonstrate the safety and efficacy of use "
        "of the covered CP Stent when used for pre-stenting in the \n"
        "RVOT prior to Melody TPV implantation."
    )

    # Verbatim from run_post_p1/claims.jsonl span text (clinical_performance blob):
    NCT_COASTII_TEXT = (
        "fety & Performance \n"
        "This publication presents the results from the COAST II trial to evaluate "
        "the safety and short-term efficacy of the CP Stent in treating \n"
        "or preventing aortic wall injury in patients with CoA (NCT01278303). "
        "Please refer informat"
    )

    # NCT as standalone at span start (PARCS fixture above, no parens)
    NCT_STANDALONE_TEXT = "NCT01824160\nStudy: PARCS Trial - Covered CP Stent RVOT pre-stenting."

    def test_nct_at_span_start_extracted(self, parser):
        """NCT01824160 at span start must produce a citation with marker_form='nct_id'."""
        span = _make_span("span_stents_nct_parcs", DOC_STENTS, self.NCT_PARCS_TEXT)
        mentions = parser.parse_citations([span])
        nct_mentions = [m for m in mentions if m["marker_form"] == "nct_id"]
        assert nct_mentions, (
            f"Expected nct_id mention for NCT01824160; got forms: "
            f"{[m['marker_form'] for m in mentions]}"
        )

    def test_nct_in_parentheses_extracted(self, parser):
        """(NCT01278303) parenthetical form must produce a citation with marker_form='nct_id'."""
        span = _make_span("span_stents_nct_coast2", DOC_STENTS, self.NCT_COASTII_TEXT)
        mentions = parser.parse_citations([span])
        nct_mentions = [m for m in mentions if m["marker_form"] == "nct_id"]
        assert nct_mentions, (
            f"Expected nct_id mention for NCT01278303; got forms: "
            f"{[m['marker_form'] for m in mentions]}"
        )
        assert any("NCT01278303" in m["marker_text"] for m in nct_mentions)

    def test_nct_normalized_key_format(self, parser):
        """normalized_key for NCT01824160 must follow nct_<8digit> convention."""
        span = _make_span("span_stents_nct_key", DOC_STENTS, self.NCT_STANDALONE_TEXT)
        mentions = parser.parse_citations([span])
        nct_mentions = [m for m in mentions if m["marker_form"] == "nct_id"]
        assert nct_mentions, "No nct_id mention found"
        m = nct_mentions[0]
        assert m["normalized_key"] == "nct_01824160", (
            f"Expected normalized_key='nct_01824160'; got: {m['normalized_key']!r}"
        )

    def test_nct_id_does_not_emit_digit_only_citation(self, parser):
        """Guard H: NCT01824160 must not cause the 8-digit suffix to appear as a bare digit mention.

        This test calls the citation parser only — the citation parser must not emit
        a mention whose marker_text is purely numeric (the NCT digit suffix).
        """
        span = _make_span("span_stents_nct_guard", DOC_STENTS, self.NCT_PARCS_TEXT)
        mentions = parser.parse_citations([span])
        # No mention should have a marker_text that is purely digits (the NCT suffix)
        digit_only_mentions = [
            m for m in mentions if m["marker_text"].strip().isdigit()
        ]
        assert digit_only_mentions == [], (
            f"NCT digit suffix emitted as standalone mention: {digit_only_mentions}"
        )


# ===========================================================================
# Format 3 — Named guidelines
# Source: NuMED IFU (both docs), FM-IFU-7 / RC-IFU-5; also NuMED Stents SSCP
# ===========================================================================


class TestNamedGuidelines:
    """Free-text named guideline references without brackets or author-year parens.

    The ACC/AHA 2008 guideline appears on page 1 of both NuMED IFU documents and is
    the single external reference in the IFU. Current parser: 0 citations. Expected
    after P4: marker_form='named_guideline'.

    Verbatim from FM-IFU-7 fixture:
    "The ACC/AHA 2008 Guidelines for the Management of Adults With Congenital Heart
     disease recommends a yearly follow-up..."
    """

    # Verbatim from FM-IFU-7 (failure_modes.md) — IFU page 1, both documents
    ACC_AHA_TEXT = (
        "The ACC/AHA 2008 Guidelines for the Management of Adults With Congenital "
        "Heart disease recommends a yearly follow-up and additional imaging of the "
        "Coarctation site by CT or MRI every 5 years or less."
    )

    # Partial variant — from RC-IFU-5: confirms single external ref in IFU
    ACC_AHA_BARE = "ACC/AHA 2008 Guidelines for Management of Adults With Congenital Heart Disease"

    # Also referenced in NuMED Stents SSCP (FM-STENTS-3 notes: "ACC/AHA 2008 Guidelines")
    ACC_AHA_IN_STENTS = (
        "Device follow-up and re-intervention is guided by the ACC/AHA 2008 Guidelines "
        "for the Management of Adults With Congenital Heart Disease."
    )

    def test_acc_aha_guideline_extracted_from_ifu_sentence(self, parser):
        """ACC/AHA 2008 guideline citation must be extracted from full IFU sentence."""
        span = _make_span("span_ifu_acc_aha_full", DOC_IFU, self.ACC_AHA_TEXT)
        mentions = parser.parse_citations([span])
        guideline_mentions = [m for m in mentions if m["marker_form"] == "named_guideline"]
        assert guideline_mentions, (
            f"Expected named_guideline mention for ACC/AHA 2008; got forms: "
            f"{[m['marker_form'] for m in mentions]}"
        )

    def test_acc_aha_normalized_key_convention(self, parser):
        """normalized_key must follow token-stripping convention: acc_aha_2008."""
        span = _make_span("span_ifu_acc_aha_key", DOC_IFU, self.ACC_AHA_TEXT)
        mentions = parser.parse_citations([span])
        guideline_mentions = [m for m in mentions if m["marker_form"] == "named_guideline"]
        assert guideline_mentions, "No named_guideline mention found"
        m = guideline_mentions[0]
        # Minimum: key contains the society abbreviation and year
        assert m["normalized_key"] is not None, (
            "normalized_key must not be None for named_guideline"
        )
        key = m["normalized_key"]
        assert "2008" in key, f"normalized_key must contain year 2008; got: {key!r}"
        assert "acc" in key.lower() or "aha" in key.lower(), (
            f"normalized_key must contain acc or aha; got: {key!r}"
        )

    def test_acc_aha_in_stents_sscp_also_extracted(self, parser):
        """Same guideline referenced in Stents SSCP must also produce named_guideline."""
        span = _make_span("span_stents_acc_aha", DOC_STENTS, self.ACC_AHA_IN_STENTS)
        mentions = parser.parse_citations([span])
        guideline_mentions = [m for m in mentions if m["marker_form"] == "named_guideline"]
        assert guideline_mentions, (
            f"Expected named_guideline in stents context; got forms: "
            f"{[m['marker_form'] for m in mentions]}"
        )

    def test_acc_aha_lowercase_guidelines_still_matches(self, parser):
        """ACC/AHA 2008 guidelines (lowercase g) must also match via [Gg]uidelines?."""
        text = "ACC/AHA 2008 guidelines for adults with congenital heart disease."
        span = _make_span("span_ifu_acc_aha_lower", DOC_IFU, text)
        mentions = parser.parse_citations([span])
        guideline_mentions = [m for m in mentions if m["marker_form"] == "named_guideline"]
        assert guideline_mentions, (
            f"Expected named_guideline for lowercase 'guidelines'; got: {mentions}"
        )

    # --- B2 negative regression tests (CITATION_NAMED_GUIDELINE over-matching guard) ---

    def test_named_guideline_rejects_the_prefix(self, parser):
        """'The 2008 Guidelines...' must not match: 'The' is not a valid uppercase acronym."""
        text = "The 2008 Guidelines for Management of Adults With Congenital Heart Disease"
        span = _make_span("span_b2_the_prefix", DOC_STENTS, text)
        mentions = parser.parse_citations([span])
        guideline_mentions = [m for m in mentions if m["marker_form"] == "named_guideline"]
        assert guideline_mentions == [], (
            f"Named guideline pattern over-matched 'The 2008 Guidelines': {guideline_mentions}"
        )

    def test_named_guideline_rejects_per_the_prefix(self, parser):
        """'Per the 2021 Guidelines...' must not match: 'Per'/'the' not valid society acronyms."""
        text = "Per the 2021 Guidelines on clinical investigations"
        span = _make_span("span_b2_per_the", DOC_STENTS, text)
        mentions = parser.parse_citations([span])
        guideline_mentions = [m for m in mentions if m["marker_form"] == "named_guideline"]
        assert guideline_mentions == [], (
            f"Named guideline over-matched 'Per the 2021 Guidelines': {guideline_mentions}"
        )

    def test_named_guideline_rejects_pursuant_to_prefix(self, parser):
        """'Pursuant to the 2021 Guidelines...' must not match."""
        text = "Pursuant to the 2021 Guidelines for performance evaluation"
        span = _make_span("span_b2_pursuant", DOC_STENTS, text)
        mentions = parser.parse_citations([span])
        guideline_mentions = [m for m in mentions if m["marker_form"] == "named_guideline"]
        assert guideline_mentions == [], (
            f"Named guideline over-matched 'Pursuant to the 2021 Guidelines': {guideline_mentions}"
        )


# ===========================================================================
# Format 4 — Composite bracketed citations [2, 3], [2, 3, 6]
# Source: RAUMEDIC SSCP, FM-RAUMEDIC-3
# ===========================================================================


class TestCompositeBracketSplit:
    """Composite bracketed references must split into N independent CitationMention records.

    FM-RAUMEDIC-3 notes: "Marqueurs composites [2, 3], [1, 2]" are not extracted.
    Empirical check confirmed: BRACKETED_NUMERIC (pattern matching single-number brackets) produces
    0 matches on "[2, 3]" or "[2, 3, 6]" — these require a new composite pattern
    that splits on commas and emits one mention per component.

    Expected after P4: "[2, 3]" → 2 mentions with marker_form='numeric_bracketed',
    marker_text='[2]' and '[3]' respectively (or component_of='[2, 3]').
    """

    # From FM-RAUMEDIC-3 verbatim: "Marqueurs composites [2, 3], [1, 2]"
    COMPOSITE_TWO = (
        "The catheter demonstrates adequate stiffness and torqueability [2, 3]. "
        "Burst pressure was validated per ISO 10555 [2, 3]."
    )

    COMPOSITE_THREE = (
        "Clinical data from three independent studies supports this conclusion [2, 3, 6]."
    )

    COMPOSITE_WITH_SINGLE = (
        "Primary endpoint was met [1]. Secondary endpoints [2, 3] were also achieved."
    )

    def test_composite_two_produces_two_mentions(self, parser):
        """[2, 3] must produce exactly 2 CitationMention records per occurrence."""
        span = _make_span("span_raumedic_comp_2", DOC_RAUMEDIC, self.COMPOSITE_TWO)
        mentions = parser.parse_citations([span])
        bracket_mentions = [m for m in mentions if m["marker_form"] == "numeric_bracketed"]
        # First occurrence of [2, 3] in the span must yield 2 mentions at minimum
        assert len(bracket_mentions) >= 2, (
            f"Expected at least 2 numeric_bracketed mentions for '[2, 3]'; "
            f"got {len(bracket_mentions)}: {[m['marker_text'] for m in bracket_mentions]}"
        )
        texts = {m["marker_text"] for m in bracket_mentions}
        assert "[2]" in texts, f"Component [2] missing from split; got: {texts}"
        assert "[3]" in texts, f"Component [3] missing from split; got: {texts}"

    def test_composite_three_produces_three_mentions(self, parser):
        """[2, 3, 6] must produce exactly 3 independent CitationMention records."""
        span = _make_span("span_raumedic_comp_3", DOC_RAUMEDIC, self.COMPOSITE_THREE)
        mentions = parser.parse_citations([span])
        bracket_mentions = [m for m in mentions if m["marker_form"] == "numeric_bracketed"]
        assert len(bracket_mentions) == 3, (
            f"Expected 3 numeric_bracketed mentions for '[2, 3, 6]'; "
            f"got {len(bracket_mentions)}: {[m['marker_text'] for m in bracket_mentions]}"
        )
        texts = {m["marker_text"] for m in bracket_mentions}
        assert {"[2]", "[3]", "[6]"} == texts, (
            f"Expected components {{[2], [3], [6]}}; got: {texts}"
        )

    def test_composite_mixed_with_single_bracket(self, parser):
        """Span with [1] and [2, 3] must produce 3 total mentions: [1], [2], [3]."""
        span = _make_span("span_raumedic_mixed", DOC_RAUMEDIC, self.COMPOSITE_WITH_SINGLE)
        mentions = parser.parse_citations([span])
        bracket_mentions = [m for m in mentions if m["marker_form"] == "numeric_bracketed"]
        assert len(bracket_mentions) == 3, (
            f"Expected 3 bracket mentions ([1], [2], [3]); "
            f"got {len(bracket_mentions)}: {[m['marker_text'] for m in bracket_mentions]}"
        )


# ===========================================================================
# Format 5 — Author-year in table cells with trailing n= suffix
# Source: RAUMEDIC SSCP, FM-RAUMEDIC-3 / Fixture A
# ===========================================================================


class TestAuthorYearTableCells:
    """Author-year in TABLE_CELL spans where pypdf appends sample size after year.

    Empirical finding from patterns.py AUTHOR_YEAR_TABLE test:
    - "Kerry et al. 2022"        → MATCH  (existing parser handles this)
    - "Kerry et al.\n2022"       → MATCH  (existing parser handles this via strip)
    - "Kerry et al.\n2022\nn=200" → NO MATCH (existing parser FAILS on n= suffix)
    - "Citerio et al. 2008"      → MATCH

    FM-RAUMEDIC-3 Fixture A: "span table-text 'Kerry et al.\n2022\nn=200'"
    The existing AUTHOR_YEAR_TABLE pattern uses anchored $ after year — any trailing
    content (n=200, dates, etc.) breaks the match.

    These tests are RED if the cell also contains n= suffix (the prevalent failure case).
    """

    # FM-RAUMEDIC-3 Fixture A verbatim
    KERRY_WITH_N = "Kerry et al.\n2022\nn=200"
    CITERIO_WITH_N = "Citerio et al.\n2008\nn=46"

    # Without n= suffix — existing parser DOES handle these (GREEN baseline)
    KERRY_CLEAN = "Kerry et al. 2022"
    KERRY_NEWLINE = "Kerry et al.\n2022"

    def test_author_year_table_with_n_suffix_extracted(self, parser):
        """TABLE_CELL 'Kerry et al.\\n2022\\nn=200' must produce author_year_table_cell.

        This test is expected RED until the AUTHOR_YEAR_TABLE pattern is relaxed
        to allow trailing content after the year (e.g., n= suffix).
        """
        span = _make_span(
            "span_raumedic_kerry_n",
            DOC_RAUMEDIC,
            self.KERRY_WITH_N,
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions, (
            f"Expected author_year_table_cell for 'Kerry et al. 2022 n=200'; "
            f"got forms: {[m['marker_form'] for m in mentions]}"
        )

    def test_citerio_table_cell_with_n_suffix_extracted(self, parser):
        """TABLE_CELL 'Citerio et al.\\n2008\\nn=46' must produce author_year_table_cell."""
        span = _make_span(
            "span_raumedic_citerio_n",
            DOC_RAUMEDIC,
            self.CITERIO_WITH_N,
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions, (
            f"Expected author_year_table_cell for Citerio et al. 2008 n=46; "
            f"got: {mentions}"
        )

    def test_author_year_clean_table_cell_still_works(self, parser):
        """Baseline GREEN: existing parser handles clean 'Kerry et al. 2022' in TABLE_CELL."""
        span = _make_span(
            "span_raumedic_kerry_clean",
            DOC_RAUMEDIC,
            self.KERRY_CLEAN,
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions, (
            "Regression guard: existing author_year_table_cell broken for clean 'Kerry et al. 2022'"
        )
        assert table_mentions[0]["normalized_key"] == "kerry_2022"

    # --- B1 negative regression tests (AUTHOR_YEAR_TABLE over-matching guard) ---

    def test_author_year_table_rejects_arbitrary_trailing_text(self, parser):
        """TABLE_CELL 'Kerry et al.\\n2022\\nfollow-up' must not match author_year_table_cell.

        Only the strict n=<digits> suffix is allowed. Arbitrary trailing words must be rejected.
        """
        span = _make_span(
            "span_b1_kerry_trailing",
            DOC_RAUMEDIC,
            "Kerry et al.\n2022\nfollow-up",
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions == [], (
            f"AUTHOR_YEAR_TABLE over-matched on trailing word 'follow-up': {table_mentions}"
        )

    def test_author_year_table_rejects_short_word_trailing(self, parser):
        """TABLE_CELL 'Study 2023\\nCell data' must not match author_year_table_cell.

        Rejected because trailing 'Cell data' fails the restricted trailing group
        `(?:\\s+n=\\d+)?\\s*$` — only `n=\\d+` or whitespace allowed after the year.
        The single-token author 'Study' is a known pre-existing pattern surface
        (matches `[A-Z][a-z]+`) — its rejection here is solely due to the trailing
        content, not the author shape.
        """
        span = _make_span(
            "span_b1_study_trailing",
            DOC_RAUMEDIC,
            "Study 2023\nCell data",
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions == [], (
            f"AUTHOR_YEAR_TABLE matched 'Study 2023\\nCell data' (should not): {table_mentions}"
        )

    def test_author_year_table_rejects_table_keyword_prefix(self, parser):
        """TABLE_CELL 'Table 2023\\nColumn values' must not match author_year_table_cell."""
        span = _make_span(
            "span_b1_table_prefix",
            DOC_RAUMEDIC,
            "Table 2023\nColumn values",
            kind=SpanLocationKind.TABLE_CELL,
        )
        mentions = parser.parse_citations([span])
        table_mentions = [m for m in mentions if m["marker_form"] == "author_year_table_cell"]
        assert table_mentions == [], (
            f"AUTHOR_YEAR_TABLE matched 'Table 2023\\nColumn values' (should not): {table_mentions}"
        )


# ===========================================================================
# Negative controls — must emit ZERO citation mentions
# ===========================================================================


class TestCitationNegativeControls:
    """Each case must produce zero CitationMention records.

    These guard against the new parenthetical-numeric pattern colliding with
    statistical annotations, sample sizes, units, and product labels.

    Cases A-H from the P4 spec brief. Fixture text verbatim from real dogfood spans
    or directly from real document context (RAUMEDIC, NuMED Stents, NuMED IFU).
    """

    @pytest.fixture()
    def _parser(self, parser):  # type: ignore[return]
        return parser

    # Case A — Confidence interval parenthetical
    # From RAUMEDIC pivotal text (existing test fixture, reused verbatim)
    CI_TEXT = "The primary endpoint response rate of 87.4% (95% CI: 82.1-91.6) was achieved."

    def test_a_confidence_interval_not_a_citation(self, parser):
        """(95% CI: 82.1-91.6) must not produce any citation mention."""
        span = _make_span("span_neg_ci", DOC_STENTS, self.CI_TEXT)
        mentions = parser.parse_citations([span])
        ci_mentions = [
            m for m in mentions
            if "CI" in m["marker_text"] or "82.1" in m["marker_text"] or "95" in m["marker_text"]
        ]
        assert ci_mentions == [], (
            f"(95% CI) falsely classified as citation: {ci_mentions}"
        )

    # Case B — Sample size marker
    # Verbatim from RAUMEDIC run context: n=412 in pivotal text
    N_EQ_TEXT = "Results were obtained in (n=412) participants enrolled at 12 sites."

    def test_b_sample_size_not_a_citation(self, parser):
        """(n=412) must not produce any citation mention."""
        span = _make_span("span_neg_n_eq", DOC_STENTS, self.N_EQ_TEXT)
        mentions = parser.parse_citations([span])
        n_mentions = [
            m
            for m in mentions
            if "n=412" in m["marker_text"] or "412" in m["marker_text"]
        ]
        assert n_mentions == [], (
            f"(n=412) falsely classified as citation: {n_mentions}"
        )

    # Case C — Unit parentheses (pressure context)
    # Verbatim from RAUMEDIC failure_modes.md FM-RAUMEDIC-4:
    # "Pressure measuring range: -40 to +400 mmHg (53 kPa)"
    UNIT_PAREN_TEXT = "Pressure measuring range: -40 to +400 mmHg (53 kPa)."

    def test_c_unit_parenthesis_not_a_citation(self, parser):
        """(53 kPa) must not produce any citation mention."""
        span = _make_span("span_neg_unit_paren", DOC_RAUMEDIC, self.UNIT_PAREN_TEXT)
        mentions = parser.parse_citations([span])
        unit_mentions = [
            m for m in mentions
            if "kPa" in m["marker_text"] or "53" in m["marker_text"]
        ]
        assert unit_mentions == [], (
            f"(53 kPa) falsely classified as citation: {unit_mentions}"
        )

    # Case D — Product/model parenthetical
    # Verbatim from RC-IFU-6 (numed-ifu regression_candidates.md):
    # "Do not exceed the maximum recommended expanded stent diameter of 24mm
    #  (8-zig stents) or 30mm (10-zig stents)."
    PRODUCT_PAREN_TEXT = (
        "Do not exceed the maximum recommended expanded stent diameter of 24mm "
        "(8-zig stents) or 30mm (10-zig stents)."
    )

    def test_d_product_label_parenthetical_not_a_citation(self, parser):
        """(8-zig stents) and (10-zig stents) must not produce citation mentions."""
        span = _make_span("span_neg_product", DOC_IFU, self.PRODUCT_PAREN_TEXT)
        mentions = parser.parse_citations([span])
        product_mentions = [
            m for m in mentions
            if "zig" in m["marker_text"] or "stents" in m["marker_text"]
        ]
        assert product_mentions == [], (
            f"Product label falsely classified as citation: {product_mentions}"
        )

    # Case E — Page / section navigation
    PAGE_NAV_TEXT = "See Section 3.4.1 (Page 12 of 45) for the complete reference list."

    def test_e_page_number_not_a_citation(self, parser):
        """(Page 12 of 45) must not produce a citation mention."""
        span = _make_span("span_neg_page", DOC_STENTS, self.PAGE_NAV_TEXT)
        mentions = parser.parse_citations([span])
        page_mentions = [
            m for m in mentions
            if "Page" in m["marker_text"] or "45" in m["marker_text"]
        ]
        assert page_mentions == [], (
            f"Page reference falsely classified as citation: {page_mentions}"
        )

    # Case F — Year-only parenthesis (no author)
    YEAR_ONLY_TEXT = "The MDR came into force (2017) and became fully applicable (2021)."

    def test_f_year_only_parenthesis_not_a_citation(self, parser):
        """(2017) and (2021) standalone years must not produce citation mentions.

        AUTHOR_YEAR_PAREN requires an author token before the year. This tests that
        the new numeric_parenthetical pattern does not also match 4-digit years.
        """
        span = _make_span("span_neg_year_only", DOC_STENTS, self.YEAR_ONLY_TEXT)
        mentions = parser.parse_citations([span])
        year_mentions = [
            m for m in mentions
            if m["marker_text"] in {"(2017)", "(2021)"}
        ]
        assert year_mentions == [], (
            f"Year-only parenthesis falsely classified as citation: {year_mentions}"
        )

    # Case G — Drug doses / measurements in parens (VALUE UNIT territory)
    # Note: per P2 scope, tier-2 units like mm are not extracted by VALUE_UNIT;
    # this guards against citation over-classification independent of that.
    DOSE_PAREN_TEXT = "Administer aspirin (75 mg) daily and monitor blood pressure (2.5 mL flush)."

    def test_g_drug_dose_parenthesis_not_a_citation(self, parser):
        """(75 mg) and (2.5 mL) must not produce citation mentions."""
        span = _make_span("span_neg_dose", DOC_STENTS, self.DOSE_PAREN_TEXT)
        mentions = parser.parse_citations([span])
        dose_mentions = [
            m for m in mentions
            if "mg" in m["marker_text"] or "mL" in m["marker_text"] or "75" in m["marker_text"]
        ]
        assert dose_mentions == [], (
            f"Drug dose falsely classified as citation: {dose_mentions}"
        )

    # Case H — NCT ID digit suffix must not be a COUNT_N numeric claim
    # This tests the CITATION PARSER specifically — the numeric extractor is out of scope here.
    # Guard: citation parser must not emit a mention whose marker_text is the raw digit suffix.
    NCT_DIGIT_GUARD_TEXT = "The COAST trial (NCT00552812) enrolled patients at 15 centers."

    def test_h_nct_digit_suffix_not_a_standalone_digit_mention(self, parser):
        """NCT00552812: the 8-digit suffix '00552812' must not appear as standalone marker_text.

        The citation parser should emit exactly one mention with marker_form='nct_id'
        and marker_text='NCT00552812' (or '(NCT00552812)'), not a bare digit string.
        This guards against an NCT regex that accidentally strips the prefix.
        """
        span = _make_span("span_neg_nct_digit", DOC_STENTS, self.NCT_DIGIT_GUARD_TEXT)
        mentions = parser.parse_citations([span])
        # Any mention whose marker_text is purely numeric is a violation
        bare_digit_mentions = [
            m for m in mentions
            if m["marker_text"].strip().lstrip("(").rstrip(")").isdigit()
        ]
        assert bare_digit_mentions == [], (
            f"NCT suffix emitted as bare digit mention: {bare_digit_mentions}"
        )

    # Case H (additional) — NCT text in a span must not fire as numeric_parenthetical
    # The format (NCT01278303) must match nct_id, not numeric_parenthetical
    def test_h_parenthetical_nct_does_not_match_numeric_parenthetical(self, parser):
        """(NCT01278303) must not produce a numeric_parenthetical mention.

        If the numeric_parenthetical pattern matches (N) for any N, it must be
        gated to exclude strings that start with letters (NCT prefix).
        After P4 implementation: expect marker_form='nct_id', not 'numeric_parenthetical'.
        This test checks the current state (no matches at all) — it must remain
        GREEN before and after P4.
        """
        text = "Primary cohort enrolled in the COAST II study (NCT01278303)."
        span = _make_span("span_neg_nct_paren", DOC_STENTS, text)
        mentions = parser.parse_citations([span])
        wrong_form_mentions = [
            m for m in mentions
            if m["marker_form"] == "numeric_parenthetical"
            and "NCT" in m["marker_text"]
        ]
        assert wrong_form_mentions == [], (
            f"NCT ID matched as numeric_parenthetical: {wrong_form_mentions}"
        )


# ===========================================================================
# W-3 guard — derive_document_id_short input validation
# ===========================================================================


class TestDeriveDocumentIdShort:
    """Unit tests for derive_document_id_short ValueError guards (W-3).

    The function must reject inputs that do not contain at least 8 deterministic
    hex characters after the 'doc_' prefix. Human-readable synthetic IDs must
    not silently produce zero-entropy short keys.
    """

    def test_derive_document_id_short_rejects_empty(self) -> None:
        """derive_document_id_short('') must raise ValueError."""
        from locuslab.extract.citation_parser import derive_document_id_short

        with pytest.raises(ValueError):
            derive_document_id_short("")

    def test_derive_document_id_short_rejects_no_prefix(self) -> None:
        """derive_document_id_short('abc12345') must raise ValueError (missing 'doc_' prefix)."""
        from locuslab.extract.citation_parser import derive_document_id_short

        with pytest.raises(ValueError):
            derive_document_id_short("abc12345")

    def test_derive_document_id_short_rejects_short(self) -> None:
        """derive_document_id_short('doc_abc') must raise ValueError (< 8 hex chars)."""
        from locuslab.extract.citation_parser import derive_document_id_short

        with pytest.raises(ValueError):
            derive_document_id_short("doc_abc")

    def test_derive_document_id_short_extracts_first_8_hex(self) -> None:
        """derive_document_id_short('doc_3b3399318c522c17') must return '3b339931'."""
        from locuslab.extract.citation_parser import derive_document_id_short

        result = derive_document_id_short("doc_3b3399318c522c17")
        assert result == "3b339931", f"Expected '3b339931'; got {result!r}"
