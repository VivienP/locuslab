"""Phase 6A guidance schema validator.

Returns a list of human-readable issue strings; the caller may raise
`GuidanceValidationError` to surface them as an exception. Each validation
rule has a stable V-* ID documented in the Phase 6A spec §10 so an issue
message can be traced to a specific rule.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypeGuard

from locuslab.guidance.schema import (
    AUTOMATION_READINESS_VALUES,
    DERIVED_MD_REVIEW_STATUS_VALUES,
    DOCUMENT_FAMILY_VALUES,
    FEEDBACK_CLASS_VALUES,
    FEEDBACK_REQUIRED_FIELDS,
    FEEDBACK_STATUS_VALUES,
    IMPLEMENTATION_STATUS_VALUES,
    INGESTION_STATUS_VALUES,
    MODAL_STRENGTH_VALUES,
    PACK_STATUS_VALUES,
    RA_REVIEW_STATUS_VALUES,
    RULE_PACK_REQUIRED_FIELDS,
    RULE_REQUIRED_FIELDS,
    SOURCE_REQUIRED_FIELDS,
    SOURCE_TYPE_VALUES,
)


class GuidanceValidationError(ValueError):
    """Raised by `validate_strict`; carries the list of issues."""

    def __init__(self, issues: Sequence[str]) -> None:
        super().__init__("; ".join(issues) if issues else "no issues")
        self.issues = list(issues)


def _is_non_empty_str(v: Any) -> TypeGuard[str]:
    return isinstance(v, str) and bool(v.strip())


def validate_inventory(
    inventory: Mapping[str, Any],
    base_path: Path | None = None,
) -> list[str]:
    """Validate the source inventory dict; return list of issue strings.

    Args:
        inventory: The parsed inventory dict.
        base_path: Optional base directory for resolving relative paths in
            ``derived_md_path_optional``. Defaults to ``Path.cwd()``.
    """
    issues: list[str] = []
    sources = inventory.get("sources")
    if not isinstance(sources, list):
        issues.append("inventory: missing 'sources' list")
        return issues

    # Pre-collect all source_ids for cross-ref resolution (V-S8, V-S9, V-S10)
    all_source_ids: set[str] = {
        str(src.get("source_id", ""))
        for src in sources
        if isinstance(src, dict) and src.get("source_id")
    }

    seen_ids: set[str] = set()
    for idx, src in enumerate(sources):
        prefix = f"inventory.sources[{idx}]"
        if not isinstance(src, dict):
            issues.append(f"{prefix}: not a dict")
            continue

        for field in SOURCE_REQUIRED_FIELDS:
            if field not in src:
                issues.append(f"{prefix}: missing required field '{field}'")

        sid = src.get("source_id")
        if not _is_non_empty_str(sid):
            issues.append(f"{prefix}: 'source_id' must be a non-empty string")
        else:
            if sid in seen_ids:
                issues.append(f"{prefix}: V-S1 duplicate 'source_id' {sid!r}")
            seen_ids.add(sid)

        # V-S2 enum checks
        stype = src.get("source_type")
        if stype is not None and stype not in SOURCE_TYPE_VALUES:
            issues.append(
                f"{prefix}: V-S2 invalid 'source_type' {stype!r} "
                f"(allowed: {sorted(SOURCE_TYPE_VALUES)})"
            )
        ingest = src.get("ingestion_status")
        if ingest is not None and ingest not in INGESTION_STATUS_VALUES:
            issues.append(
                f"{prefix}: V-S2 invalid 'ingestion_status' {ingest!r} "
                f"(allowed: {sorted(INGESTION_STATUS_VALUES)})"
            )

        # V-S3 / V-S4 upload consistency
        local_path = src.get("local_path_optional")
        local_hash = src.get("sha256_optional")
        if ingest == "uploaded_local":
            if local_path in (None, ""):
                issues.append(
                    f"{prefix}: V-S3 'uploaded_local' source must set 'local_path_optional'"
                )
            if local_hash in (None, ""):
                issues.append(
                    f"{prefix}: V-S3 'uploaded_local' source must set 'sha256_optional'"
                )
        if ingest == "not_uploaded":
            if local_path not in (None, ""):
                issues.append(
                    f"{prefix}: V-S4 'not_uploaded' source must not set 'local_path_optional'"
                )
            if local_hash not in (None, ""):
                issues.append(
                    f"{prefix}: V-S4 'not_uploaded' source must not set 'sha256_optional'"
                )

        # V-S5
        if not _is_non_empty_str(src.get("redistribution_note")):
            issues.append(
                f"{prefix}: V-S5 'redistribution_note' must be a non-empty string"
            )

        # V-S6
        dfam = src.get("document_family")
        if dfam is not None and dfam not in DOCUMENT_FAMILY_VALUES:
            issues.append(
                f"{prefix}: V-S6 invalid 'document_family' {dfam!r} "
                f"(allowed: {sorted(DOCUMENT_FAMILY_VALUES)})"
            )

        # Phase 6E-prep-A: V-S7..V-S10 + derived_md_review_status enum check
        _validate_derived_md(src, prefix, all_source_ids, issues, base_path=base_path)

    return issues


def _validate_derived_md(
    src: dict[str, Any],
    prefix: str,
    all_source_ids: set[str],
    issues: list[str],
    *,
    base_path: Path | None = None,
) -> None:
    """Run V-S7..V-S10 and derived_md_review_status enum check for one source entry.

    V-S7: If ``derived_md_path_optional`` is set, the file must exist and
          ``derived_md_sha256_optional`` must match the file's SHA-256.
    V-S8..V-S10 fire only when the .md file exists and can be parsed.

    Args:
        base_path: Base directory for resolving relative ``derived_md_path_optional``
            values. Defaults to the current working directory.
    """
    # derived_md_review_status enum check (V-S2 pattern)
    review_status = src.get("derived_md_review_status")
    if review_status is not None and review_status not in DERIVED_MD_REVIEW_STATUS_VALUES:
        issues.append(
            f"{prefix}: V-S2 invalid 'derived_md_review_status' {review_status!r} "
            f"(allowed: {sorted(DERIVED_MD_REVIEW_STATUS_VALUES)})"
        )

    md_path_raw = src.get("derived_md_path_optional")
    if not md_path_raw:
        # Nothing to validate if no derived MD is declared
        return

    md_path = Path(str(md_path_raw))
    # Resolve relative paths against base_path (or cwd)
    if not md_path.is_absolute():
        resolve_base = base_path if base_path is not None else Path.cwd()
        md_path = resolve_base / md_path

    # V-S7: File existence
    if not md_path.is_file():
        issues.append(
            f"{prefix}: V-S7 'derived_md_path_optional' {str(md_path)!r} file not found"
        )
        return  # Cannot proceed without the file

    # V-S7: SHA-256 match
    expected_hash = src.get("derived_md_sha256_optional")
    if expected_hash is not None:
        actual_hash = hashlib.sha256(md_path.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            issues.append(
                f"{prefix}: V-S7 'derived_md_sha256_optional' mismatch for "
                f"{str(md_path)!r} (expected {expected_hash!r}, got {actual_hash!r})"
            )
            # Hash mismatch means we cannot trust the content; skip V-S8..V-S10
            return

    # Try to parse frontmatter for V-S8..V-S10
    try:
        from locuslab.guidance.frontmatter import parse_frontmatter
        md_text = md_path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(md_text)
    except (ValueError, UnicodeDecodeError):
        # V-S7 already handles missing/corrupt content; V-S8..V-S10 do not cascade
        return

    # V-S9: Frontmatter source_id must equal inventory source_id
    inv_sid = src.get("source_id", "")
    fm_sid = fm.source_id
    if fm_sid != inv_sid:
        issues.append(
            f"{prefix}: V-S9 frontmatter 'source_id' {fm_sid!r} does not match "
            f"inventory 'source_id' {inv_sid!r}"
        )

    # V-S8: Each cross_ref source_id must resolve in inventory
    for xref in fm.cross_refs:
        ref_sid = xref.source_id
        if ref_sid not in all_source_ids:
            issues.append(
                f"{prefix}: V-S8 frontmatter cross_ref references unknown "
                f"source_id {ref_sid!r}"
            )

    # V-S10: derived_from_source_id must resolve in inventory
    dfrom = fm.derived_from_source_id
    if dfrom and dfrom not in all_source_ids:
        issues.append(
            f"{prefix}: V-S10 frontmatter 'derived_from_source_id' {dfrom!r} "
            f"not found in inventory"
        )


def _inventory_source_map(inventory: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for src in inventory.get("sources", []) or []:
        if isinstance(src, dict) and isinstance(src.get("source_id"), str):
            by_id[src["source_id"]] = src
    return by_id


def validate_rule_pack(
    rule_pack: Mapping[str, Any], inventory: Mapping[str, Any]
) -> list[str]:
    """Validate a single rule pack against the inventory; return issues."""
    issues: list[str] = []
    src_map = _inventory_source_map(inventory)

    for field in RULE_PACK_REQUIRED_FIELDS:
        if field not in rule_pack:
            issues.append(f"rule_pack: missing required field '{field}'")

    pack_id = rule_pack.get("pack_id")
    if not _is_non_empty_str(pack_id):
        issues.append("rule_pack: V-P1 'pack_id' must be a non-empty string")

    pack_status = rule_pack.get("pack_status")
    if pack_status is not None and pack_status not in PACK_STATUS_VALUES:
        issues.append(
            f"rule_pack: V-P2 invalid 'pack_status' {pack_status!r} "
            f"(allowed: {sorted(PACK_STATUS_VALUES)})"
        )

    pack_family = rule_pack.get("document_family")
    if pack_family is not None and pack_family not in DOCUMENT_FAMILY_VALUES:
        issues.append(
            f"rule_pack: invalid 'document_family' {pack_family!r} "
            f"(allowed: {sorted(DOCUMENT_FAMILY_VALUES)})"
        )

    source_ids = rule_pack.get("source_ids") or []
    if not isinstance(source_ids, list):
        issues.append("rule_pack: 'source_ids' must be a list")
        source_ids = []
    for sid in source_ids:
        if sid not in src_map:
            issues.append(
                f"rule_pack: V-P3 source_ids references unknown source_id {sid!r}"
            )

    rules = rule_pack.get("rules") or []
    if not isinstance(rules, list):
        issues.append("rule_pack: 'rules' must be a list")
        rules = []

    seen_rule_ids: set[str] = set()
    for idx, rule in enumerate(rules):
        rprefix = f"rule_pack.rules[{idx}]"
        if not isinstance(rule, dict):
            issues.append(f"{rprefix}: not a dict")
            continue

        for field in RULE_REQUIRED_FIELDS:
            if field not in rule:
                issues.append(f"{rprefix}: missing required field '{field}'")

        rid = rule.get("rule_id")
        if not _is_non_empty_str(rid):
            issues.append(f"{rprefix}: V-R1 'rule_id' must be a non-empty string")
        else:
            if rid in seen_rule_ids:
                issues.append(f"{rprefix}: V-R1 duplicate 'rule_id' {rid!r}")
            seen_rule_ids.add(rid)

        rsid = rule.get("source_id")
        if not _is_non_empty_str(rsid):
            issues.append(f"{rprefix}: V-R2 'source_id' must be a non-empty string")
        elif rsid not in src_map:
            issues.append(f"{rprefix}: V-R2 references unknown source_id {rsid!r}")

        modal = rule.get("modal_strength")
        if modal is not None and modal not in MODAL_STRENGTH_VALUES:
            issues.append(
                f"{rprefix}: V-R3 invalid 'modal_strength' {modal!r} "
                f"(allowed: {sorted(MODAL_STRENGTH_VALUES)})"
            )

        auto = rule.get("automation_readiness")
        if auto is not None and auto not in AUTOMATION_READINESS_VALUES:
            issues.append(
                f"{rprefix}: V-R4 invalid 'automation_readiness' {auto!r} "
                f"(allowed: {sorted(AUTOMATION_READINESS_VALUES)})"
            )

        impl = rule.get("implementation_status")
        if impl is not None and impl not in IMPLEMENTATION_STATUS_VALUES:
            issues.append(
                f"{rprefix}: V-R5 invalid 'implementation_status' {impl!r} "
                f"(allowed: {sorted(IMPLEMENTATION_STATUS_VALUES)})"
            )

        ra = rule.get("RA_review_status")
        if ra is not None and ra not in RA_REVIEW_STATUS_VALUES:
            issues.append(
                f"{rprefix}: V-R6 invalid 'RA_review_status' {ra!r} "
                f"(allowed: {sorted(RA_REVIEW_STATUS_VALUES)})"
            )

        # V-R7 — cannot quote a source that has not been uploaded
        ingest = src_map.get(rsid or "", {}).get("ingestion_status")
        if ingest == "not_uploaded":
            if rule.get("source_hash") not in (None, ""):
                issues.append(
                    f"{rprefix}: V-R7 source is 'not_uploaded' but rule sets a "
                    f"'source_hash' (cannot quote a hash we have not computed)"
                )
            excerpt = rule.get("exact_excerpt")
            if excerpt not in (None, ""):
                issues.append(
                    f"{rprefix}: V-R7 source is 'not_uploaded' but rule sets an "
                    f"'exact_excerpt' (cannot quote a source we have not uploaded)"
                )

        # V-R8 — AI-assisted observation cannot become a final deterministic finding
        if auto == "ai_assisted_observation":
            if impl == "implemented":
                issues.append(
                    f"{rprefix}: V-R8 'ai_assisted_observation' rule must not have "
                    f"'implementation_status' == 'implemented' (it cannot become a "
                    f"final ECO finding)"
                )
            fam = rule.get("finding_family")
            if _is_non_empty_str(fam) and str(fam).upper().startswith("ECO"):
                issues.append(
                    f"{rprefix}: V-R8 'ai_assisted_observation' rule must not carry "
                    f"an ECO 'finding_family' (it produces an observation, not a "
                    f"finding)"
                )

        # V-R9 — human_review_only / out_of_scope rules must remain spec_only
        if auto in {"human_review_only", "out_of_scope"} and impl not in (None, "spec_only"):
            issues.append(
                f"{rprefix}: V-R9 {auto!r} rule must have 'implementation_status' "
                f"== 'spec_only' (got {impl!r})"
            )

        # Phase 6B additions (V-R10 / V-R11 / V-R12) govern the RA_approved
        # and source_excerpt_pending lifecycle introduced by the SSCP v0 pack.
        excerpt_pending_raw = rule.get("source_excerpt_pending")
        excerpt_pending = bool(excerpt_pending_raw) if excerpt_pending_raw is not None else False
        excerpt = rule.get("exact_excerpt")
        rule_hash = rule.get("source_hash")

        # V-R10 — RA_approved rules must carry a verbatim excerpt AND a
        # source hash. V-R7 already prevents source_hash on a not_uploaded
        # source, so V-R10 cascades into "RA_approved implies uploaded_local".
        if ra == "RA_approved":
            if not _is_non_empty_str(excerpt):
                issues.append(
                    f"{rprefix}: V-R10 'RA_approved' rule must carry a non-empty "
                    f"'exact_excerpt' (got {excerpt!r})"
                )
            if not _is_non_empty_str(rule_hash):
                issues.append(
                    f"{rprefix}: V-R10 'RA_approved' rule must carry a non-empty "
                    f"'source_hash' (got {rule_hash!r})"
                )

        # V-R11 — a rule with no excerpt must explicitly flag
        # source_excerpt_pending=true, so a future reader sees the honesty
        # marker rather than guessing whether the omission is intentional.
        if excerpt in (None, "") and not excerpt_pending:
            issues.append(
                f"{rprefix}: V-R11 rule has 'exact_excerpt' null/empty but does "
                f"not declare 'source_excerpt_pending': true; mark explicitly "
                f"or supply an excerpt"
            )

        # V-R12 — RA_approved cannot also be source_excerpt_pending; the
        # two flags are mutually exclusive by construction.
        if ra == "RA_approved" and excerpt_pending:
            issues.append(
                f"{rprefix}: V-R12 'RA_approved' rule must not carry "
                f"'source_excerpt_pending': true"
            )

        # V-R13 (Phase 6C) — when a rule is RA_approved, its source_hash MUST
        # match the inventory's sha256_optional for the referenced source.
        # Catches the silent-drift failure mode where a future packet refreshes
        # the inventory's hash (new source revision) but forgets to refresh
        # the per-rule hash, leaving the rule pointing at a stale excerpt.
        if ra == "RA_approved" and _is_non_empty_str(rule_hash) and rsid in src_map:
            inv_hash = src_map[rsid].get("sha256_optional")
            if _is_non_empty_str(inv_hash) and rule_hash != inv_hash:
                issues.append(
                    f"{rprefix}: V-R13 'RA_approved' rule 'source_hash' "
                    f"{rule_hash!r} does not match inventory source "
                    f"{rsid!r} sha256_optional {inv_hash!r}"
                )

    return issues


def validate_feedback(feedback: Mapping[str, Any]) -> list[str]:
    """Validate the feedback dict; return list of issue strings."""
    issues: list[str] = []
    items = feedback.get("feedback_items")
    if not isinstance(items, list):
        issues.append("feedback: missing 'feedback_items' list")
        return issues

    seen_ids: set[str] = set()
    for idx, item in enumerate(items):
        prefix = f"feedback.feedback_items[{idx}]"
        if not isinstance(item, dict):
            issues.append(f"{prefix}: not a dict")
            continue

        for field in FEEDBACK_REQUIRED_FIELDS:
            if field not in item:
                issues.append(f"{prefix}: missing required field '{field}'")

        fid = item.get("feedback_id")
        if not _is_non_empty_str(fid):
            issues.append(f"{prefix}: V-F1 'feedback_id' must be non-empty string")
        else:
            if fid in seen_ids:
                issues.append(f"{prefix}: V-F1 duplicate 'feedback_id' {fid!r}")
            seen_ids.add(fid)

        cls = item.get("class")
        if cls is not None and cls not in FEEDBACK_CLASS_VALUES:
            issues.append(
                f"{prefix}: V-F2 invalid 'class' {cls!r} "
                f"(allowed: {sorted(FEEDBACK_CLASS_VALUES)})"
            )

        status = item.get("status")
        if status is not None and status not in FEEDBACK_STATUS_VALUES:
            issues.append(
                f"{prefix}: V-F3 invalid 'status' {status!r} "
                f"(allowed: {sorted(FEEDBACK_STATUS_VALUES)})"
            )

        if not _is_non_empty_str(item.get("description")):
            issues.append(f"{prefix}: V-F4 'description' must be a non-empty string")

    return issues


def validate_all(
    *,
    inventory: Mapping[str, Any],
    rule_packs: Sequence[Mapping[str, Any]] | None = None,
    feedback: Mapping[str, Any] | None = None,
) -> list[str]:
    """Run inventory + rule-pack + feedback validation; return aggregated issues."""
    issues: list[str] = []
    issues.extend(validate_inventory(inventory))
    for pack in rule_packs or []:
        issues.extend(validate_rule_pack(pack, inventory))
    if feedback is not None:
        issues.extend(validate_feedback(feedback))
    return issues


def validate_strict(
    *,
    inventory: Mapping[str, Any],
    rule_packs: Sequence[Mapping[str, Any]] | None = None,
    feedback: Mapping[str, Any] | None = None,
) -> None:
    """Convenience wrapper that raises GuidanceValidationError if any issue found."""
    issues = validate_all(
        inventory=inventory, rule_packs=rule_packs, feedback=feedback
    )
    if issues:
        raise GuidanceValidationError(issues)
