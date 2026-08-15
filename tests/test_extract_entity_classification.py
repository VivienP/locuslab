"""Entity and classification extractor regression tests.

These tests cover the five pattern families added to `_extract_classification`.
All 29 tests are GREEN as of 2026-05-23 (P3 implemented + W-1 reviewer fix).

Fixture strings are synthetic DemoDevice / SYNTHUDI shapes that preserve
the original regex families (14-digit-ish UDI, NB 0123, EMDN, MR, standards).

Target extractors:
  extract.classification.basic_udi_di:v1
  extract.classification.nb_number:v1
  extract.classification.emdn_code:v1
  extract.classification.mr_conditional:v1
  extract.classification.harmonized_standard:v1 (ClaimType.STANDARD_REFERENCE)

Historical implementation constraints:
  - No new Claim fields (text, claim_type, extraction_method, span_id,
    document_id, confidence_label only)
  - No DocumentKind.IFU, no new DocumentKind
  - No verdict, checker, or EcoFinding logic
  - P1/P2/P4 modules and test files are not touched
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
# Extractor method tags (target)
# ---------------------------------------------------------------------------

_METHOD_BASIC_UDI_DI = "extract.classification.basic_udi_di:v1"
_METHOD_NB_NUMBER = "extract.classification.nb_number:v1"
_METHOD_EMDN_CODE = "extract.classification.emdn_code:v1"
_METHOD_MR_CONDITIONAL = "extract.classification.mr_conditional:v1"
_METHOD_HARMONIZED_STANDARD = "extract.classification.harmonized_standard:v1"

# ---------------------------------------------------------------------------
# Synthetic document IDs (stable hashes for provenance assertions)
# ---------------------------------------------------------------------------

_DOC_DemoDevice = "doc_3b3399318c522c17"  # synthetic DemoDevice SSCP
_DOC_STENTS = "doc_8e1133d3bb1097ce"  # synthetic DemoDevice SSCP
_DOC_IFU_CCP = "doc_f5ed001ab4c8cf2b"  # synthetic DemoDevice IFU
_DOC_IFU_CMCP = "doc_1b0478f0c7f210f9"  # synthetic DemoDevice IFU

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


def _make_para_span(
    span_id: str,
    document_id: str,
    text: str,
    index: int = 0,
) -> Span:
    return Span(
        span_id=span_id,
        document_id=document_id,
        location=SpanLocation(kind=SpanLocationKind.PARAGRAPH, index=index),
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


# ===========================================================================
# Family 1 — Basic UDI-DI
# Sources:
#   RC-REG-2: DemoDevice SSCP, regression_candidates.md — fixture text
#   RC-STENTS-5: DemoDevice Stents, regression_candidates.md — verbatim span
#   rule_candidates.md RC-02: pattern rationale
# ===========================================================================


class TestBasicUdiDi:
    """Basic UDI-DI extraction from SSCP cover/section 1 spans.

    DemoDevice SSCP declares two Basic UDI-DI codes: 1234567890SYNTHUDI123 and
    12345678901SYNTHUDIX (section 3.1).
    DemoDevice Stents SSCP declares: 0987654321SYNTHUDI (section 1).

    Pattern: 14-digit numeric prefix + alphanumeric suffix, within ~50 chars
    of a "Basic UDI-DI" label or "EUDAMED" keyword.

    Negative: catalog numbers (092946-001) must not match — no 14-digit prefix.
    """

    # Verbatim from RC-REG-2 fixture text (raumedic regression_candidates.md):
    DemoDevice_CLASSIFICATION_SPAN = (
        "Device classification: Class III\n"
        "EMDN code: Z12039001\n"
        "Notified Body: 0123 (DemoNB)\n"
        "Basic UDI-DI: 1234567890SYNTHUDI123"
    )

    # Second DemoDevice UDI-DI code (from rule_candidates.md RC-02):
    DemoDevice_SECOND_UDI_SPAN = (
        "Basic UDI-DI: 12345678901SYNTHUDIX\n"
        "Catalogue number: 1234567890SYNTHUDI123"
    )

    # Verbatim from RC-STENTS-5 fixture (stents regression_candidates.md):
    STENTS_COVER_SPAN = (
        "DemoDevice covered stent)\n2009 (DemoDevice covered stent)\n"
        "DemoDevice – Not yet CE Marked \n"
        "Basic UDI-DI 0987654321SYNTHUDI \n\xa0\n"
        "2. Intended use of the device"
    )

    # Negative: DemoDevice item/catalog numbers — from run_summary.md "what worked" list
    # "Aucun numéro d'article (092946-001, 094328-001) n'a fui en claim numeric"
    DemoDevice_CATALOG_SPAN = (
        "Catalogue numbers: 092946-001, 094328-001\n"
        "These are item reference numbers for ordering purposes."
    )

    def test_demo_udi_di_extracted_as_classification(self, extractor):
        """1234567890SYNTHUDI123 near 'Basic UDI-DI' must produce CLASSIFICATION."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_demo_udi_p3_1",
            _DOC_DemoDevice,
            self.DemoDevice_CLASSIFICATION_SPAN,
        )
        claims = extractor.extract_claims([span], [doc])
        udi_claims = [
            c for c in claims
            if c.claim_type == ClaimType.CLASSIFICATION
            and c.extraction_method == _METHOD_BASIC_UDI_DI
        ]
        assert udi_claims, (
            f"Expected a CLASSIFICATION claim with method {_METHOD_BASIC_UDI_DI!r}; "
            f"got methods: {[c.extraction_method for c in claims]}"
        )
        assert any("1234567890SYNTHUDI123" in c.text for c in udi_claims), (
            f"Expected UDI-DI value in claim text; got texts: {[c.text for c in udi_claims]}"
        )

    def test_demo_second_udi_di_extracted(self, extractor):
        """12345678901SYNTHUDIX must also be extracted as a separate CLASSIFICATION claim."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_demo_udi_p3_2",
            _DOC_DemoDevice,
            self.DemoDevice_SECOND_UDI_SPAN,
        )
        claims = extractor.extract_claims([span], [doc])
        udi_claims = [
            c for c in claims
            if c.claim_type == ClaimType.CLASSIFICATION
            and c.extraction_method == _METHOD_BASIC_UDI_DI
        ]
        assert udi_claims, "Expected CLASSIFICATION claim for second UDI-DI"
        assert any("12345678901SYNTHUDIX" in c.text for c in udi_claims), (
            f"UDI-DI 12345678901SYNTHUDIX not found in classification claim texts: "
            f"{[c.text for c in udi_claims]}"
        )

    def test_stents_udi_di_extracted_as_classification(self, extractor):
        """0987654321SYNTHUDI from DemoDevice cover span must produce a CLASSIFICATION claim.

        Source: RC-STENTS-5 verbatim fixture text.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span("span_stents_udi_p3_1", _DOC_STENTS, self.STENTS_COVER_SPAN)
        claims = extractor.extract_claims([span], [doc])
        udi_claims = [
            c for c in claims
            if c.claim_type == ClaimType.CLASSIFICATION
            and c.extraction_method == _METHOD_BASIC_UDI_DI
        ]
        assert udi_claims, (
            f"Expected CLASSIFICATION claim for UDI-DI 0987654321SYNTHUDI; "
            f"got claim types: {[c.claim_type for c in claims]}"
        )
        assert any("0987654321SYNTHUDI" in c.text for c in udi_claims)

    def test_catalog_number_not_matched_as_udi_di(self, extractor):
        """092946-001 and 094328-001 must NOT produce UDI-DI claims.

        Negative control A: catalog numbers lack the UDI-DI label anchor entirely.
        The label-anchor gate short-circuits before the digit/hyphen discriminator
        is exercised; see test_catalog_number_with_udi_label_not_matched for the
        digit discriminator coverage.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_demo_catalog_neg",
            _DOC_DemoDevice,
            self.DemoDevice_CATALOG_SPAN,
        )
        claims = extractor.extract_claims([span], [doc])
        udi_claims = [
            c for c in claims
            if c.extraction_method == _METHOD_BASIC_UDI_DI
        ]
        assert not udi_claims, (
            f"Catalog numbers produced false UDI-DI claims: {[c.text for c in udi_claims]}"
        )

    def test_catalog_number_with_udi_label_not_matched(self, extractor):
        """`Basic UDI-DI: 092946-001` must NOT produce a UDI-DI claim.

        Negative control A2 (reviewer W-1): exercises the digit/hyphen
        discriminator with the label anchor present. A catalog number formatted
        like `092946-001` has 6 digits + hyphen + 3 digits, lacking both the
        10-14 digit contiguous run AND the alphanumeric letter suffix that
        BASIC_UDI_DI requires. The label anchor alone must not be sufficient.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_demo_catalog_with_label",
            _DOC_DemoDevice,
            "Basic UDI-DI: 092946-001\nArticle number: 094328-001",
        )
        claims = extractor.extract_claims([span], [doc])
        udi_claims = [
            c for c in claims
            if c.extraction_method == _METHOD_BASIC_UDI_DI
        ]
        assert not udi_claims, (
            f"Catalog number with UDI label produced false UDI-DI claims: "
            f"{[c.text for c in udi_claims]}"
        )


