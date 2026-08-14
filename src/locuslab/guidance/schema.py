"""Guidance schema constants (enums, required field lists).

These constants are the canonical vocabulary used by the validator.
Changes here must be reflected in the JSON data files under
`docs/guidance/` and `docs/rules/guidance/`.
"""

from __future__ import annotations

SOURCE_TYPE_VALUES: frozenset[str] = frozenset(
    {"MDR", "MDCG", "harmonized_standard", "internal_checklist", "other"}
)

INGESTION_STATUS_VALUES: frozenset[str] = frozenset(
    {
        "not_uploaded",
        "uploaded_local",
        "extracted",
        "rule_candidates_created",
        "reviewed",
    }
)

DOCUMENT_FAMILY_VALUES: frozenset[str] = frozenset(
    {
        "CER",
        "PMCF_PLAN",
        "PMCF_EVAL",
        "PMS_PSUR",
        "SSCP",
        "GSPR_MAPPING",
        "IFU",
        "OTHER",
    }
)

MODAL_STRENGTH_VALUES: frozenset[str] = frozenset(
    {"required", "expected", "recommended", "guidance_only", "bonus"}
)

AUTOMATION_READINESS_VALUES: frozenset[str] = frozenset(
    {
        "deterministic",
        "ai_assisted_observation",
        "human_review_only",
        "out_of_scope",
    }
)

IMPLEMENTATION_STATUS_VALUES: frozenset[str] = frozenset(
    {"draft", "spec_only", "implemented", "retired"}
)

RA_REVIEW_STATUS_VALUES: frozenset[str] = frozenset(
    {"unreviewed", "RA_pending", "RA_approved", "RA_rejected"}
)

PACK_STATUS_VALUES: frozenset[str] = frozenset({"draft", "reviewed", "retired"})

FEEDBACK_CLASS_VALUES: frozenset[str] = frozenset(
    {
        "false_positive",
        "false_negative",
        "missing_rule",
        "bad_wording",
        "needs_RA_review",
        "out_of_scope",
    }
)

FEEDBACK_STATUS_VALUES: frozenset[str] = frozenset(
    {"new", "triaged", "fixture_added", "rule_updated", "rejected", "closed"}
)

SOURCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "source_id",
    "title",
    "issuer",
    "version_date",
    "document_family",
    "source_type",
    "official_url",
    "local_path_optional",
    "sha256_optional",
    "redistribution_note",
    "ingestion_status",
)

RULE_REQUIRED_FIELDS: tuple[str, ...] = (
    "rule_id",
    "source_id",
    "source_title",
    "source_version",
    "source_url_or_local_path",
    "source_hash",
    "document_family",
    "target_document_type",
    "exact_excerpt",
    "paraphrase",
    "modal_strength",
    "automation_readiness",
    "finding_family",
    "implementation_status",
    "RA_review_status",
    "notes",
)

FEEDBACK_REQUIRED_FIELDS: tuple[str, ...] = (
    "feedback_id",
    "created_date",
    "source",
    "class",
    "related_rule_id",
    "related_fixture",
    "description",
    "proposed_action",
    "status",
    "notes",
)

RULE_PACK_REQUIRED_FIELDS: tuple[str, ...] = (
    "pack_id",
    "document_family",
    "pack_version",
    "pack_status",
    "source_ids",
    "rules",
)

# Phase 6E-prep-A additions — DO NOT modify SOURCE_REQUIRED_FIELDS above.

CROSS_REF_RELATION_VALUES: frozenset[str] = frozenset(
    {
        "interpretive_guidance",
        "sscp_uses_clinical_evaluation_summary",
        "annual_update_with_pmcf_data",
        "equivalence_basis",
        "expert_panel_consultation",
        "pms_plan_dependency",
        "harmonised_standard_reference",
        "derived_excerpt_of",
    }
)

DERIVED_MD_REVIEW_STATUS_VALUES: frozenset[str] = frozenset(
    {
        "machine_generated",
        "RA_reviewed",
        "rejected",
    }
)

SOURCE_DERIVED_MD_OPTIONAL_FIELDS: tuple[str, ...] = (
    "derived_md_path_optional",
    "derived_md_sha256_optional",
    "derived_md_parser",
    "derived_md_review_status",
    "cross_refs_present",
    "derived_from_source_id",
)
