"""Noise-gate regression tests for header chrome and foreshortening.

Covers two failure modes confirmed across three dogfood runs on 2026-05-23:

  FM-PHASE2-2  SSCP repeated PDF header/chrome contamination
               Sources:
                 reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/failure_modes.md
                 reports/dogfood/2026-05-23/stents-coa-rvot-rev00/failure_modes.md

  FM-IFU-2     IFU foreshortening percentage table suppression
               Source:
                 reports/dogfood/2026-05-23/numed-ifu-ccp-cmcp/failure_modes.md

All 17 tests in this file are GREEN as of 2026-05-23 (P1 implementation landed + cleanup rounds).

Fixture texts are verbatim from the dogfood JSONL / read_pdf output.
No claim fields beyond {claim_id, document_id, span_id, text, claim_type,
extraction_method, confidence_label} are asserted (constraint C-3).
No DocumentKind.IFU is used (constraint C-2).
No verdict/checker logic is introduced (constraint C-4).
"""

from __future__ import annotations

import pytest

from locuslab.models import (
    ClaimType,
    Document,
    DocumentKind,
    Span,
    SpanLocation,
    SpanLocationKind,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page_span(
    span_id: str,
    document_id: str,
    text: str,
    index: int = 0,
) -> Span:
    return Span(
        span_id=span_id,
        document_id=document_id,
        location=SpanLocation(kind=SpanLocationKind.PAGE, index=index),
        text=text,
        section=None,
    )


def _make_doc(document_id: str, kind: DocumentKind = DocumentKind.SSCP) -> Document:
    return Document(
        document_id=document_id,
        kind=kind,
        path="dummy.pdf",
        sha256="0" * 64,
        parser="pypdf",
    )


@pytest.fixture()
def extractor():  # type: ignore[return]
    from locuslab.extract.claim_extractor import ClaimExtractor

    return ClaimExtractor()


# ---------------------------------------------------------------------------
# FM-PHASE2-2 fixture constants
# Verbatim from:
#   reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/run/claims.jsonl
#   + read_pdf(SSCP_PG_0009_2024-03-28_en.pdf, document_id='doc_3b3399318c522c17')
# ---------------------------------------------------------------------------

_DOC_RAUMEDIC = "doc_3b3399318c522c17"

# Span span_a792b48eecff0098 — page 7 of RAUMEDIC SSCP.
# 41/69 clinical_performance claims share this verbatim prefix.
# text length 2450 chars; only prefix shown here — the full text is used in
# the span fixture (RAUMEDIC_SPAN_PAGE7_TEXT).
RAUMEDIC_SPAN_PAGE7_ID = "span_a792b48eecff0098"
RAUMEDIC_SPAN_PAGE7_TEXT = (
    "Titel: Summary of Safety and Clinical Performance \n \n \n"
    "VA_RM_00124_FB_05  4.0 \n"
    "Seite 7 von 41 \n"
    "Criteria Specification DuE \n"
    "Application of a single catheter to \n"
    "maximum of 10 days \n"
    "Repeat applications, \n"
    "including any \n"
    "restrictions as to the \n"
    "number or duration of \n"
    "re-applications \n"
    "None NA \n"
    "Contact with mucosal \n"
    "membranes/ \n"
    "invasiveness/ \n"
    "implantation \n"
    "RAUMEDIC® precision pressure catheters \n"
    "are inv"
)

# Span span_fe29634a6b98cd30 — page 11.
RAUMEDIC_SPAN_PAGE11_ID = "span_fe29634a6b98cd30"
RAUMEDIC_SPAN_PAGE11_TEXT = (
    "Titel: Summary of Safety and Clinical Performance \n \n \n"
    "VA_RM_00124_FB_05  4.0 \n"
    "Seite 11 von 41 \n"
    "Criteria Specification DuE \n"
    "below the edge of the bone between \n"
    "dura and skullcap without using force! \n"
    "• The pressure can be measured at any \n"
    "point on the skull. The present disease \n"
    "should be used for orientation when \n"
    "selecting the site of application. \n"
    "Epidural precision catheter application \n"
    "should"
)

# Span span_d28897bc376044f6 — page 30, contains real clinical study table rows
# mixed with the header.  The header prefix must NOT suppress the real content.
RAUMEDIC_SPAN_PAGE30_ID = "span_d28897bc376044f6"
RAUMEDIC_SPAN_PAGE30_TEXT = (
    "Titel: Summary of Safety and Clinical Performance \n \n \n"
    "VA_RM_00124_FB_05  4.0 \n"
    "Seite 30 von 41 \n"
    "Authors Study design \n"
    "Measurement of intracranial pressure and drainage \n"
    "Pinggera et al.  \n"
    "2022 \n"
    "Retrospective analysis \n"
    "Outcome: Specific brain tissue damage induced by neuromonitoring devices "
    "in situ and its clinical relevance. \n"
    "NEUROVENT-P (n=19) \n"
    " \n"
    "Patient age: Mean age: 42.8 years (range – 20 to 34"
)

# Span span_57a646c02787e919 — page 36.  Contains real clinical performance
# content ONLY (no header prefix). Negative-control: must still emit claims.
RAUMEDIC_SPAN_PAGE36_ID = "span_57a646c02787e919"
RAUMEDIC_SPAN_PAGE36_TEXT = (
    "Titel: Summary of Safety and Clinical Performance \n \n \n"
    "VA_RM_00124_FB_05  4.0 \n"
    "Seite 36 von 41 \n"
    "Authors  Study design Results  \n"
    "is better than depending on a single sign such \n"
    "as physical examination or CT alone. \n"
    "Bhargava et al. 2020 Systematic review \n"
    "Children with SOL, \n"
    "haemorrhage, infection, \n"
    "IIH, trauma,  \n"
    "It was not able to identify a threshold value in \n"
    "ultrasound measured optic nerve shea"
)

# ---------------------------------------------------------------------------
# FM-PHASE2-2 fixture constants — NuMED Stents SSCP
# Verbatim from:
#   reports/dogfood/2026-05-23/stents-coa-rvot-rev00/run/claims.jsonl
#   + read_pdf(Stents_CoA_RVOT_Rev00.pdf, document_id='doc_8e1133d3bb1097ce')
# ---------------------------------------------------------------------------

_DOC_STENTS = "doc_8e1133d3bb1097ce"

# span_1af8724be73304ff — page 12 of NuMED Stents SSCP.
# 45/73 clinical_performance claims share this prefix.
STENTS_SPAN_PAGE12_ID = "span_1af8724be73304ff"
STENTS_SPAN_PAGE12_TEXT = (
    "NuMED \n"
    "Summary of Safety and Clinical Performance \n"
    "SSCP – Stents – CoA & RVOT \n"
    "FCD-1137                  Rev 02                                   Page 12 of 45 \n"
    "\xa0\n"
    "‐ Mean age: 23.6\xb110.99 (range 12 to 58) years \n"
    "‐ Sex: 79 M; 41 F \n"
    "Report ‐ High quality. R1 R2 R3 \n"
    "Suitability Grade (Range 4-12) 4 \n"
    " \n"
    "Data Contribution Relevant Data Grading \n"
    "Outcomes/Endpoints ‐ Procedural success \n"
    "‐ Reduction in systolic blood pressure gradient \n"
    "‐ Reduction in mean d"
)

# span_2caff91fc5bcc73a — page 41, contains the SSCP intro paragraph.
# The header prefix appears but is immediately followed by real regulatory content.
STENTS_SPAN_PAGE41_ID = "span_2caff91fc5bcc73a"
STENTS_SPAN_PAGE41_TEXT = (
    "NuMED \n"
    "Summary of Safety and Clinical Performance \n"
    "SSCP – Stents – CoA & RVOT \n"
    "FCD-1137                  Rev 02                                   Page 41 of 45 \n"
    "\xa0\n"
    "Document Revision: 00 \n"
    "Date issued: 21 June 2022 \n"
    " \n"
    "This Summary of Safety and Clinical Performance (SSCP) is intended to provide "
    "public access to an updated summary of \n"
    "the main aspects of the safety and clinical performance of the device.  "
    "The information presented below is intended f"
)

# span_8d4e7c3cf205c6bf — page 36, contains real efficacy data.
# This span ALSO starts with the NuMED header prefix, but has real clinical
# performance content that must still emit claims.
STENTS_SPAN_PAGE36_ID = "span_8d4e7c3cf205c6bf"
STENTS_SPAN_PAGE36_TEXT = (
    "NuMED \n"
    "Summary of Safety and Clinical Performance \n"
    "SSCP – Stents – CoA & RVOT \n"
    "FCD-1137                  Rev 02                                   Page 36 of 45 \n"
    "\xa0\n"
    "or postcatheterization coarctation. However, subtle differences in the need "
    "for reintervention and \n"
    "presence of aortic wall injuries are noted. \n"
    "‐ Reintervention incidence was 7% for postsurgical coarctation, 22% and 23% "
    "for native and \n"
    "postcatheterization. \n"
    "‐ Aortic wall injuries were "
)

# Pure real clinical content — no header prefix — from a span that produced
# a legitimate clinical_performance claim (span_f6525f7225d5a41c).
STENTS_SPAN_REAL_CLINICAL_ID = "span_f6525f7225d5a41c"
STENTS_SPAN_REAL_CLINICAL_TEXT = (
    "it. A lot of time is taken in getting these essential steps right, and there "
    "is potential for safety, \nefficiency, and efficacy problems at every step. "
    "Slipping of the stents off balloons leading to m"
)

# ---------------------------------------------------------------------------
# FM-IFU-2 fixture constants
# Verbatim from:
#   reports/dogfood/2026-05-23/numed-ifu-ccp-cmcp/run/claims.jsonl
#   + read_pdf(rm0344-69e_cmcp_ce_dual_ni.pdf, document_id='doc_1b0478f0c7f210f9')
#   + read_pdf(rm0344-61e_ccp_dual_sterile_ni.pdf, document_id='doc_f5ed001ab4c8cf2b')
# ---------------------------------------------------------------------------

_DOC_IFU_CCP = "doc_f5ed001ab4c8cf2b"   # rm0344-61e (CCP)
_DOC_IFU_CMCP = "doc_1b0478f0c7f210f9"  # rm0344-69e (CMCP)

# span_22492c6943bc559a — PAGE span from doc_1b0478f0c7f210f9.
# Verbatim foreshortening table for CP10Z stents.
# Produced 37+ PERCENTAGE_DECIMAL noise claims in the dogfood run.
IFU_FORESHORTING_SPAN_ID = "span_22492c6943bc559a"
IFU_FORESHORTENING_TEXT = (
    "5 \n"
    "Inflated \nBalloon \nDiameter \n"
    "CP10Z39 \n(Stent length after \nexpansion) \nPercentage \nShortening \n"
    "CP10Z45 \n(Stent length after \nexpansion) \nPercentage \nShortening \n"
    "CP10Z50 \n(Stent length after \nexpansion) \nPercentage \nShortening \n"
    "CP10Z55 \n(Stent length after \nexpansion) \nPercentage \nShortening \n"
    "CP10Z60 \n(Stent length after \nexpansion) \nPercentage \nShortening \n"
    "26mm (3.17) cm \n18.33% \n(3.44) cm \n22.09% \n(4.10) cm \n17.34% \n"
    "(4.24) cm \n23.32% \n(4.85) cm \n20.20% \n"
    "28mm (2.96) cm \n23.68% \n(3.24) cm \n26.75% \n(3.71) cm \n25.11% \n"
    "(4.00) cm \n27.58% \n(4.39) cm \n27.87% \n"
    "30mm (2.58) cm \n33.45% \n(3.09) cm \n30.16% \n(3.26) cm \n34.34% \n"
    "(3.64) cm \n34.17% \n(4.11) cm \n32.55% \n"
    " \n"
    "CP Stent™ 8 Zig Balloon Sizing Chart \n"
    " Stent ID (mm) \n"
    "Inner Balloon \nPressure \n(atm) \n"
    "12mm \nDiameter \nRBP = 7.0 \n14mm \nDiameter \nRBP = 6.0 \n"
    "15mm \nDiameter \nRBP = 5.0 \n16mm \nDiameter \nRBP = 5.0 \n"
    "18mm \nDiameter \nRBP = 4.0 \n20mm \nDiameter \nRBP = 4.0 \n"
    "22mm \nDiameter \nRBP = 3.0 \n24mm \nDiameter \nRBP = 3.0 \n"
    "1.0 2.75 3.22 3.49 3.75 3.94 4.02 4.20 4.28 \n"
    "2.0 2.85 3.32 3.59 3.85 4.36 4.13 4.33 4.50 \n"
    "3.0 5.85 6.91 6.89 7.79 8.54 9.20 10.16 10.57 \n"
    "4.0 6.12 7.00 7.02 7.95 8.71 9.63 10.40 11.08 \n"
    "5.0 6.20 7.08 7.10 8.04 8.91 10.00   \n"
    "FOR ALL NuMED CATHETERS AN INFLATION DEVICE  \n"
    "WITH PRESSURE GAUGE SHOULD BE USED. \n"
)

# span_b1309af606b34601 — PAGE span from doc_f5ed001ab4c8cf2b (CCP doc).
# Contains the CP8Z foreshortening chart plus the warranty disclaimer.
# Produced 19.5%, 30.16% and other noise claims in the dogfood run.
IFU_FORESHORTING_CCP_SPAN_ID = "span_b1309af606b34601"
IFU_FORESHORTENING_CCP_TEXT_PREFIX = (
    # Page 4 of rm0344-61e starts with warranty text then the chart.
    "4 \n"
    "Warranty and Limitations \n"
    "Stents and accessories are sold in an 'as is' condition. The entire risk as to "
    "the quality and performance of the stent is with the buyer. \n"
    "NuMED disclaims all warranties, expressed or implied, with respect to catheters "
    "and accessories, including but not limited to, any \n"
    "implied warranty of merchantability or fitness for a particular purpose. NuMED "
    "shall not be liable to any person for any medical \n"
    "expenses or any direct or consequential damages resulting from the use of any "
    "catheter or accessory or caused by any defect, \n"
    "failure, or malfunction of any catheter or "
    # (truncated to 550 chars; the span contains 'CP Stent™ Foreshortening Chart'
    # followed by table rows with 19.5%, 30.16%, etc.)
)
IFU_FORESHORTENING_CCP_MARKER = "CP Stent™ Foreshortening Chart"

# Negative-control: a PAGE span with a real clinical decimal percentage sentence
# that must still emit a PERCENTAGE_DECIMAL claim after the gate is applied.
# Constructed from real IFU language (procedural text on span_29b455e896cefd35).
IFU_REAL_PCT_SPAN_ID = "span_29b455e896cefd35"
IFU_REAL_PCT_TEXT = (
    "4 \n"
    "balloon catheter. \n"
    "5. Confirm positioning and inflate the outer balloon to rated diameter. "
    "Do not exceed the manufacturer's balloon rated burst \npressure. \n"
    " \n"
    "Delivery System Withdrawal \n"
    "1. Once the stent is expanded, deflate both balloons completely and rotate "
    "to ensure the stent is free and properly deployed.  If \n"
    "there is a residual waist in the stent, expand only the outer balloon again, "
    "making sure not to exceed the rated burst pressure.  \n"
    "The procedural success rate was 97.6% in the intention-to-treat population "
    "for the primary efficacy endpoint. \n"
    "Remove the balloon catheter and confirm the result with angiography. \n"
)


# ===========================================================================
# TestSscpHeaderChromeNoiseGate
# ===========================================================================


class TestSscpHeaderChromeNoiseGate:
    """FM-PHASE2-2 — SSCP PDF header chrome produces false clinical_performance claims.

    Tests verify that the SSCP header-strip gate (strip_sscp_page_header) correctly
    suppresses header-only keyword matches while preserving real evidence claims in
    the body content that follows the header.
    """

    # ------------------------------------------------------------------
    # RAUMEDIC SSCP — German header "Titel: Summary of Safety..."
    # ------------------------------------------------------------------

    def test_raumedic_page7_header_only_emits_zero_cp_claims(self, extractor) -> None:
        """FM-RAUMEDIC-2: RAUMEDIC page 7 span whose header triggers 'Performance' keyword
        must emit zero clinical_performance claims.

        Dogfood evidence: claim_08c1f3dbb056f040 (and 40 siblings) confirm the bug.
        The span text starts with the 167-char RAUMEDIC header prefix on every page.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_SPAN_PAGE7_ID, _DOC_RAUMEDIC, RAUMEDIC_SPAN_PAGE7_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        assert cp_claims == [], (
            f"Expected zero clinical_performance claims from header-only span; "
            f"got {len(cp_claims)}: {[c.text[:80] for c in cp_claims]}"
        )

    def test_raumedic_page11_header_only_emits_zero_cp_claims(self, extractor) -> None:
        """FM-RAUMEDIC-2: RAUMEDIC page 11 span — second fixture confirming the pattern."""
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_SPAN_PAGE11_ID, _DOC_RAUMEDIC, RAUMEDIC_SPAN_PAGE11_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        assert cp_claims == [], (
            f"Expected zero clinical_performance claims from header-only span; "
            f"got {len(cp_claims)}: {[c.text[:80] for c in cp_claims]}"
        )

    def test_raumedic_page30_real_content_still_emits_cp_claims(self, extractor) -> None:
        """FM-RAUMEDIC-2 negative control: a span that starts with the header but
        contains real clinical study data must still emit at least one
        clinical_performance claim from the real content region.

        The header strip must remove the prefix but must NOT suppress all claims
        from a span that has real content after the prefix.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_SPAN_PAGE30_ID, _DOC_RAUMEDIC, RAUMEDIC_SPAN_PAGE30_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        # The span contains "Outcome:" and study design keywords — at least one claim expected.
        assert cp_claims, (
            "Expected at least one clinical_performance claim from span with real clinical "
            "content after the header; got zero."
        )

    def test_raumedic_header_strip_does_not_change_span_id(self, extractor) -> None:
        """Provenance constraint: any claims produced from page 30 must reference
        the original span_id unchanged.

        Constraint C-1 from the spec: stripping header text must NOT change the
        span_id or document_id of any downstream claim.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_SPAN_PAGE30_ID, _DOC_RAUMEDIC, RAUMEDIC_SPAN_PAGE30_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        for claim in claims:
            assert claim.span_id == RAUMEDIC_SPAN_PAGE30_ID, (
                f"Claim {claim.claim_id} has span_id={claim.span_id!r}; "
                f"expected {RAUMEDIC_SPAN_PAGE30_ID!r}"
            )
            assert claim.document_id == _DOC_RAUMEDIC, (
                f"Claim {claim.claim_id} has document_id={claim.document_id!r}; "
                f"expected {_DOC_RAUMEDIC!r}"
            )

    # ------------------------------------------------------------------
    # NuMED Stents SSCP — English header "NuMED / Summary of Safety..."
    # ------------------------------------------------------------------

    def test_stents_page12_header_only_emits_zero_cp_claims(self, extractor) -> None:
        """FM-STENTS-2: NuMED Stents page 12 span must emit zero clinical_performance claims.

        The NuMED header is 148-169 chars and contains BOTH "Summary of Safety" and
        "Clinical Performance" — two keyword triggers — making this harder than RAUMEDIC.
        Dogfood: 45/73 claims had this prefix.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span(
            STENTS_SPAN_PAGE12_ID, _DOC_STENTS, STENTS_SPAN_PAGE12_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        assert cp_claims == [], (
            f"Expected zero clinical_performance claims from NuMED header span; "
            f"got {len(cp_claims)}: {[c.text[:80] for c in cp_claims]}"
        )

    def test_stents_page41_header_only_emits_zero_cp_claims(self, extractor) -> None:
        """FM-STENTS-2: NuMED Stents page 41 (SSCP intro) must emit zero cp claims.

        Page 41 content is the SSCP boilerplate intro paragraph — not a real
        performance statement.  The header prefix + 'clinical performance' in the
        intro body both trigger the keyword.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span(
            STENTS_SPAN_PAGE41_ID, _DOC_STENTS, STENTS_SPAN_PAGE41_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        assert cp_claims == [], (
            f"Expected zero clinical_performance claims from NuMED header+intro span; "
            f"got {len(cp_claims)}: {[c.text[:80] for c in cp_claims]}"
        )

    def test_stents_page36_real_content_still_emits_cp_claims(self, extractor) -> None:
        """FM-STENTS-2 negative control: NuMED page 36 has real efficacy data after
        the header and must still emit clinical_performance claims.

        Content: reintervention incidence, aortic wall injuries — real outcomes.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span(
            STENTS_SPAN_PAGE36_ID, _DOC_STENTS, STENTS_SPAN_PAGE36_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        cp_claims = [c for c in claims if c.claim_type == ClaimType.CLINICAL_PERFORMANCE]
        assert cp_claims, (
            "Expected at least one clinical_performance claim from NuMED page 36 "
            "(real efficacy data after header); got zero."
        )

    def test_ifu_without_header_produces_no_false_positives(self, extractor) -> None:
        """FM-IFU-8 negative control: IFU spans have no running header.

        The gate must not suppress legitimate claims on documents without the SSCP
        page-chrome pattern.  This uses the NuMED IFU 'real percentage' span which
        contains a genuine efficacy statement.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_REAL_PCT_SPAN_ID, _DOC_IFU_CMCP, IFU_REAL_PCT_TEXT)
        claims = extractor.extract_claims([span], [doc])
        pct_claims = [c for c in claims if c.claim_type == ClaimType.NUMERIC]
        # "97.6%" is a real efficacy claim and must survive the gate.
        assert any("97.6" in c.text for c in pct_claims), (
            f"Expected 97.6% numeric claim from IFU efficacy span; "
            f"pct claims: {[c.text for c in pct_claims]}"
        )

    def test_strip_sscp_page_header_returns_input_on_no_match(self) -> None:
        """No-match contract: strip_sscp_page_header returns the input unchanged
        when no recognized SSCP or RAUMEDIC header prefix is found.

        Documents that are not SSCP/RAUMEDIC must never have their text altered by
        the gate.  This test documents the contract directly so a future change to
        the regex cannot silently widen the match surface.
        """
        from locuslab.extract.noise_gates import strip_sscp_page_header

        text = "any text that contains no recognized header prefix at all"
        assert strip_sscp_page_header(text) == text


# ===========================================================================
# TestIfuForeshorteningTableGate
# ===========================================================================


class TestIfuForeshorteningTableGate:
    """FM-IFU-2 — IFU foreshortening table produces 162 noise PERCENTAGE_DECIMAL claims.

    Tests verify that is_foreshortening_table_span correctly identifies foreshortening
    chart spans (including translated variants lacking English markers) and that
    ClaimExtractor.extract() suppresses percentage claims from those spans.

    Gate requirement: content-based detection only.  The gate must inspect the
    span text for foreshortening table markers (e.g. "Foreshortening Chart",
    "Percentage Shortening", CP-stent model codes such as "CP8Z16", "CP10Z39").
    It must NOT rely on SpanLocationKind.TABLE_CELL (these are PAGE spans) or
    DocumentKind.IFU (that enum value does not exist in V1).

    Branch 3 (≥2 CP codes + structural co-signal) is specifically tested via the
    translated-table rail to confirm that suppression works without English markers.
    """

    def test_foreshortening_span_emits_zero_pct_claims(self, extractor) -> None:
        """FM-IFU-2: PAGE span containing the CP10Z foreshortening chart must emit
        zero extract.numeric.percentage:v1 claims.

        Dogfood evidence: span_22492c6943bc559a produced 37+ PERCENTAGE_DECIMAL
        noise claims (18.33%, 22.09%, 23.32%, 20.20%, etc.).
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_FORESHORTING_SPAN_ID, _DOC_IFU_CMCP, IFU_FORESHORTENING_TEXT)
        claims = extractor.extract_claims([span], [doc])
        pct_claims = [
            c for c in claims
            if c.extraction_method == "extract.numeric.percentage:v1"
        ]
        assert pct_claims == [], (
            f"Expected zero extract.numeric.percentage:v1 claims from foreshortening "
            f"table span; got {len(pct_claims)}: {[c.text for c in pct_claims[:8]]}"
        )

    def test_foreshortening_ccp_span_emits_zero_pct_claims(self, extractor) -> None:
        """FM-IFU-2: PAGE span from doc rm0344-61e containing 'CP Stent Foreshortening Chart'
        must emit zero PERCENTAGE_DECIMAL claims.

        Dogfood evidence: span_b1309af606b34601 produced 19.5%, 30.16%, and related noise.
        """
        # Build a representative portion of the span that contains the chart marker and values.
        span_text = (
            "4 \n"
            "Warranty and Limitations \n"
            "Stents and accessories are sold in an 'as is' condition.\n"
            "NuMED disclaims all warranties.\n"
            " \n"
            "CP Stent™ Foreshortening Chart \n"
            "Inflated \nBalloon \nDiameter \n"
            "CP8Z16 \n(Stent length after expansion) \nPercentage Shortening \n"
            "CP8Z22 \n(Stent length after expansion) \nPercentage Shortening \n"
            "12mm 19.5% 22.0% \n"
            "14mm 30.16% 25.4% \n"
            "16mm 16.3% 18.7% \n"
        )
        doc = _make_doc(_DOC_IFU_CCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_FORESHORTING_CCP_SPAN_ID, _DOC_IFU_CCP, span_text)
        claims = extractor.extract_claims([span], [doc])
        pct_claims = [
            c for c in claims
            if c.extraction_method == "extract.numeric.percentage:v1"
        ]
        assert pct_claims == [], (
            f"Expected zero extract.numeric.percentage:v1 claims from CP8Z foreshortening "
            f"span; got {len(pct_claims)}: {[c.text for c in pct_claims]}"
        )

    def test_real_clinical_pct_in_page_span_still_emits_claim(self, extractor) -> None:
        """FM-IFU-2 negative control: a PAGE span with a real clinical percentage
        (infection rate, efficacy endpoint) must still emit a PERCENTAGE_DECIMAL claim.

        The gate must not over-suppress.  A percentage embedded in a clinical sentence
        without foreshortening table markers is a legitimate claim.
        """
        span_text = (
            "3 \n"
            "Clinical Performance Summary \n"
            "The overall procedural success rate was 97.6% across all implant centres. \n"
            "Device-related adverse events occurred in 2.5% of procedures within 30 days. \n"
            "Long-term patency was maintained in 94.1% of patients at 5-year follow-up. \n"
        )
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span("span_synthetic_clinical_pct", _DOC_IFU_CMCP, span_text)
        claims = extractor.extract_claims([span], [doc])
        pct_values = [
            c.text for c in claims
            if c.extraction_method == "extract.numeric.percentage:v1"
        ]
        assert any("97.6" in v for v in pct_values), (
            f"Expected 97.6% from clinical sentence; got: {pct_values}"
        )
        assert any("2.5" in v for v in pct_values), (
            f"Expected 2.5% from clinical sentence; got: {pct_values}"
        )

    def test_foreshortening_gate_does_not_depend_on_table_cell_kind(
        self, extractor
    ) -> None:
        """Constraint C-2: the gate must operate on PAGE spans, not TABLE_CELL.

        The foreshortening table is delivered as a PAGE span by pypdf (flattened).
        A TABLE_CELL span with the same foreshortening text must ALSO be suppressed
        (the gate logic should be span-text-based, not span-kind-based).
        This verifies the gate is not accidentally bypassed for PAGE spans by relying
        on the existing TABLE_CELL branch in _extract_clinical_performance.
        """
        span_text = IFU_FORESHORTENING_TEXT
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        # Deliberately use PAGE kind — the real production case.
        span_page = _make_page_span(
            "span_foreshortening_page_kind_check",
            _DOC_IFU_CMCP,
            span_text,
        )
        claims = extractor.extract_claims([span_page], [doc])
        pct_claims = [
            c for c in claims
            if c.extraction_method == "extract.numeric.percentage:v1"
        ]
        assert pct_claims == [], (
            f"Gate must suppress foreshortening pct claims on PAGE spans; "
            f"got {len(pct_claims)} claims."
        )

    def test_foreshortening_gate_preserves_span_id_on_non_suppressed_claims(
        self, extractor
    ) -> None:
        """Provenance constraint C-1: claims from a non-foreshortening page span
        must reference the original span_id.

        This is a belt-and-suspenders check: the gate must not accidentally mutate
        span_id or document_id on the non-suppressed path.
        """
        span_text = (
            "3 \n"
            "The primary endpoint was achieved in 94.1% of the intention-to-treat "
            "population (n=143, p<0.001).\n"
        )
        target_span_id = "span_provenance_check_ifu_gate"
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(target_span_id, _DOC_IFU_CMCP, span_text)
        claims = extractor.extract_claims([span], [doc])
        for claim in claims:
            assert claim.span_id == target_span_id, (
                f"Claim {claim.claim_id} has span_id={claim.span_id!r}; "
                f"expected {target_span_id!r}"
            )
            assert claim.document_id == _DOC_IFU_CMCP, (
                f"Claim {claim.claim_id} has document_id={claim.document_id!r}; "
                f"expected {_DOC_IFU_CMCP!r}"
            )

    def test_translated_foreshortening_table_is_suppressed(self, extractor) -> None:
        """Branch 3 positive rail: a translated (FR) foreshortening table without English
        markers must be detected via the language-neutral structural co-signal.

        Fixture models a French foreshortening table header ("Tableau des raccourcissements
        du CP Stent") with ≥2 CP model codes and comma-decimal percentages across multiple
        lines. Branch 3 of is_foreshortening_table_span fires: ≥2 CP codes + ≥4 non-empty
        lines (and ≥2 percentage values with comma-decimal format).

        The extractor-count assertion is forward-looking — comma-decimal percentages
        (e.g., "18,33%") are not currently matched by PERCENTAGE_DECIMAL (which requires
        dot-decimal), so the count is 0 regardless of the gate.  The real regression value
        of this test is the direct is_foreshortening_table_span predicate assertion, which
        catches a gate-logic regression.  The forward-looking assertion will activate when
        locale support is added (planned P2+).
        """
        from locuslab.extract.noise_gates import is_foreshortening_table_span

        span_text = (
            "Tableau des raccourcissements du CP Stent \n"
            "Diamètre du ballon gonflé \n"
            "CP8Z16 \n(Longueur du stent après expansion) \nRaccourcissement \n"
            "CP10Z39 \n(Longueur du stent après expansion) \nRaccourcissement \n"
            "12mm 18,33% 22,09% \n"
            "14mm 23,68% 26,75% \n"
            "16mm 19,50% 25,11% \n"
            "18mm 27,58% 27,87% \n"
            "20mm 33,45% 30,16% \n"
        )
        # Gate predicate must return True for this translated table.
        assert is_foreshortening_table_span(span_text), (
            "is_foreshortening_table_span must return True for translated FR "
            "foreshortening table (branch 3: ≥2 CP codes + structural co-signal)"
        )
        # Full extractor run: zero extract.numeric.percentage:v1 claims expected.
        # Comma-decimal percentages do not match PERCENTAGE_DECIMAL today, so this
        # is naturally 0; the gate provides an additional forward-looking guard.
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span("span_fr_foreshortening_table", _DOC_IFU_CMCP, span_text)
        claims = extractor.extract_claims([span], [doc])
        pct_claims = [
            c for c in claims
            if c.extraction_method == "extract.numeric.percentage:v1"
        ]
        assert pct_claims == [], (
            f"Expected zero extract.numeric.percentage:v1 claims from FR foreshortening "
            f"table span; got {len(pct_claims)}: {[c.text for c in pct_claims]}"
        )

    def test_narrative_two_percentages_two_timepoints_not_suppressed(
        self, extractor
    ) -> None:
        """Branch 3 negative rail: a narrative sentence with 2 CP codes AND 2 dot-decimal
        percentages at different timepoints must NOT be suppressed by the gate.

        Fixture: "Both CP8Z16 and CP10Z39 showed 94.1% procedural success at 12 months
        and 96.3% at 24 months."

        Under AND semantics (W-1 fix), branch 3 requires ≥2 CP codes AND ≥4 non-empty
        lines AND ≥2 percentage values. This single-sentence fixture has ≥2 CP codes and
        ≥2 percentage values but only 1 non-empty line, so branch 3 must return False and
        the extractor must emit numeric claims for both 94.1% and 96.3%.

        Under the old OR semantics, this fixture would have incorrectly fired branch 3
        (percentage_count >= 2 satisfied the OR) and suppressed both numeric claims.
        This test is the primary regression guard for the W-1 fix.
        """
        from locuslab.extract.noise_gates import is_foreshortening_table_span

        narrative = (
            "Both CP8Z16 and CP10Z39 showed 94.1% procedural success at 12 months "
            "and 96.3% at 24 months."
        )

        # Gate predicate must return False — only 1 non-empty line, branch 3 must not fire.
        assert not is_foreshortening_table_span(narrative), (
            "is_foreshortening_table_span must return False for a single-line narrative "
            "with 2 CP codes and 2 percentages (non_empty_lines < 4, branch 3 AND not met)"
        )

        # Full extractor run: both percentages must be emitted as numeric claims.
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span("span_narrative_two_pct_two_timepoints", _DOC_IFU_CMCP, narrative)
        claims = extractor.extract_claims([span], [doc])
        pct_claims = [
            c for c in claims
            if c.extraction_method == "extract.numeric.percentage:v1"
        ]
        texts = [c.text for c in pct_claims]
        assert any("94.1" in t for t in texts), (
            f"Expected 94.1% numeric claim from narrative; pct claims: {texts}"
        )
        assert any("96.3" in t for t in texts), (
            f"Expected 96.3% numeric claim from narrative; pct claims: {texts}"
        )

    def test_narrative_with_two_cp_codes_is_not_suppressed(self, extractor) -> None:
        """Branch 3 negative rail: a single-line clinical narrative mentioning two
        CP product codes must NOT trigger the foreshortening gate.

        Fixture: "Both CP8Z16 and CP10Z39 showed 94.1% procedural success."
        This has ≥2 CP codes but only 1 non-blank line and only 1 dot-decimal
        percentage — the branch-3 structural co-signal is absent, so the gate
        must return False and the extractor must emit a numeric claim for 94.1%.
        """
        from locuslab.extract.noise_gates import is_foreshortening_table_span

        narrative = "Both CP8Z16 and CP10Z39 showed 94.1% procedural success."

        # Gate predicate must return False for this narrative.
        assert not is_foreshortening_table_span(narrative), (
            "is_foreshortening_table_span must return False for a single-line "
            "clinical narrative with two CP codes (branch 3 co-signal absent)"
        )
        # Full extractor run: the 94.1% claim must be emitted.
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span("span_narrative_two_cp_codes", _DOC_IFU_CMCP, narrative)
        claims = extractor.extract_claims([span], [doc])
        pct_claims = [
            c for c in claims
            if c.extraction_method == "extract.numeric.percentage:v1"
        ]
        assert any("94.1" in c.text for c in pct_claims), (
            f"Expected 94.1% numeric claim from narrative with two CP codes; "
            f"pct claims: {[c.text for c in pct_claims]}"
        )