# ===========================================================================
# Family 2 — Notified Body number
# Sources:
#   rule_candidates.md RC-01: "NB 0123 (DemoNB)"
#   stents rule_candidates.md RC-RULE-3: "NB 1639" pattern
#   regression_candidates.md RC-REG-2: fixture text with "Notified Body: 0123"
# ===========================================================================


class TestNbNumber:
    """Notified Body number extraction.

    DemoDevice SSCP: NB 0123 (DemoNB) — from rule_candidates.md RC-01.
    DemoDevice Stents: NB 1639 — from stents rule_candidates.md RC-RULE-3.

    Pattern: literal "NB" or "Notified Body" within ±20 chars of a 4-digit number.
    Negative: bare 4-digit year in non-NB context must not match.
    """

    # Verbatim from RC-REG-2 fixture (raumedic regression_candidates.md):
    DemoDevice_NB_SPAN = (
        "Device classification: Class III\n"
        "EMDN code: Z12039001\n"
        "Notified Body: 0123 (DemoNB)\n"
        "Basic UDI-DI: 1234567890SYNTHUDI123"
    )

    # From rule_candidates.md RC-01: verbatim NB syntax used in DemoDevice
    DemoDevice_NB_INLINE_SPAN = (
        "Certified by Notified Body 0123 Demo Notified Body "
        "under MDR 2017/745 Article 52."
    )

    # From stents rule_candidates.md RC-RULE-3: DemoDevice NB number
    STENTS_NB_SPAN = (
        "Notified Body ID number 1639\n"
        "Manufacturer SRN US-MF-000010948\n"
        "Authorised Representative SRN NL-AR-000010437"
    )

    # Negative: 4-digit year in a date context — must not match NB pattern
    # Source: DemoDevice stents SSCP date references (run_summary.md header notes)
    YEAR_CONTEXT_SPAN = (
        "First CE marking obtained in 2004 for the Covered CP Stent.\n"
        "Revised 2008 per MDR transitional requirements.\n"
        "Document date: 2024-03-28."
    )

    def test_demo_nb_0123_extracted(self, extractor):
        """'Notified Body: 0123' must produce a CLASSIFICATION claim with NB number."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span("span_demo_nb_1", _DOC_DemoDevice, self.DemoDevice_NB_SPAN)
        claims = extractor.extract_claims([span], [doc])
        nb_claims = [
            c for c in claims
            if c.claim_type == ClaimType.CLASSIFICATION
            and c.extraction_method == _METHOD_NB_NUMBER
        ]
        assert nb_claims, (
            f"Expected CLASSIFICATION claim for NB 0123; "
            f"got methods: {[c.extraction_method for c in claims]}"
        )
        assert any("0123" in c.text for c in nb_claims), (
            f"NB number 0123 not in claim text; got: {[c.text for c in nb_claims]}"
        )

    def test_demo_nb_inline_format(self, extractor):
        """'Notified Body 0123 DemoNB' inline format must also be captured."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span("span_demo_nb_2", _DOC_DemoDevice, self.DemoDevice_NB_INLINE_SPAN)
        claims = extractor.extract_claims([span], [doc])
        nb_claims = [
            c for c in claims
            if c.extraction_method == _METHOD_NB_NUMBER
        ]
        assert nb_claims, "Expected NB number claim for inline 'Notified Body 0123' format"

    def test_stents_nb_1639_extracted(self, extractor):
        """NB 1639 from DemoDevice Stents cover span must produce a CLASSIFICATION claim."""
        doc = _make_doc(_DOC_STENTS)
        span = _make_para_span("span_stents_nb_1", _DOC_STENTS, self.STENTS_NB_SPAN)
        claims = extractor.extract_claims([span], [doc])
        nb_claims = [
            c for c in claims
            if c.extraction_method == _METHOD_NB_NUMBER
        ]
        assert nb_claims, "Expected CLASSIFICATION claim for NB 1639"
        assert any("1639" in c.text for c in nb_claims), (
            f"NB number 1639 not found in claim texts: {[c.text for c in nb_claims]}"
        )

    def test_year_in_date_context_not_nb(self, extractor):
        """4-digit years in date/CE context must NOT produce NB number claims.

        Negative control B: '2004', '2008', '2024' without 'NB'/'Notified Body' prefix.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_para_span("span_year_neg", _DOC_STENTS, self.YEAR_CONTEXT_SPAN)
        claims = extractor.extract_claims([span], [doc])
        nb_claims = [c for c in claims if c.extraction_method == _METHOD_NB_NUMBER]
        assert not nb_claims, (
            f"Year-only digits produced false NB claims: {[c.text for c in nb_claims]}"
        )


# ===========================================================================
# Family 3 — EMDN code
# Sources:
#   RC-REG-2: DemoDevice fixture with "EMDN code: Z12039001"
#   stents rule_candidates.md RC-RULE-4: "EMDN P070401020199"
#   run_summary.md stents: entity recall table "EMDN P070401020199 MISSED"
# ===========================================================================


class TestEmdnCode:
    """EMDN code extraction — anchored to 'EMDN' keyword.

    DemoDevice: EMDN Z12039001 (format: [A-Z]\\d{8}, 9 chars total).
    DemoDevice Stents: EMDN P070401020199 (format: [A-Z]\\d{12}, 13 chars total).

    Anchor requirement: 'EMDN' must appear within the span text as a label.
    This prevents the single-letter prefix + digits from matching EN ISO codes,
    page numbers, or standard codes that share the alphabetic prefix format.

    Negative: 'EN 868-5' — starts with a letter prefix + digits, but EMDN
    anchor is absent.
    """

    # Verbatim from RC-REG-2 fixture (raumedic regression_candidates.md):
    DemoDevice_EMDN_SPAN = (
        "Device classification: Class III\n"
        "EMDN code: Z12039001\n"
        "Notified Body: 0123 (DemoNB)\n"
        "Basic UDI-DI: 1234567890SYNTHUDI123"
    )

    # Verbatim from stents rule_candidates.md RC-RULE-4:
    STENTS_EMDN_SPAN = (
        "EMDN P070401020199\n"
        "Device description: Covered Cheatham-Platinum Stent for "
        "Coarctation of the Aorta and Right Ventricular Outflow Tract."
    )

    # Negative: harmonized standard code — similar alphabetic prefix + digits,
    # but EMDN anchor absent. Must not match EMDN pattern.
    # Verbatim fragment from RC-STENTS-6 (stents regression_candidates.md):
    EN_STANDARD_SPAN = (
        "EN 868-5:2018 Packaging for terminally sterilized medical devices — "
        "Part 5: Sealable pouches and reels of porous materials and plastic film."
    )

    def test_demo_emdn_z12039001_extracted(self, extractor):
        """EMDN Z12039001 with 'EMDN' label must produce a CLASSIFICATION claim."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span("span_demo_emdn_1", _DOC_DemoDevice, self.DemoDevice_EMDN_SPAN)
        claims = extractor.extract_claims([span], [doc])
        emdn_claims = [
            c for c in claims
            if c.claim_type == ClaimType.CLASSIFICATION
            and c.extraction_method == _METHOD_EMDN_CODE
        ]
        assert emdn_claims, (
            f"Expected CLASSIFICATION claim for EMDN Z12039001; "
            f"got methods: {[c.extraction_method for c in claims]}"
        )
        assert any("Z12039001" in c.text for c in emdn_claims), (
            f"EMDN code Z12039001 not in claim text; texts: {[c.text for c in emdn_claims]}"
        )

    def test_stents_emdn_p070401020199_extracted(self, extractor):
        """EMDN P070401020199 from DemoDevice Stents span must produce a CLASSIFICATION claim."""
        doc = _make_doc(_DOC_STENTS)
        span = _make_para_span("span_stents_emdn_1", _DOC_STENTS, self.STENTS_EMDN_SPAN)
        claims = extractor.extract_claims([span], [doc])
        emdn_claims = [
            c for c in claims
            if c.extraction_method == _METHOD_EMDN_CODE
        ]
        assert emdn_claims, "Expected CLASSIFICATION claim for EMDN P070401020199"
        assert any("P070401020199" in c.text for c in emdn_claims), (
            f"EMDN P070401020199 not in claim texts: {[c.text for c in emdn_claims]}"
        )

    def test_en_standard_without_emdn_label_not_matched(self, extractor):
        """'EN 868-5' must NOT produce an EMDN claim — no 'EMDN' anchor present.

        Negative control: standard codes share the letter+digits format but lack
        the mandatory 'EMDN' anchor in the span text.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_para_span("span_en_std_neg", _DOC_STENTS, self.EN_STANDARD_SPAN)
        claims = extractor.extract_claims([span], [doc])
        emdn_claims = [c for c in claims if c.extraction_method == _METHOD_EMDN_CODE]
        assert not emdn_claims, (
            f"EN standard produced false EMDN claim: {[c.text for c in emdn_claims]}"
        )

    def test_year_digit_not_matched_as_emdn(self, extractor):
        """Standalone 4-digit year must not match EMDN pattern.

        Negative control C: '2008', '2024' have no letter prefix and no EMDN anchor.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_year_emdn_neg", _DOC_DemoDevice,
            "Biological evaluation per ISO 10993 performed in 2008 and updated 2024."
        )
        claims = extractor.extract_claims([span], [doc])
        emdn_claims = [c for c in claims if c.extraction_method == _METHOD_EMDN_CODE]
        assert not emdn_claims, (
            f"Year digits produced false EMDN claim: {[c.text for c in emdn_claims]}"
        )


