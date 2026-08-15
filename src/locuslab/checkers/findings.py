"""Phase 3 MVP deterministic checkers producing Finding records.

Four checker families cover the demo-grade surface:

- `check_broken_citation_anchor`: bracketed-numeric or named-key markers that
  do not resolve to any Source.
- `check_unresolved_evidence_link`: EvidenceLink.status == "source_unresolved".
- `check_source_availability_gap`: Source.availability_status == "missing_file"
  or EvidenceLink.status == "source_missing".
- `check_manual_review_required`: EvidenceLink.status == "manual_review_required"
  filtered to claim_types that meaningfully require source backing.

All checkers are pure deterministic functions. No LLM, no network, no
embeddings, no solver-first logic. Per CLAUDE.md V1 guardrails.

Conservative language convention per
docs/skills/no-confident-verdict-without-evidence: use "no resolved local
source", "unresolved evidence link", "requires manual review". Avoid
"non-compliant", "false claim", "NB will reject", "unsupported", "must",
"shall" in emitted finding evidence and remediation text.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from locuslab.extract.citation_parser import CitationMention
from locuslab.models import (
    AdjudicationState,
    Claim,
    ClaimType,
    EvidenceLink,
    Finding,
    FindingSeverity,
    Source,
)

# Checker IDs (stable, used in Finding.checker_id)
CHECKER_BROKEN_CITATION = "checker.broken_citation_anchor:v1"
CHECKER_UNRESOLVED_EVIDENCE = "checker.unresolved_evidence_link:v1"
CHECKER_SOURCE_AVAILABILITY = "checker.source_availability_gap:v1"
CHECKER_MANUAL_REVIEW = "checker.manual_review_required:v1"

# Claim types for which a manual_review_required link is worth surfacing as a
# Finding. NUMERIC and CITATION claim types are extraction primitives that do
# not require source backing in V1, so manual_review on those is expected
# noise and is filtered out.
_MANUAL_REVIEW_CLAIM_TYPES: frozenset[ClaimType] = frozenset(
    {
        ClaimType.CLASSIFICATION,
        ClaimType.CLINICAL_PERFORMANCE,
        ClaimType.SAFETY,
        ClaimType.BENEFIT_RISK,
    }
)


def make_eco_id(checker_short: str, affected_ids: Sequence[str]) -> str:
    """Build a stable, deterministic ECO ID from checker + sorted affected IDs.

    Format: `ECO-{CHECKER_SHORT}-{8 hex chars}`. The hash inputs are the
    checker short token and the affected IDs sorted ascending, so re-running
    the pipeline with the same artifacts yields the same ECO ID.
    """
    digest = hashlib.sha256()
    digest.update(checker_short.encode("utf-8"))
    for aid in sorted(affected_ids):
        digest.update(b"|")
        digest.update(aid.encode("utf-8"))
    return f"ECO-{checker_short}-{digest.hexdigest()[:8]}"


def _make_finding(
    *,
    eco_short: str,
    severity: FindingSeverity,
    checker_id: str,
    finding_type: str,
    affected_object_ids: Sequence[str],
    evidence: str,
    remediation_hint: str,
) -> Finding:
    """Build a Finding with deterministic eco_id and PENDING adjudication."""
    affected_tuple = tuple(affected_object_ids)
    return Finding(
        eco_id=make_eco_id(eco_short, affected_tuple),
        severity=severity,
        checker_id=checker_id,
        finding_type=finding_type,
        affected_object_ids=affected_tuple,
        evidence=evidence,
        remediation_hint=remediation_hint,
        adjudication_state=AdjudicationState.PENDING,
    )


def check_broken_citation_anchor(
    citations: Sequence[CitationMention],
    sources: Sequence[Source],
) -> list[Finding]:
    """Emit a Finding for each citation marker that does not resolve to a Source.

    Two failure modes are flagged:

    1. A `CitationMention` whose `normalized_key` is set (e.g., `kerry_2022`)
       but no Source carries that citation_key.
    2. A `CitationMention` with `marker_form == "numeric_bracketed"` and
       `normalized_key is None` (no resolvable bibliography entry).

    The 'numeric_parenthetical' (in-document footnote) form is NOT flagged
    here — its normalized_key is document-scoped and a missing source is
    expected behavior in V1 (footnote_to_source resolution is NEEDS-DESIGN).
    """
    findings: list[Finding] = []
    available_keys = {s.citation_key for s in sources if s.citation_key}

    for cite in citations:
        norm_key = cite.get("normalized_key")
        marker_form = cite.get("marker_form", "")
        marker_text = cite.get("marker_text", "")
        document_id = cite["document_id"]
        span_id = cite["span_id"]
        mention_id = cite["mention_id"]

        # numeric_parenthetical (in-document footnote markers like `(1)`)
        # have document-scoped normalized_keys that intentionally do not
        # resolve to a global Source. Footnote-to-source resolution is
        # NEEDS-DESIGN; skip this form to avoid noisy findings.
        if marker_form == "numeric_parenthetical":
            continue

        is_unresolved = False
        evidence_detail = ""
        if norm_key is not None and norm_key not in available_keys:
            is_unresolved = True
            evidence_detail = (
                f"Citation marker {marker_text!r} resolves to normalized key "
                f"{norm_key!r} but no local source carries that citation_key."
            )
        elif marker_form == "numeric_bracketed" and norm_key is None:
            is_unresolved = True
            evidence_detail = (
                f"Bracketed-numeric marker {marker_text!r} has no in-document "
                f"references list and no bibliography source resolves it."
            )

        if is_unresolved:
            findings.append(
                _make_finding(
                    eco_short="CITE",
                    severity=FindingSeverity.MAJOR,
                    checker_id=CHECKER_BROKEN_CITATION,
                    finding_type="unresolved_citation_marker",
                    affected_object_ids=(document_id, span_id, mention_id),
                    evidence=evidence_detail,
                    remediation_hint=(
                        "Add the cited source file to the dossier, add a "
                        "numbered references list defining the marker, or "
                        "replace the marker with an author-year citation that "
                        "resolves to a local source."
                    ),
                )
            )

    return findings


def check_unresolved_evidence_link(
    evidence_links: Sequence[EvidenceLink],
    claims: Sequence[Claim],
) -> list[Finding]:
    """Emit a Finding for each EvidenceLink with status `source_unresolved`.

    The underlying claim has been extracted but the linker could not
    associate it with any local Source. The finding is a source-traceability
    gap, not a verdict: it states that no resolved source was located,
    nothing about the truth value of the claim.
    """
    findings: list[Finding] = []
    claims_by_id = {c.claim_id: c for c in claims}

    for link in evidence_links:
        if link.status != "source_unresolved":
            continue
        claim = claims_by_id.get(link.claim_id)
        if claim is None:
            continue
        evidence_detail = (
            f"Claim {claim.claim_id!r} of type {claim.claim_type.value!r} "
            f"has no resolved local source. "
            f"Linking method: {link.linking_method!r}."
        )
        findings.append(
            _make_finding(
                eco_short="SRC",
                severity=FindingSeverity.MAJOR,
                checker_id=CHECKER_UNRESOLVED_EVIDENCE,
                finding_type="claim_without_resolved_source",
                affected_object_ids=(
                    claim.document_id,
                    claim.span_id,
                    claim.claim_id,
                    link.evidence_link_id,
                ),
                evidence=evidence_detail,
                remediation_hint=(
                    "Provide an inline citation that resolves to a local "
                    "source, attach the supporting document, or queue the "
                    "claim for manual review."
                ),
            )
        )

    return findings


def check_source_availability_gap(
    sources: Sequence[Source],
    evidence_links: Sequence[EvidenceLink],
    claims: Sequence[Claim],
) -> list[Finding]:
    """Emit Findings for Sources with `missing_file` availability.

    One Finding per missing-file Source. Severity defaults to Major; GSPR
    Status-cell-aware severity refinement (Minor when Status=Met, Informational
    when Status=Not Met) is deferred to V2 — the Status column is not currently
    exposed in the EvidenceLink record.
    """
    findings: list[Finding] = []
    claims_by_id = {c.claim_id: c for c in claims}

    # Index links by source_id so we can name the affected claims.
    links_by_source: dict[str, list[EvidenceLink]] = {}
    for link in evidence_links:
        if link.source_id is None:
            continue
        links_by_source.setdefault(link.source_id, []).append(link)

    for source in sources:
        if source.availability_status != "missing_file":
            continue
        related_links = links_by_source.get(source.source_id, [])
        related_claim_ids = sorted({link.claim_id for link in related_links})
        related_document_ids = sorted(
            {claims_by_id[cid].document_id for cid in related_claim_ids if cid in claims_by_id}
        )
        path_label = source.path or "(no path)"
        if related_claim_ids:
            evidence_detail = (
                f"Source {path_label!r} is referenced by "
                f"{len(related_claim_ids)} claim(s) but the file is not "
                f"located in the provided dossier package."
            )
        else:
            evidence_detail = (
                f"Source {path_label!r} is registered as missing_file but "
                f"is not directly referenced by any extracted claim; review "
                f"whether the reference can be removed or the file supplied."
            )
        affected = (
            tuple(related_document_ids)
            + tuple(sorted(source.origin_span_ids))
            + (source.source_id,)
            + tuple(related_claim_ids)
        )
        findings.append(
            _make_finding(
                eco_short="COMPL",
                severity=FindingSeverity.MAJOR,
                checker_id=CHECKER_SOURCE_AVAILABILITY,
                finding_type="evidence_document_referenced_but_missing",
                affected_object_ids=affected,
                evidence=evidence_detail,
                remediation_hint=(
                    f"Add {path_label!r} to the dossier package, or update "
                    f"the referencing artifact to point at an available "
                    f"evidence file."
                ),
            )
        )

    # Also emit a Finding for GSPR-type completeness gaps surfaced through
    # `source_missing` evidence links that have no associated Source record.
    seen_link_ids: set[str] = set()
    for link in evidence_links:
        if link.status != "source_missing" or link.source_id is not None:
            continue
        if link.evidence_link_id in seen_link_ids:
            continue
        seen_link_ids.add(link.evidence_link_id)
        claim = claims_by_id.get(link.claim_id)
        if claim is None:
            continue
        evidence_detail = (
            f"Completeness gap on claim {claim.claim_id!r}: the applicable "
            f"GSPR row has no evidence document reference."
        )
        findings.append(
            _make_finding(
                eco_short="COMPL",
                severity=FindingSeverity.MAJOR,
                checker_id=CHECKER_SOURCE_AVAILABILITY,
                finding_type="completeness_gap_applicable_but_no_evidence",
                affected_object_ids=(
                    claim.document_id,
                    claim.span_id,
                    claim.claim_id,
                    link.evidence_link_id,
                ),
                evidence=evidence_detail,
                remediation_hint=(
                    "Add the missing evidence document, or update the GSPR "
                    "row to mark the requirement Not Applicable with a "
                    "documented justification."
                ),
            )
        )

    return findings


def check_manual_review_required(
    evidence_links: Sequence[EvidenceLink],
    claims: Sequence[Claim],
) -> list[Finding]:
    """Emit Findings for manual_review_required links on substantive claim types.

    NUMERIC and CITATION claim types are filtered out: they are extraction
    primitives that are not expected to carry source backing in V1, so
    manual_review on those is structural noise. Findings are emitted for
    CLASSIFICATION, CLINICAL_PERFORMANCE, SAFETY, and BENEFIT_RISK claims.
    """
    findings: list[Finding] = []
    claims_by_id = {c.claim_id: c for c in claims}

    for link in evidence_links:
        if link.status != "manual_review_required":
            continue
        claim = claims_by_id.get(link.claim_id)
        if claim is None:
            continue
        if claim.claim_type not in _MANUAL_REVIEW_CLAIM_TYPES:
            continue

        if claim.claim_type == ClaimType.CLASSIFICATION:
            finding_type = "classification_rationale_requires_manual_review"
            evidence_detail = (
                f"Classification claim {claim.text!r} requires manual review "
                f"by RA: no inline rationale was detected and the linker "
                f"could not deterministically resolve supporting evidence."
            )
            remediation = (
                "Add a reference to the classification rationale (e.g., MDR "
                "Annex VIII rule applied, or a separate classification "
                "document), or accept the manual-review marker as a queue "
                "entry for the reviewer."
            )
        else:
            finding_type = "evidence_link_requires_manual_review"
            evidence_detail = (
                f"Claim {claim.claim_id!r} of type {claim.claim_type.value!r} "
                f"requires manual review: linker could not deterministically "
                f"decide whether the claim is supported by any local source."
            )
            remediation = (
                "Have a reviewer inspect the claim against the available "
                "sources and adjudicate the evidence link manually."
            )

        findings.append(
            _make_finding(
                eco_short="MANUAL",
                severity=FindingSeverity.INFORMATIONAL,
                checker_id=CHECKER_MANUAL_REVIEW,
                finding_type=finding_type,
                affected_object_ids=(
                    claim.document_id,
                    claim.span_id,
                    claim.claim_id,
                    link.evidence_link_id,
                ),
                evidence=evidence_detail,
                remediation_hint=remediation,
            )
        )

    return findings


def run_checkers(
    claims: Sequence[Claim],
    citations: Sequence[CitationMention],
    sources: Sequence[Source],
    evidence_links: Sequence[EvidenceLink],
) -> list[Finding]:
    """Run all Phase 3 MVP checkers and return findings sorted by eco_id."""
    findings: list[Finding] = []
    findings.extend(check_broken_citation_anchor(citations, sources))
    findings.extend(check_unresolved_evidence_link(evidence_links, claims))
    findings.extend(check_source_availability_gap(sources, evidence_links, claims))
    findings.extend(check_manual_review_required(evidence_links, claims))
    # Sort by eco_id for deterministic output ordering.
    findings.sort(key=lambda f: f.eco_id)
    return findings
