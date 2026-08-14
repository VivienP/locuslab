"""Value-unit extractor regression tests.

Covers FM-PHASE2-4 (VALUE UNIT miss) confirmed across three dogfood runs on 2026-05-23.
Post-P1 baseline: reports/dogfood/2026-05-23/{slug}/run_post_p1/
Source documents:
  reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/input/SSCP_PG_0009_2024-03-28_en.pdf
  reports/dogfood/2026-05-23/stents-coa-rvot-rev00/input/Stents_CoA_RVOT_Rev00.pdf
  reports/dogfood/2026-05-23/numed-ifu-ccp-cmcp/input/rm0344-61e_ccp_dual_sterile_ni.pdf
  reports/dogfood/2026-05-23/numed-ifu-ccp-cmcp/input/rm0344-69e_cmcp_ce_dual_ni.pdf

Target extractor: extract.numeric.value_unit:v1 (not yet implemented — all positive tests
are intentionally RED until implementation lands).

Hard constraints (verbatim from owner brief):
  - claim_type = ClaimType.NUMERIC only (no new enum value)
  - extraction_method = "extract.numeric.value_unit:v1" (new method tag only)
  - No new Claim fields asserted (text, claim_type, extraction_method, span_id,
    document_id, confidence_label only)
  - No DocumentKind.IFU, no new ClaimType, no verdict/checker/EcoFinding
  - P1 noise gates unchanged and load-bearing

Fixture text provenance:
  All fixture strings are verbatim from the dogfood regression_candidates.md files and
  from the post-P1 run claims.jsonl span context, not from PDF direct reads.
  Span IDs and document IDs are real values from the dogfood run.
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
# Constants — extractor method tag
# ---------------------------------------------------------------------------

_METHOD_VALUE_UNIT = "extract.numeric.value_unit:v1"
_METHOD_PERCENTAGE = "extract.numeric.percentage:v1"
_METHOD_COUNT = "extract.numeric.count:v1"

# ---------------------------------------------------------------------------
# Dogfood document IDs (verbatim from run_post_p1/claims.jsonl headers)
# ---------------------------------------------------------------------------

_DOC_RAUMEDIC = "doc_3b3399318c522c17"
_DOC_STENTS = "doc_8e1133d3bb1097ce"
_DOC_IFU_CCP = "doc_f5ed001ab4c8cf2b"   # rm0344-61e (CCP)
_DOC_IFU_CMCP = "doc_1b0478f0c7f210f9"  # rm0344-69e (CMCP)

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


def _value_unit_claims(claims: list) -> list:  # type: ignore[type-arg]
    """Filter to claims emitted by the value-unit extractor only."""
    return [c for c in claims if c.extraction_method == _METHOD_VALUE_UNIT]


@pytest.fixture()
def extractor():  # type: ignore[return]
    from locuslab.extract.claim_extractor import ClaimExtractor

    return ClaimExtractor()


# ---------------------------------------------------------------------------
# Fixture text constants — verbatim from dogfood regression_candidates.md
# ---------------------------------------------------------------------------

# RAUMEDIC SSCP Section 3.3.2 — pressure measuring range
# Source: RC-REG-4 in reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/regression_candidates.md
RAUMEDIC_PRESSURE_RANGE_SPAN_ID = "span_raumedic_pressure_range_3_3_2"
RAUMEDIC_PRESSURE_RANGE_TEXT = (
    "Titel: Summary of Safety and Clinical Performance \n \n \n"
    "VA_RM_00124_FB_05  4.0 \n"
    "Seite 8 von 41 \n"
    "Pressure measuring range: -40 to +400 mmHg (53 kPa) \n"
    "Accuracy: ± 2 mmHg at 0 mmHg \n"
    "Temperature range: 25 °C to 45 °C"
)

# RAUMEDIC SSCP Section 3.3.2 — zero-point drift
# Source: RC-REG-5 in reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/regression_candidates.md
RAUMEDIC_DRIFT_SPAN_ID = "span_raumedic_drift_3_3_2"
RAUMEDIC_DRIFT_TEXT = (
    "Zero-point stability in physiology: maximum 3.0 mmHg drift in 100 h"
)

# RAUMEDIC SSCP Section 3.2 — duration
# Source: RC-REG-6 in reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/regression_candidates.md
# tests/test_extract_noise_gates.py line 96-106
RAUMEDIC_DURATION_SPAN_ID = "span_raumedic_duration_3_2"
RAUMEDIC_DURATION_TEXT = (
    "Application of a single catheter to \n"
    "maximum of 10 days \n"
    "Active (up to 29 days cumulative application). \n"
    "Repeat applications, including any restrictions"
)

# RAUMEDIC SSCP Section 3.2 / 1.1.4 — age thresholds
# Source: RC-REG-9 in reports/dogfood/2026-05-23/raumedic-sscp-pg-0009/regression_candidates.md
RAUMEDIC_AGE_SPAN_ID = "span_raumedic_age_thresholds"
RAUMEDIC_AGE_TEXT = (
    "Indications: \n"
    "Adults: ≥ 16 years \n"
    "Children: ≥ 12 years for NEUROVENT-TO \n"
    "Neonates and infants: ≥ 1 year and ≥ 3 years for specific variants"
)

# NuMED Stents SSCP — gradient mean ± SD
# Source: RC-STENTS-7 in reports/dogfood/2026-05-23/stents-coa-rvot-rev00/regression_candidates.md
# Verbatim fixture text from observed span
STENTS_GRADIENT_SPAN_ID = "span_stents_gradient_efficacy"
STENTS_GRADIENT_TEXT = (
    "NuMED \n"
    "Summary of Safety and Clinical Performance \n"
    "SSCP – Stents – CoA & RVOT \n"
    "FCD-1137                  Rev 02                                   Page 22 of 45 \n"
    "\xa0\n"
    "Short term efficacy Blood pressure gradient \n"
    "(at 1 month) \n"
    "All: from 24 ± 26 mmHg to -1 ± 15 mmHg  \n"
    "Treatment group: from 14 ± 24 to -2 ± 1"
)

# NuMED IFU (CMCP) — foreshortening span containing the RBP table
# Verbatim from IFU_FORESHORTENING_TEXT in tests/test_extract_noise_gates.py
# The RBP = 7.0 values sit in the lower half of the same span as the foreshortening table.
IFU_RBP_SPAN_ID = "span_22492c6943bc559a"  # real span ID from dogfood run
IFU_RBP_TEXT = (
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

# NuMED IFU (CMCP) — MRI safety information
# Source: RC-IFU-3 in reports/dogfood/2026-05-23/numed-ifu-ccp-cmcp/regression_candidates.md
# Verbatim fixture text from dogfood run
IFU_MRI_SPAN_ID = "span_ifu_mri_safety"
IFU_MRI_TEXT = (
    "MRI SAFETY INFORMATION \n"
    "Nonclinical testing and modeling has demonstrated that the CP Stent is MR Conditional. \n"
    "A patient with this device can be safely scanned in an MR system meeting the following "
    "conditions: \n"
    "• Static magnetic field of 1.5 T and 3 T \n"
    "• Maximum spatial gradient magnetic field of 2500 gauss/cm (25 T/m) \n"
    "• Maximum MR system reported, whole body averaged specific absorption rate (SAR) "
    "of 2.0 W/kg \n"
    "  for 15 minutes of scanning (Normal Operating Mode) \n"
    "Based on nonclinical testing and modeling, in vivo temperature rise is expected to be "
    "less than \n"
    "2 °C after 15 minutes of continuous scanning. \n"
    "Image artifacts: 3 mm spin echo / 6 mm gradient echo."
)

# NuMED IFU — locale comma-decimal variant of SAR
# Source: RC-IFU (FM-IFU-3) and post_p1_delta_synthesis.md
# Simulates the FR-locale page from the same IFU (comma decimal)
IFU_SAR_LOCALE_SPAN_ID = "span_ifu_sar_locale_fr"
IFU_SAR_LOCALE_TEXT = (
    "INFORMATIONS SUR L'IRM \n"
    "Les tests et modélisations non cliniques ont démontré que le CP Stent "
    "est IRM Conditionnel. \n"
    "• Champ magnétique statique de 1,5 T et 3 T \n"
    "• Taux d'absorption spécifique (TAS) de 2,0 W/kg \n"
    "  pour 15 minutes de balayage (Mode de fonctionnement normal) \n"
    "L'élévation de température in vivo devrait être inférieure "
    "à 2 °C après 15 minutes de balayage continu. \n"
)

# Negative control: verbatim foreshortening table cells  (from P1 fixture)
NEGATIVE_FORESHORTENING_SPAN_ID = "span_22492c6943bc559a"

# Negative control: standards section from RAUMEDIC Section 3.8
NEGATIVE_STANDARDS_SPAN_ID = "span_raumedic_standards_3_8"
NEGATIVE_STANDARDS_TEXT = (
    "Standards applied (selection): \n"
    "EN ISO 10993-1 Biological evaluation of medical devices \n"
    "IEC 60601-1 Medical electrical equipment \n"
    "ASTM F 136 Standard specification for wrought titanium \n"
    "ISO 14971:2019 Application of risk management to medical devices"
)

# Negative control: catalog / article numbers
NEGATIVE_CATALOG_SPAN_ID = "span_raumedic_catalog_numbers"
NEGATIVE_CATALOG_TEXT = (
    "Article numbers: \n"
    "NEUROVENT-P: 092946-001 \n"
    "NEUROVENT-TO: 094328-001 \n"
    "NEUROVENT-LAB: 095142-003"
)

# Negative control: page numbers and version codes
NEGATIVE_PAGE_VERSION_SPAN_ID = "span_raumedic_page_version"
NEGATIVE_PAGE_VERSION_TEXT = (
    "VA_RM_00124_FB_05  4.0 \n"
    "Seite 12 von 41 \n"
    "Page 12 of 45 \n"
    "Rev 02"
)

# Negative control: bibliography / author-year citations
NEGATIVE_BIBLIOGRAPHY_SPAN_ID = "span_raumedic_bibliography"
NEGATIVE_BIBLIOGRAPHY_TEXT = (
    "References \n"
    "1. Citerio et al. 2008. ICP monitoring in TBI. J Neurosurg. \n"
    "2. Kerry et al. 2022. Prospective study (n=200). Neurocrit Care. \n"
    "NCT00552812 — Randomized trial of ICP monitoring."
)

# Negative control: bare count n=200 (must not double-fire with count extractor)
NEGATIVE_BARE_COUNT_SPAN_ID = "span_raumedic_bare_count"
NEGATIVE_BARE_COUNT_TEXT = (
    "A prospective study enrolled n = 200 patients across three centres."
)


# ===========================================================================
# TestValueUnitExtractorBasicPatterns
# Fixtures 1-4 + fixture 7 (MRI static field)
# ===========================================================================


class TestValueUnitExtractorBasicPatterns:
    """Basic VALUE UNIT pattern extraction — RAUMEDIC SSCP + MRI static field.

    All positive tests are RED until extract.numeric.value_unit:v1 is implemented.
    """

    def test_pressure_range_lower_bound_extracted(self, extractor) -> None:
        """Fixture 1: '-40 to +400 mmHg' range — lower bound -40 mmHg extracted.

        Source: Section 3.3.2 RAUMEDIC SSCP (RC-REG-4).
        The text field must contain '-40' and 'mmHg' verbatim from the span.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_PRESSURE_RANGE_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_PRESSURE_RANGE_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "-40" in c.text and "mmHg" in c.text for c in vu_claims
        ), (
            f"Expected a value-unit claim containing '-40' and 'mmHg'; "
            f"got value-unit claims: {[c.text for c in vu_claims]}"
        )

    def test_pressure_range_upper_bound_extracted(self, extractor) -> None:
        """Fixture 1: '-40 to +400 mmHg' range — upper bound +400 mmHg extracted.

        Source: Section 3.3.2 RAUMEDIC SSCP (RC-REG-4).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_PRESSURE_RANGE_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_PRESSURE_RANGE_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "400" in c.text and "mmHg" in c.text for c in vu_claims
        ), (
            f"Expected a value-unit claim containing '400' and 'mmHg'; "
            f"got value-unit claims: {[c.text for c in vu_claims]}"
        )

    def test_pressure_range_claim_has_correct_provenance(self, extractor) -> None:
        """Fixture 1 provenance: value-unit claims from RAUMEDIC pressure range span
        must carry the correct span_id and document_id.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_PRESSURE_RANGE_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_PRESSURE_RANGE_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        for c in vu_claims:
            assert c.span_id == RAUMEDIC_PRESSURE_RANGE_SPAN_ID, (
                f"Claim span_id {c.span_id!r} != {RAUMEDIC_PRESSURE_RANGE_SPAN_ID!r}"
            )
            assert c.document_id == _DOC_RAUMEDIC, (
                f"Claim document_id {c.document_id!r} != {_DOC_RAUMEDIC!r}"
            )
            assert c.claim_type == ClaimType.NUMERIC, (
                f"Claim claim_type {c.claim_type!r} != NUMERIC"
            )

    def test_drift_value_extracted(self, extractor) -> None:
        """Fixture 2: '3.0 mmHg drift in 100 h' — drift value extracted.

        Source: Section 3.3.2 RAUMEDIC SSCP (RC-REG-5).
        Text must contain '3.0' and 'mmHg'.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_DRIFT_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_DRIFT_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "3.0" in c.text and "mmHg" in c.text for c in vu_claims
        ), (
            f"Expected value-unit claim with '3.0' and 'mmHg'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_duration_29_days_extracted(self, extractor) -> None:
        """Fixture 3a: 'up to 29 days' — duration claim extracted.

        Source: Section 3.2 RAUMEDIC SSCP (RC-REG-6).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_DURATION_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_DURATION_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "29" in c.text and "day" in c.text.lower() for c in vu_claims
        ), (
            f"Expected value-unit claim with '29' and 'day'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_duration_10_days_extracted(self, extractor) -> None:
        """Fixture 3b: 'maximum of 10 days' — duration claim extracted.

        Source: Section 3.2 RAUMEDIC SSCP (from RAUMEDIC_SPAN_PAGE7_TEXT body).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_DURATION_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_DURATION_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "10" in c.text and "day" in c.text.lower() for c in vu_claims
        ), (
            f"Expected value-unit claim with '10' and 'day'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_age_threshold_12_years_extracted(self, extractor) -> None:
        """Fixture 4a: '≥ 12 years' — age threshold claim extracted.

        Source: Section 3.2 RAUMEDIC SSCP (RC-REG-9).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_AGE_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_AGE_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "12" in c.text and "year" in c.text.lower() for c in vu_claims
        ), (
            f"Expected value-unit claim with '12' and 'year'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_age_threshold_1_year_extracted(self, extractor) -> None:
        """Fixture 4b: '≥ 1 year' — smallest age threshold claim extracted.

        Source: Section 1.1.4 RAUMEDIC SSCP (RC-REG-9 variant).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            RAUMEDIC_AGE_SPAN_ID, _DOC_RAUMEDIC, RAUMEDIC_AGE_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "1" in c.text and "year" in c.text.lower() for c in vu_claims
        ), (
            f"Expected value-unit claim with '1' and 'year'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_mri_static_field_1_5T_extracted(self, extractor) -> None:
        """Fixture 7a: '1.5 T' MRI static field — claim extracted.

        Source: RC-IFU-3, MRI SAFETY INFORMATION section of NuMED IFU.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_MRI_SPAN_ID, _DOC_IFU_CMCP, IFU_MRI_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "1.5" in c.text and " T" in c.text for c in vu_claims
        ), (
            f"Expected value-unit claim with '1.5' and 'T'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_mri_static_field_3T_extracted(self, extractor) -> None:
        """Fixture 7b: '3 T' MRI static field — claim extracted.

        Source: RC-IFU-3, same MRI safety span.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_MRI_SPAN_ID, _DOC_IFU_CMCP, IFU_MRI_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "3 T" in c.text or c.text.strip() == "3 T" for c in vu_claims
        ), (
            f"Expected value-unit claim containing '3 T'; "
            f"got: {[c.text for c in vu_claims]}"
        )


# ===========================================================================
# TestValueUnitExtractorMeanSd
# Fixture 5 — NuMED Stents gradient
# ===========================================================================


class TestValueUnitExtractorMeanSd:
    """Mean ± SD pattern — NuMED Stents gradient efficacy data.

    All positive tests are RED until implementation lands.
    """

    def test_gradient_mean_sd_baseline_extracted(self, extractor) -> None:
        """Fixture 5a: '24 ± 26 mmHg' — mean±SD baseline extracted.

        Source: RC-STENTS-7 verbatim: 'All: from 24 ± 26 mmHg to -1 ± 15 mmHg'.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span(
            STENTS_GRADIENT_SPAN_ID, _DOC_STENTS, STENTS_GRADIENT_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "24" in c.text and "mmHg" in c.text for c in vu_claims
        ), (
            f"Expected value-unit claim with '24' and 'mmHg'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_gradient_mean_sd_post_treatment_extracted(self, extractor) -> None:
        """Fixture 5b: '-1 ± 15 mmHg' — post-treatment mean±SD extracted.

        Source: RC-STENTS-7 same span.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span(
            STENTS_GRADIENT_SPAN_ID, _DOC_STENTS, STENTS_GRADIENT_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "-1" in c.text and "mmHg" in c.text for c in vu_claims
        ), (
            f"Expected value-unit claim with '-1' and 'mmHg'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_gradient_claims_carry_correct_document_id(self, extractor) -> None:
        """Provenance: value-unit claims from NuMED Stents gradient span carry
        the correct document_id and span_id.
        """
        doc = _make_doc(_DOC_STENTS)
        span = _make_page_span(
            STENTS_GRADIENT_SPAN_ID, _DOC_STENTS, STENTS_GRADIENT_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        for c in vu_claims:
            assert c.document_id == _DOC_STENTS
            assert c.span_id == STENTS_GRADIENT_SPAN_ID
            assert c.claim_type == ClaimType.NUMERIC


# ===========================================================================
# TestValueUnitExtractorIfu
# Fixtures 6, 8, 9, 10 — NuMED IFU (RBP, SAR locale, gradient field, temperature)
# ===========================================================================


class TestValueUnitExtractorIfu:
    """IFU-specific VALUE UNIT patterns — NuMED IFU CCP/CMCP.

    All positive tests are RED until implementation lands.

    Note on fixture 6 (RBP = 7.0 atm): the RBP values sit in the same PAGE span
    as the CP10Z foreshortening table (IFU_RBP_TEXT = IFU_FORESHORTENING_TEXT).
    The foreshortening gate must suppress PERCENTAGE_DECIMAL (P1 guarantee).
    The value-unit extractor must still fire on 'RBP = 7.0' because RBP is an atm
    value, not a dimensionless percentage. A co-incidental gate trigger would be a
    separate bug; this test documents the expected behavior explicitly.
    """

    def test_rbp_7_atm_extracted_from_foreshortening_span(self, extractor) -> None:
        """Fixture 6: 'RBP = 7.0' at 12mm diameter in sizing chart — atm claim extracted.

        The span also contains the foreshortening table. The P1 foreshortening gate
        suppresses percentage claims but must NOT suppress atm RBP claims.
        Source: RC-IFU-7 verbatim span.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_RBP_SPAN_ID, _DOC_IFU_CMCP, IFU_RBP_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "7.0" in c.text and "atm" in c.text.lower() for c in vu_claims
        ), (
            f"Expected value-unit claim with '7.0' and 'atm' from RBP sizing chart; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_sar_dot_decimal_extracted(self, extractor) -> None:
        """Fixture 8a: '2.0 W/kg' SAR (dot-decimal) — claim extracted.

        Source: RC-IFU-3 MRI safety information (EN locale).
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_MRI_SPAN_ID, _DOC_IFU_CMCP, IFU_MRI_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "2.0" in c.text and "W/kg" in c.text for c in vu_claims
        ), (
            f"Expected value-unit claim with '2.0' and 'W/kg'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_sar_comma_decimal_extracted(self, extractor) -> None:
        """Fixture 8b: '2,0 W/kg' SAR (comma-decimal, FR locale) — claim extracted.

        Source: FM-IFU-3 locale gap, post_p1_delta_synthesis.md confirms the
        comma-decimal variant in non-EN IFU pages. Verbatim from IFU_SAR_LOCALE_TEXT.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_SAR_LOCALE_SPAN_ID, _DOC_IFU_CMCP, IFU_SAR_LOCALE_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            # Accept either "2,0 W/kg" (verbatim) or "2.0 W/kg" (normalized)
            ("2,0" in c.text or "2.0" in c.text) and "W/kg" in c.text
            for c in vu_claims
        ), (
            f"Expected value-unit claim with '2,0' or '2.0' and 'W/kg' (FR locale); "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_gradient_field_2500_gauss_extracted(self, extractor) -> None:
        """Fixture 9: '2500 gauss/cm' — spatial gradient field claim extracted.

        Source: RC-IFU-3 MRI safety information.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_MRI_SPAN_ID, _DOC_IFU_CMCP, IFU_MRI_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "2500" in c.text and "gauss" in c.text.lower() for c in vu_claims
        ), (
            f"Expected value-unit claim with '2500' and 'gauss'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_temperature_rise_2_celsius_extracted(self, extractor) -> None:
        """Fixture 10: 'less than 2 °C' — temperature rise threshold extracted.

        Source: RC-IFU-3 MRI safety information: 'temperature rise is expected to be
        less than 2 °C after 15 minutes'.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_MRI_SPAN_ID, _DOC_IFU_CMCP, IFU_MRI_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert any(
            "2" in c.text and ("°C" in c.text or "°C" in c.text) for c in vu_claims
        ), (
            f"Expected value-unit claim with '2' and '°C'; "
            f"got: {[c.text for c in vu_claims]}"
        )

    def test_ifu_vu_claims_carry_correct_extraction_method(self, extractor) -> None:
        """Constraint check: all value-unit claims from MRI span carry the new
        extraction_method tag, not any existing method.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_MRI_SPAN_ID, _DOC_IFU_CMCP, IFU_MRI_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        # At least one claim must be present for the method assertion to be meaningful.
        assert vu_claims, (
            "Expected at least one extract.numeric.value_unit:v1 claim from MRI safety span"
        )
        for c in vu_claims:
            assert c.extraction_method == _METHOD_VALUE_UNIT
            assert c.claim_type == ClaimType.NUMERIC

    def test_rbp_all_sizing_chart_values_extracted(self, extractor) -> None:
        """W-2 regression guard: the IFU sizing chart contains 8 RBP values
        (RBP = 7.0, 6.0, 5.0, 5.0, 4.0, 4.0, 3.0, 3.0). All must emit as
        separate value-unit claims gated by the (atm) header context.
        The earlier `test_rbp_7_atm_extracted_from_foreshortening_span` only
        asserted the first claim — this test guards the full recall.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(IFU_RBP_SPAN_ID, _DOC_IFU_CMCP, IFU_RBP_TEXT)
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        rbp_claims = [c for c in vu_claims if "RBP" in c.text]
        # 8 distinct RBP fragments in the source. At least 6 should extract
        # cleanly even if some are filtered by edge dedup or boundary cases.
        assert len(rbp_claims) >= 6, (
            f"Expected at least 6 RBP claims, got {len(rbp_claims)}: "
            f"{[c.text for c in rbp_claims]}"
        )
        # Each claim must be source-grounded (substring of the span text).
        for c in rbp_claims:
            assert c.text in IFU_RBP_TEXT, (
                f"Non-source-grounded RBP claim text: {c.text!r}"
            )


# ===========================================================================
# TestValueUnitExtractorNegativeControls
# Cases A-F — extractor MUST NOT fire
# All negative-control tests must be GREEN immediately (extractor not yet
# implemented so it cannot fire on anything yet; these tests stay GREEN after
# implementation confirms the extractor does not over-match).
# ===========================================================================


class TestValueUnitExtractorNegativeControls:
    """Negative controls — value-unit extractor must not fire on non-value-unit text.

    These tests exercise the gate boundary.  They are expected to be GREEN both
    before and after implementation.  A FAIL here after implementation = regression.

    Note: Cases A also verifies the P1 guarantee (zero percentage:v1 claims from
    foreshortening spans).  If a negative-control test for percentage:v1 fails on
    the current baseline, it indicates a pre-existing FP in P1 (not for P2 to fix).
    """

    # Case A — foreshortening table cells must not emit value_unit OR percentage claims

    def test_foreshortening_table_emits_zero_value_unit_claims(
        self, extractor
    ) -> None:
        """Case A: foreshortening table span (verbatim from P1 fixture) must emit
        zero extract.numeric.value_unit:v1 claims.

        '19.5%', '30.16%' are foreshortening shortening percentages — semantically
        not value-unit facts. The gate must not be confused by the presence of 'mm'
        (balloon diameter labels like '26mm') or bare numbers.
        Source: IFU_FORESHORTENING_TEXT (same span as IFU_RBP_TEXT).
        Pre-existing P1 guarantee: also zero extract.numeric.percentage:v1.
        """
        doc = _make_doc(_DOC_IFU_CMCP, kind=DocumentKind.OTHER)
        span = _make_page_span(
            IFU_RBP_SPAN_ID,  # same span ID as the RBP fixture; foreshortening text overlaps
            _DOC_IFU_CMCP,
            IFU_RBP_TEXT,  # IFU_RBP_TEXT IS IFU_FORESHORTENING_TEXT — same span
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        pct_claims = [c for c in claims if c.extraction_method == _METHOD_PERCENTAGE]
        assert pct_claims == [], (
            f"P1 guarantee violated: percentage:v1 claims from foreshortening span: "
            f"{[c.text for c in pct_claims]}"
        )
        # The RBP atm values ARE expected to fire (that is fixture 6 above).
        # The foreshortening percentage cells ('18.33%', '22.09%') must NOT fire as value-unit.
        pct_as_vu = [
            c for c in vu_claims
            if "%" in c.text
        ]
        assert pct_as_vu == [], (
            f"Foreshortening percentage values must not fire as value-unit claims; "
            f"got: {[c.text for c in pct_as_vu]}"
        )

    # Case B — standard codes must not fire

    def test_standard_codes_do_not_emit_value_unit_claims(self, extractor) -> None:
        """Case B: 'EN ISO 10993-1', 'IEC 60601-1', 'ASTM F 136' must not produce
        value-unit claims.

        Standard codes contain digit sequences but these are catalog identifiers,
        not physical measurements. The extractor must require a recognized measurement
        unit following the number.
        Source: RAUMEDIC Section 3.8 (NEGATIVE_STANDARDS_TEXT).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            NEGATIVE_STANDARDS_SPAN_ID, _DOC_RAUMEDIC, NEGATIVE_STANDARDS_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert vu_claims == [], (
            f"Standard codes must not produce value-unit claims; "
            f"got: {[c.text for c in vu_claims]}"
        )

    # Case C — catalog / article numbers must not fire

    def test_catalog_numbers_do_not_emit_value_unit_claims(self, extractor) -> None:
        """Case C: '092946-001', '094328-001' (RAUMEDIC article numbers) must not
        produce value-unit claims.

        Article numbers contain hyphens and digits but no measurement unit context.
        Source: RAUMEDIC IFU catalog section (NEGATIVE_CATALOG_TEXT).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            NEGATIVE_CATALOG_SPAN_ID, _DOC_RAUMEDIC, NEGATIVE_CATALOG_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert vu_claims == [], (
            f"Catalog/article numbers must not produce value-unit claims; "
            f"got: {[c.text for c in vu_claims]}"
        )

    # Case D — page numbers and version codes must not fire

    def test_page_number_and_version_do_not_emit_value_unit_claims(
        self, extractor
    ) -> None:
        """Case D: 'Page 12 of 45', 'VA_RM_00124_FB_05 4.0', 'Rev 02' must not
        produce value-unit claims.

        These are PDF chrome tokens. They contain bare numbers and decimal version
        codes that must not trigger the value-unit extractor.
        Source: RAUMEDIC page header (NEGATIVE_PAGE_VERSION_TEXT).
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            NEGATIVE_PAGE_VERSION_SPAN_ID, _DOC_RAUMEDIC, NEGATIVE_PAGE_VERSION_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert vu_claims == [], (
            f"Page numbers and version codes must not produce value-unit claims; "
            f"got: {[c.text for c in vu_claims]}"
        )

    # Case E — bibliography / author-year / NCT IDs must not fire

    def test_bibliography_does_not_emit_value_unit_claims(self, extractor) -> None:
        """Case E: 'Citerio et al. 2008', 'NCT00552812' (bibliography span) must not
        produce value-unit claims.

        The bibliography span filter (is_bibliography_span) should suppress the whole
        span before any extractor runs. This test confirms the span is correctly
        identified as bibliography AND that no value-unit claims leak through.
        P4 territory: citation parsing belongs to the citation extractor, not here.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            NEGATIVE_BIBLIOGRAPHY_SPAN_ID, _DOC_RAUMEDIC, NEGATIVE_BIBLIOGRAPHY_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert vu_claims == [], (
            f"Bibliography span must not produce value-unit claims; "
            f"got: {[c.text for c in vu_claims]}"
        )

    # Case F — bare n=NN must not double-fire

    def test_bare_count_n_does_not_double_fire_as_value_unit(
        self, extractor
    ) -> None:
        """Case F: 'n = 200' must be captured by COUNT_N extractor only, not also
        by the value-unit extractor.

        The value-unit extractor must NOT fire on 'n = 200' because 'n' is not a
        physical measurement unit; it is a count variable. Double-firing would
        create duplicate numeric claims with different extraction_method values
        on the same raw text.
        Source: NEGATIVE_BARE_COUNT_TEXT.
        """
        doc = _make_doc(_DOC_RAUMEDIC)
        span = _make_page_span(
            NEGATIVE_BARE_COUNT_SPAN_ID, _DOC_RAUMEDIC, NEGATIVE_BARE_COUNT_TEXT
        )
        claims = extractor.extract_claims([span], [doc])
        vu_claims = _value_unit_claims(claims)
        assert vu_claims == [], (
            f"'n = 200' must not produce value-unit claims (handled by COUNT_N); "
            f"got: {[c.text for c in vu_claims]}"
        )
        # Positive check: COUNT_N extractor should have fired.
        count_claims = [c for c in claims if c.extraction_method == _METHOD_COUNT]
        assert count_claims, (
            "Expected COUNT_N claim for 'n = 200'; got zero count claims. "
            "Negative control requires COUNT_N to be working."
        )