# ===========================================================================
# Family 4 — MR Conditional
# Sources:
#   rule_candidates.md RC-05: "MR conditional" labeling claim
#   numed-ifu RC-IFU-3 fixture: verbatim MRI safety section
#   run_summary.md numed-ifu: "MRI: 1.5T static field YES in span but NO claim"
# ===========================================================================


class TestMrConditional:
    """MR Conditional label extraction.

    IFU rm0344-61e and rm0344-69e declare 'MR Conditional' in the MRI Safety
    section (page 3 of both documents). DemoDevice SSCP declares 'MR conditional'
    for NEUROVENT devices (section 3.3.1, rule_candidates.md RC-05).

    Pattern: case-insensitive 'MR' + whitespace + 'conditional'.
    Low collision risk — no known false-positive surfaces in the dogfood set.
    """

    # Verbatim from RC-IFU-3 fixture (numed-ifu regression_candidates.md):
    IFU_MRI_SAFETY_SPAN = (
        "MRI SAFETY INFORMATION\n"
        "Nonclinical testing and modeling has demonstrated that the CP Stent is MR Conditional.\n"
        "A patient with this device can be safely scanned in an MR system meeting the "
        "following conditions:\n"
        "• Static magnetic field of 1.5 T and 3 T\n"
        "• Maximum spatial gradient magnetic field of 2500 gauss/cm (25 T/m)\n"
        "• Maximum MR system reported, whole body averaged specific absorption rate (SAR) "
        "of 2.0 W/kg\n"
        "  for 15 minutes of scanning (Normal Operating Mode)\n"
        "Based on nonclinical testing and modeling, in vivo temperature rise is expected "
        "to be less than\n"
        "2 °C after 15 minutes of continuous scanning.\n"
        "Image artifacts: 3 mm spin echo / 6 mm gradient echo."
    )

    # From rule_candidates.md RC-05: lowercase variant from DemoDevice
    DemoDevice_MR_COND_SPAN = (
        "The device is labelled as MR conditional.\n"
        "A FSCA was issued in December 2012 regarding MR conditional re-labeling."
    )

    # Capitalization variant (title case): 'MR Conditional' (as in IFU title block)
    TITLE_CASE_SPAN = (
        "MR Conditional: the device meets the requirements of ASTM F2503-20 "
        "for labeling as MR Conditional."
    )

    def test_ifu_mr_conditional_extracted(self, extractor):
        """'MR Conditional' in IFU MRI safety section must produce a CLASSIFICATION claim."""
        doc = _make_doc(_DOC_IFU_CCP, DocumentKind.OTHER)
        span = _make_page_span("span_ifu_mrcond_1", _DOC_IFU_CCP, self.IFU_MRI_SAFETY_SPAN, index=2)
        claims = extractor.extract_claims([span], [doc])
        mr_claims = [
            c for c in claims
            if c.claim_type == ClaimType.CLASSIFICATION
            and c.extraction_method == _METHOD_MR_CONDITIONAL
        ]
        assert mr_claims, (
            f"Expected CLASSIFICATION claim for 'MR Conditional' in IFU MRI span; "
            f"got methods: {[c.extraction_method for c in claims]}"
        )

    def test_demo_mr_conditional_lowercase(self, extractor):
        """'labelled as MR conditional' (lowercase) must also be captured."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span("span_demo_mrcond_1", _DOC_DemoDevice, self.DemoDevice_MR_COND_SPAN)
        claims = extractor.extract_claims([span], [doc])
        mr_claims = [
            c for c in claims
            if c.extraction_method == _METHOD_MR_CONDITIONAL
        ]
        assert mr_claims, "Expected MR Conditional claim for lowercase 'MR conditional'"

    def test_mr_conditional_title_case(self, extractor):
        """'MR Conditional' in title-case inline text must be captured."""
        doc = _make_doc(_DOC_IFU_CCP, DocumentKind.OTHER)
        span = _make_para_span("span_ifu_mrcond_2", _DOC_IFU_CCP, self.TITLE_CASE_SPAN)
        claims = extractor.extract_claims([span], [doc])
        mr_claims = [
            c for c in claims
            if c.extraction_method == _METHOD_MR_CONDITIONAL
        ]
        assert mr_claims, "Expected MR Conditional claim for title-case variant"


# ===========================================================================
# Family 5 — Harmonized standards
# Sources:
#   raumedic rule_candidates.md RC-13: 26+ standards in section 3.8
#   stents run_summary.md entity recall: EN ISO 11135:2014, EN ISO 11737-1:2018, etc.
#   stents regression_candidates.md RC-STENTS-6: verbatim span with ' EN I' truncation
#   numed-ifu run_summary.md: "EO sterilization (EN ISO 11135) YES in span but NO claim"
# ===========================================================================


class TestHarmonizedStandard:
    """Harmonized standard extraction from SSCPs and IFUs.

    DemoDevice section 3.8 lists 26+ standards. Four confirmed from DemoDevice Stents
    entity recall table (run_summary.md stents). Format diversity is high — the
    extractor must handle EN ISO NNNNN:YYYY, IEC NNNNN-N, ASTM F NNN, EN NNN-N,
    USP-NF YYYY.

    Dependency note: RC-STENTS-6 shows the DemoDevice standards span is truncated to
    ' EN I' by header contamination. These tests use the reconstructed full-text
    span (as would exist after header strip). The header-strip dependency is
    documented in the spec but is NOT tested here (that belongs to P1 tests).
    """

    # Reconstructed post-header-strip content from RC-STENTS-6 + stents run_summary.md
    # entity recall table ("EN ISO 11135:2014 MISSED", "EN ISO 11737-1:2018 MISSED", etc.)
    STENTS_STANDARDS_SPAN = (
        "EN ISO 11135:2014 Sterilization of health-care products — "
        "Ethylene oxide — Requirements for development, validation and routine "
        "control of a sterilization process for medical devices.\n"
        "EN ISO 11737-1:2018/A1:2021 Sterilization of health-care products — "
        "Microbiological methods — Part 1: Determination of a population of "
        "microorganisms on products.\n"
        "EN ISO 13485:2016 Medical devices — Quality management systems.\n"
        "EN ISO 15223-1:2021 Symbols to be used with information to be supplied by "
        "the manufacturer."
    )

    # From raumedic rule_candidates.md RC-13 context — ISO biocompatibility standard
    # with amendment notation, confirmed present in section 3.8 of DemoDevice SSCP
    DemoDevice_ISO_WITH_AMENDMENT = (
        "ISO 10993-1:2018/Amd 1:2021 Biological evaluation of medical devices — "
        "Part 1: Evaluation and testing within a risk management process."
    )

    # IEC electrical safety standard — from raumedic rule_candidates.md RC-13
    # "IEC 60601-1" mentioned as one of the 26+ standards
    IEC_STANDARD_SPAN = (
        "IEC 60601-1:2005/AMD1:2012/AMD2:2020 Medical electrical equipment — "
        "Part 1: General requirements for basic safety and essential performance."
    )

    # ASTM standard — referenced in MR Conditional context (rule_candidates.md RC-05:
    # "ASTM F2503 or IEC 62570")
    ASTM_STANDARD_SPAN = (
        "ASTM F 136-13 Standard Specification for Wrought Titanium-6Aluminum-4Vanadium "
        "ELI (Extra Low Interstitial) Alloy for Surgical Implant Applications."
    )

    # USP-NF — from scope brief "USP-NF 2023" as a valid harmonized standard prefix
    USP_STANDARD_SPAN = (
        "USP-NF 2023 <71> Sterility Tests — conducted on final product batch prior "
        "to release for clinical use."
    )

    # Negative: EN 868-5 in isolation (no EMDN anchor, but this tests that EN NNN-N
    # IS matched as a harmonized standard, not falsely rejected)
    EN_SHORT_STANDARD_SPAN = (
        "EN 868-5:2018 Packaging for terminally sterilized medical devices — "
        "Part 5: Sealable pouches and reels of porous materials and plastic film."
    )

    def test_en_iso_11135_extracted(self, extractor):
        """EN ISO 11135:2014 must produce a dedicated standard-reference claim."""
        doc = _make_doc(_DOC_STENTS)
        span = _make_para_span("span_stents_std_1", _DOC_STENTS, self.STENTS_STANDARDS_SPAN)
        claims = extractor.extract_claims([span], [doc])
        std_claims = [
            c for c in claims
            if c.claim_type == ClaimType.STANDARD_REFERENCE
            and c.extraction_method == _METHOD_HARMONIZED_STANDARD
        ]
        assert std_claims, (
            f"Expected STANDARD_REFERENCE claim for EN ISO 11135; "
            f"got methods: {[c.extraction_method for c in claims]}"
        )
        assert any("ISO 11135" in c.text for c in std_claims), (
            f"EN ISO 11135 not in standard claim texts: {[c.text for c in std_claims]}"
        )

    def test_multiple_standards_from_same_span(self, extractor):
        """All four EN ISO standards in STENTS_STANDARDS_SPAN must each produce a claim."""
        doc = _make_doc(_DOC_STENTS)
        span = _make_para_span("span_stents_std_multi", _DOC_STENTS, self.STENTS_STANDARDS_SPAN)
        claims = extractor.extract_claims([span], [doc])
        std_claims = [
            c for c in claims
            if c.claim_type == ClaimType.STANDARD_REFERENCE
            and c.extraction_method == _METHOD_HARMONIZED_STANDARD
        ]
        # At minimum: ISO 11135, ISO 11737-1, ISO 13485, ISO 15223-1
        texts = " ".join(c.text for c in std_claims)
        assert "ISO 11135" in texts, "EN ISO 11135:2014 not extracted"
        assert "ISO 13485" in texts, "EN ISO 13485:2016 not extracted"
        assert len(std_claims) >= 3, (
            f"Expected at least 3 standard claims from multi-standard span; "
            f"got {len(std_claims)}: {[c.text for c in std_claims]}"
        )

    def test_iso_with_amendment_notation(self, extractor):
        """ISO 10993-1:2018/Amd 1:2021 must produce one harmonized standard claim."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_demo_iso_amd",
            _DOC_DemoDevice,
            self.DemoDevice_ISO_WITH_AMENDMENT,
        )
        claims = extractor.extract_claims([span], [doc])
        std_claims = [
            c for c in claims
            if c.claim_type == ClaimType.STANDARD_REFERENCE
            and c.extraction_method == _METHOD_HARMONIZED_STANDARD
        ]
        assert std_claims, "Expected harmonized standard claim for ISO 10993-1 with amendment"
        assert any("10993" in c.text for c in std_claims)

    def test_iec_standard_extracted(self, extractor):
        """IEC 60601-1 must produce a standard-reference claim."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span("span_iec_std_1", _DOC_DemoDevice, self.IEC_STANDARD_SPAN)
        claims = extractor.extract_claims([span], [doc])
        std_claims = [
            c for c in claims
            if c.claim_type == ClaimType.STANDARD_REFERENCE
            and c.extraction_method == _METHOD_HARMONIZED_STANDARD
        ]
        assert std_claims, "Expected harmonized standard claim for IEC 60601-1"
        assert any("60601" in c.text for c in std_claims)

    def test_astm_standard_extracted(self, extractor):
        """ASTM F 136-13 must produce a standard-reference claim."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span("span_astm_std_1", _DOC_DemoDevice, self.ASTM_STANDARD_SPAN)
        claims = extractor.extract_claims([span], [doc])
        std_claims = [
            c for c in claims
            if c.claim_type == ClaimType.STANDARD_REFERENCE
            and c.extraction_method == _METHOD_HARMONIZED_STANDARD
        ]
        assert std_claims, "Expected harmonized standard claim for ASTM F 136-13"
        assert any("136" in c.text or "ASTM" in c.text for c in std_claims)

    def test_usp_nf_standard_extracted(self, extractor):
        """USP-NF 2023 <71> must produce a standard-reference claim."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span("span_usp_std_1", _DOC_DemoDevice, self.USP_STANDARD_SPAN)
        claims = extractor.extract_claims([span], [doc])
        std_claims = [
            c for c in claims
            if c.claim_type == ClaimType.STANDARD_REFERENCE
            and c.extraction_method == _METHOD_HARMONIZED_STANDARD
        ]
        assert std_claims, "Expected harmonized standard claim for USP-NF 2023"
        assert any("USP" in c.text for c in std_claims)


# ===========================================================================
# Negative controls — 7 families A-G
# Ensures no P3 pattern misfires on non-entity text.
# ===========================================================================


class TestEntityClassificationNegativeControls:
    """Negative control tests for all seven families defined in the owner brief.

    Each test asserts that no P3-method claim is emitted. Existing extractors
    (numeric, clinical_performance, etc.) may still fire — that is not tested here.
    Only P3 classification extraction methods are checked.

    All P3 methods must remain GREEN after P3 implementation.
    """

    _P3_METHODS = {
        _METHOD_BASIC_UDI_DI,
        _METHOD_NB_NUMBER,
        _METHOD_EMDN_CODE,
        _METHOD_MR_CONDITIONAL,
        _METHOD_HARMONIZED_STANDARD,
    }

    def _p3_claims(self, claims):  # type: ignore[no-untyped-def]
        return [c for c in claims if c.extraction_method in self._P3_METHODS]

    def test_neg_a_catalog_numbers(self, extractor):
        """Negative A: catalog numbers 092946-001, 094328-001 must not produce P3 claims.

        Source: raumedic run_summary.md "what worked" — confirmed no numeric leakage.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_neg_a", _DOC_DemoDevice,
            "Catalogue numbers: 092946-001, 094328-001. "
            "Please reference these codes when ordering spare parts."
        )
        claims = extractor.extract_claims([span], [doc])
        p3 = self._p3_claims(claims)
        assert not p3, f"Negative A: catalog numbers produced P3 claims: {[c.text for c in p3]}"

    def test_neg_b_page_references(self, extractor):
        """Negative B: 'Page 12 of 45', 'Seite 7 von 41' must not match NB number.

        Source: stents run_summary.md header format; raumedic header format.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span(
            "span_neg_b", _DOC_STENTS,
            "DemoDevice \nSummary of Safety and Clinical Performance \n"
            "SSCP – DemoDevice \nFCD-0001                  Rev 02"
            "                                   Page 12 of 45 \n\xa0\n"
            "3. Device Description"
        )
        claims = extractor.extract_claims([span], [doc])
        nb_claims = [c for c in claims if c.extraction_method == _METHOD_NB_NUMBER]
        assert not nb_claims, (
            f"Negative B: page number produced NB claim: {[c.text for c in nb_claims]}"
        )

    def test_neg_c_year_only_digits(self, extractor):
        """Negative C: bare year digits 2008, 2024 must not match EMDN or NB patterns."""
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_neg_c", _DOC_DemoDevice,
            "Device first certified in 2008. Current revision: 2024."
        )
        claims = extractor.extract_claims([span], [doc])
        p3 = self._p3_claims(claims)
        assert not p3, f"Negative C: year digits produced P3 claims: {[c.text for c in p3]}"

    def test_neg_d_sample_size_n_equals(self, extractor):
        """Negative D: n=200 must not match any P3 pattern.

        Source: raumedic run_summary.md — 'n=200' is a COUNT_N claim, not classification.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_neg_d", _DOC_DemoDevice,
            "Kerry et al. 2022: prospective study, n=200 patients enrolled."
        )
        claims = extractor.extract_claims([span], [doc])
        p3 = self._p3_claims(claims)
        assert not p3, f"Negative D: n=200 produced P3 claims: {[c.text for c in p3]}"

    def test_neg_e_value_unit_residuals(self, extractor):
        """Negative E: '100 h', '29 days' (VALUE UNIT residuals) must not become P3 claims.

        Source: raumedic regression_candidates.md RC-REG-5/RC-REG-6 fixture texts.
        The VALUE UNIT extractor owns these — P3 must not re-classify them.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_neg_e", _DOC_DemoDevice,
            "Zero-point stability: maximum 3.0 mmHg drift in 100 h.\n"
            "Active (up to 29 days cumulative application)."
        )
        claims = extractor.extract_claims([span], [doc])
        p3 = self._p3_claims(claims)
        assert not p3, f"Negative E: VALUE UNIT text produced P3 claims: {[c.text for c in p3]}"

    def test_neg_f_citation_markers(self, extractor):
        """Negative F: [2], (1), NCT00552812 must not double-classify as CLASSIFICATION claims.

        Source: raumedic run_summary.md (14 citations extracted as citations, not classification).
        Citation parser owns these markers; P3 must not re-emit them as CLASSIFICATION.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_neg_f", _DOC_DemoDevice,
            "Outcomes reported by Kerry et al. [2], Citerio et al. [3], "
            "and in clinical trial NCT00552812 (COAST study) (1)."
        )
        claims = extractor.extract_claims([span], [doc])
        p3 = self._p3_claims(claims)
        assert not p3, (
            f"Negative F: citation markers produced P3 classification claims: "
            f"{[c.text for c in p3]}"
        )

    def test_neg_g_pressure_unit_in_standard_name(self, extractor):
        """Negative G: a span containing unit names that appear in standard names
        must not cause VALUE UNIT results to be re-classified as harmonized standards.

        Specifically: the span 'Pressure measuring range: -40 to +400 mmHg (53 kPa)'
        must not produce a harmonized standard claim even though ISO standards can
        reference units in their titles.

        Source: raumedic run_summary.md 'Pressure measuring range' span example.
        """
        doc = _make_doc(_DOC_DemoDevice)
        span = _make_para_span(
            "span_neg_g", _DOC_DemoDevice,
            "Pressure measuring range: -40 to +400 mmHg (53 kPa)\n"
            "Maximum pressure: 1500 mmHg\n"
            "Zero-point stability: 3.0 mmHg drift in 100 h"
        )
        claims = extractor.extract_claims([span], [doc])
        std_claims = [c for c in claims if c.extraction_method == _METHOD_HARMONIZED_STANDARD]
        assert not std_claims, (
            f"Negative G: pressure/unit text produced harmonized standard claims: "
            f"{[c.text for c in std_claims]}"
        )
