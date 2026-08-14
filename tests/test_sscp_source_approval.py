"""SSCP guidance source pinning and RA excerpt approval (offline)."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.guidance import (  # noqa: E402
    OUTPUT_BOUNDARY,
    REVIEW_STATUS,
    build_checklist,
    validate_inventory,
    validate_rule_pack,
)

INVENTORY_PATH = REPO_ROOT / "docs" / "guidance" / "source_inventory.json"
SSCP_RULE_PACK_PATH = REPO_ROOT / "docs" / "rules" / "guidance" / "sscp" / "rule_pack.json"
MDCG_SSCP_PDF = (
    REPO_ROOT / "docs" / "guidance" / "sources" / "mdcg" / "md_mdcg_2019_9_sscp_en.pdf"
)
PINNED_SOURCE_ID = "mdcg-sscp-public-guidance"

# Exactly these four rule_ids are RA_approved in Phase 6C v0.3.0. The list is
# a contract: an unexpected fifth approved rule (or a missing one) should
# break the test, forcing an explicit review.
EXPECTED_APPROVED_RULE_IDS = frozenset(
    {
        "guidance.sscp.required_section.intended_purpose",
        "guidance.sscp.required_section.device_description",
        "guidance.sscp.metadata.basic_udi_di_present",
        "guidance.sscp.metadata.notified_body_identifier",
    }
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def repo_inventory() -> dict[str, object]:
    return _load(INVENTORY_PATH)


@pytest.fixture()
def sscp_pack() -> dict[str, object]:
    return _load(SSCP_RULE_PACK_PATH)


def _find_source(inv: Mapping[str, object], sid: str) -> dict[str, object]:
    sources = inv.get("sources") or []
    for src in sources:  # type: ignore[union-attr]
        if src.get("source_id") == sid:  # type: ignore[union-attr]
            return src  # type: ignore[no-any-return]
    raise KeyError(sid)


def _rules_by_id(pack: Mapping[str, object]) -> dict[str, dict[str, object]]:
    return {r["rule_id"]: r for r in pack.get("rules") or []}  # type: ignore[union-attr,index,return-value]


class TestSourcePinning:
    def test_mdcg_sscp_source_is_uploaded_local(
        self, repo_inventory: dict[str, object]
    ) -> None:
        src = _find_source(repo_inventory, PINNED_SOURCE_ID)
        assert src["ingestion_status"] == "uploaded_local"
        assert src["local_path_optional"] is not None
        assert src["sha256_optional"] is not None

    def test_pinned_source_path_exists_on_disk(
        self, repo_inventory: dict[str, object]
    ) -> None:
        src = _find_source(repo_inventory, PINNED_SOURCE_ID)
        path = REPO_ROOT / str(src["local_path_optional"])
        assert path.is_file(), f"pinned source missing on disk: {path}"

    def test_pinned_source_hash_matches_file(
        self, repo_inventory: dict[str, object]
    ) -> None:
        src = _find_source(repo_inventory, PINNED_SOURCE_ID)
        path = REPO_ROOT / str(src["local_path_optional"])
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert src["sha256_optional"] == actual, (
            f"inventory sha256 {src['sha256_optional']!r} does not match file "
            f"sha256 {actual!r}; refresh the inventory"
        )

    def test_inventory_validates(self, repo_inventory: dict[str, object]) -> None:
        issues = validate_inventory(repo_inventory)
        assert issues == [], f"Phase 6C inventory must validate cleanly: {issues}"

    def test_inventory_carries_expected_backlog_entries(
        self, repo_inventory: dict[str, object]
    ) -> None:
        ids = {s["source_id"] for s in repo_inventory["sources"]}  # type: ignore[union-attr,index]
        # Brief-mandated backlog entries (with naming flexibility for the
        # MDR full-text reference that is local rather than a placeholder).
        expected = {
            "mdcg-sscp-public-guidance",
            "eu-mdr-2017-745-art-32",
            "eu-mdr-2017-745-art-61-annex-xiv",
            "eu-mdr-2017-745-pms-psur",
            "eudamed-sscp-upload-guidance",
            "eu-lay-summary-guidance-536-2014",
            "team-nb-sscp-interpretation",
            "mdcg-2022-9-ivdr-ssp",
        }
        missing = expected - ids
        assert not missing, f"missing backlog entries: {missing}"


class TestRulePackApprovalStateMachine:
    def test_pack_validates_with_pinned_source(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        issues = validate_rule_pack(sscp_pack, repo_inventory)
        assert issues == [], f"shipped Phase 6C pack must validate: {issues}"

    def test_exactly_four_deterministic_rules_are_ra_approved(
        self, sscp_pack: dict[str, object]
    ) -> None:
        approved = {
            r["rule_id"]
            for r in sscp_pack["rules"]  # type: ignore[union-attr,index]
            if r.get("RA_review_status") == "RA_approved"  # type: ignore[union-attr]
        }
        assert approved == EXPECTED_APPROVED_RULE_IDS, (
            f"approved set differs from expected; missing="
            f"{EXPECTED_APPROVED_RULE_IDS - approved}, "
            f"unexpected={approved - EXPECTED_APPROVED_RULE_IDS}"
        )

    def test_approved_rules_carry_excerpt_hash_path_version(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        rules = _rules_by_id(sscp_pack)
        inv_hash = _find_source(repo_inventory, PINNED_SOURCE_ID)["sha256_optional"]
        for rid in EXPECTED_APPROVED_RULE_IDS:
            r = rules[rid]
            assert r.get("RA_review_status") == "RA_approved"
            assert r.get("source_excerpt_pending") is False, rid
            assert isinstance(r.get("exact_excerpt"), str) and r["exact_excerpt"], rid
            assert r.get("source_hash") == inv_hash, (
                f"{rid}: source_hash {r.get('source_hash')!r} does not match "
                f"inventory hash {inv_hash!r}"
            )
            assert isinstance(r.get("source_url_or_local_path"), str), rid
            assert isinstance(r.get("source_version"), str), rid

    def test_approved_rules_remain_spec_only(self, sscp_pack: dict[str, object]) -> None:
        rules = _rules_by_id(sscp_pack)
        for rid in EXPECTED_APPROVED_RULE_IDS:
            assert rules[rid].get("implementation_status") == "spec_only", (
                f"{rid}: approval must not flip implementation_status to implemented "
                f"in Phase 6C (deterministic checker promotion is Phase 6D)"
            )

    def test_non_approved_rules_remain_ra_pending(
        self, sscp_pack: dict[str, object]
    ) -> None:
        for r in sscp_pack["rules"]:  # type: ignore[union-attr,index]
            if r["rule_id"] not in EXPECTED_APPROVED_RULE_IDS:  # type: ignore[union-attr]
                assert r.get("RA_review_status") == "RA_pending", (  # type: ignore[union-attr]
                    f"{r['rule_id']}: non-approved rule must stay RA_pending in 6C"  # type: ignore[union-attr]
                )
                assert r.get("source_excerpt_pending") is True, (  # type: ignore[union-attr]
                    f"{r['rule_id']}: non-approved rule must keep "  # type: ignore[union-attr]
                    "source_excerpt_pending=true"
                )

    def test_pack_version_bumped_to_0_3_0(self, sscp_pack: dict[str, object]) -> None:
        assert sscp_pack.get("pack_version") == "0.3.0", (
            "Phase 6C bumps pack_version to 0.3.0"
        )


class TestApprovalGuardrails:
    def test_approved_without_excerpt_fails(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(sscp_pack)
        target = _rules_by_id(bad_pack)["guidance.sscp.required_section.intended_purpose"]
        target["exact_excerpt"] = None
        issues = validate_rule_pack(bad_pack, repo_inventory)
        assert any("V-R10" in i and "exact_excerpt" in i for i in issues), (
            f"Expected V-R10 to fire on RA_approved without excerpt: {issues}"
        )

    def test_approved_with_excerpt_pending_fails(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(sscp_pack)
        target = _rules_by_id(bad_pack)["guidance.sscp.metadata.basic_udi_di_present"]
        target["source_excerpt_pending"] = True
        issues = validate_rule_pack(bad_pack, repo_inventory)
        assert any("V-R12" in i for i in issues), (
            f"Expected V-R12 to fire on RA_approved + source_excerpt_pending=true: {issues}"
        )

    def test_approved_with_wrong_hash_fails_v_r13(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        """V-R13: source_hash on approved rule must match inventory sha256."""
        bad_pack = copy.deepcopy(sscp_pack)
        target = _rules_by_id(bad_pack)["guidance.sscp.required_section.intended_purpose"]
        target["source_hash"] = "f" * 64
        issues = validate_rule_pack(bad_pack, repo_inventory)
        assert any("V-R13" in i for i in issues), (
            f"Expected V-R13 to fire on hash mismatch: {issues}"
        )

    def test_quoting_a_not_uploaded_source_still_fails(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        """V-R7 must keep blocking excerpts/hashes on not_uploaded sources
        even after Phase 6C uploads the MDCG SSCP source."""
        bad_pack = copy.deepcopy(sscp_pack)
        # Find a backlog entry that is still not_uploaded.
        not_uploaded_sid = next(
            s["source_id"]  # type: ignore[index]
            for s in repo_inventory["sources"]  # type: ignore[union-attr,index]
            if s.get("ingestion_status") == "not_uploaded"  # type: ignore[union-attr]
        )
        bad_pack["rules"].append(  # type: ignore[union-attr,index]
            {
                "rule_id": "test.v_r7.not_uploaded_quote",
                "source_id": not_uploaded_sid,
                "source_title": "test",
                "source_version": "v1",
                "source_url_or_local_path": "test.pdf",
                "source_hash": "a" * 64,
                "document_family": "SSCP",
                "target_document_type": "SSCP",
                "exact_excerpt": "Some quoted text",
                "source_excerpt_pending": False,
                "paraphrase": "test",
                "modal_strength": "required",
                "automation_readiness": "deterministic",
                "finding_family": None,
                "implementation_status": "spec_only",
                "RA_review_status": "RA_pending",
                "notes": None,
            }
        )
        issues = validate_rule_pack(bad_pack, repo_inventory)
        assert any("V-R7" in i for i in issues), (
            f"Expected V-R7 to keep blocking not_uploaded quotes: {issues}"
        )


class TestChecklistOutputStillReviewAid:
    """Phase 6C did not change the checklist contract: every item must
    still be a non-finding review aid, regardless of how many rules are
    RA_approved."""

    def test_every_item_carries_needs_human_confirmation(
        self, sscp_pack: dict[str, object]
    ) -> None:
        checklist = build_checklist(rule_pack=sscp_pack, document_family="SSCP")
        for item in checklist["review_items"]:  # type: ignore[union-attr,index]
            assert item["review_status"] == REVIEW_STATUS  # type: ignore[index]
            assert item["output_boundary"] == OUTPUT_BOUNDARY  # type: ignore[index]

    def test_approved_rules_still_emit_review_items(
        self, sscp_pack: dict[str, object]
    ) -> None:
        """A rule moving to RA_approved must NOT cause the checklist to
        skip it — the buyer/reviewer still wants to confirm presence."""
        checklist = build_checklist(rule_pack=sscp_pack, document_family="SSCP")
        item_rule_ids = {it["rule_id"] for it in checklist["review_items"]}  # type: ignore[union-attr,index]
        assert item_rule_ids >= EXPECTED_APPROVED_RULE_IDS, (
            "Approved rules must still produce checklist items"
        )

    def test_approved_checklist_items_surface_source_excerpt_and_hash(
        self, sscp_pack: dict[str, object]
    ) -> None:
        """Dogfood guard: RA-approved source context must be visible in the
        review artifact, not only buried in rule_pack.json."""
        checklist = build_checklist(rule_pack=sscp_pack, document_family="SSCP")
        by_rule = {
            item["rule_id"]: item
            for item in checklist["review_items"]  # type: ignore[union-attr,index]
        }
        for rid in EXPECTED_APPROVED_RULE_IDS:
            item = by_rule[rid]
            assert item.get("exact_excerpt"), f"{rid}: missing exact_excerpt"
            assert item.get("source_hash"), f"{rid}: missing source_hash"
            evidence = item.get("evidence_to_review")
            assert isinstance(evidence, dict), rid
            assert evidence.get("exact_excerpt") == item.get("exact_excerpt"), rid
            assert evidence.get("source_hash") == item.get("source_hash"), rid

    def test_rendered_markdown_shows_approved_source_excerpt(
        self, sscp_pack: dict[str, object]
    ) -> None:
        """Human reviewers should see the approved source basis in Markdown."""
        from locuslab.guidance import render_markdown

        checklist = build_checklist(rule_pack=sscp_pack, document_family="SSCP")
        md = render_markdown(checklist)
        assert "Source excerpt" in md
        assert "The device's intended purpose(s) shall be described." in md

    def test_checklist_renderer_runs_under_phase_6c_pack(self, tmp_path: Path) -> None:
        """End-to-end: the Phase 6B renderer script accepts the Phase 6C pack."""
        out = tmp_path / "checklist_out"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "render_guidance_review.py"),
                "--document-family",
                "SSCP",
                "--rule-pack",
                str(SSCP_RULE_PACK_PATH),
                "--inventory",
                str(INVENTORY_PATH),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"renderer failed under Phase 6C pack. "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert (out / "guidance_review.json").is_file()
        assert (out / "guidance_review.md").is_file()


class TestNoEcoFindingsFromGuidance:
    """Hard contract: Phase 6C must not introduce any new ECO finding
    family or wire guidance rules into `locus verify`."""

    def test_no_rule_carries_eco_finding_family(self, sscp_pack: dict[str, object]) -> None:
        for r in sscp_pack["rules"]:  # type: ignore[union-attr,index]
            fam = r.get("finding_family")  # type: ignore[union-attr]
            if fam is not None:
                assert not str(fam).upper().startswith("ECO"), (
                    f"{r['rule_id']}: rule carries ECO finding_family {fam!r}; "  # type: ignore[union-attr]
                    "guidance rules must not emit ECO findings in v1"
                )
