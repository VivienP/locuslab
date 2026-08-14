"""Guidance rule-pack foundation tests (offline)."""

from __future__ import annotations

import copy
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

from locuslab.report.language import REPORT_FORBIDDEN_LANGUAGE  # noqa: E402

INVENTORY_PATH = REPO_ROOT / "docs" / "guidance" / "source_inventory.json"
SSCP_RULE_PACK_PATH = REPO_ROOT / "docs" / "rules" / "guidance" / "sscp" / "rule_pack.json"
FEEDBACK_PATH = REPO_ROOT / "docs" / "rules" / "guidance" / "feedback_items.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_guidance_rules.py"

# Rule pack paraphrases legitimately quote regulatory modal verbs ("an SSCP
# shall include...", "the manufacturer must..."). We strip those from the
# canonical ban so rule-pack prose can faithfully paraphrase MDR/MDCG text
# without tripping the verdict-language gate, while every other buyer-prose
# ban stays enforced.
_RULE_PACK_MODAL_EXCEPTIONS = frozenset({"must ", "shall "})
RULE_PACK_FORBIDDEN_VERDICT_LANGUAGE = (
    REPORT_FORBIDDEN_LANGUAGE - _RULE_PACK_MODAL_EXCEPTIONS
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Mapping[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.fixture()
def repo_inventory() -> dict[str, object]:
    return _load(INVENTORY_PATH)


@pytest.fixture()
def repo_sscp_pack() -> dict[str, object]:
    return _load(SSCP_RULE_PACK_PATH)


@pytest.fixture()
def repo_feedback() -> dict[str, object]:
    return _load(FEEDBACK_PATH)


def _validate_all(
    inventory: dict[str, object],
    rule_pack: dict[str, object] | None = None,
    feedback: dict[str, object] | None = None,
) -> list[str]:
    """Helper: run the validator and return a list of issue strings."""
    from locuslab.guidance import validate_all

    return validate_all(inventory=inventory, rule_packs=[rule_pack] if rule_pack else [],
                        feedback=feedback)


class TestRepoFilesValidate:
    def test_repo_inventory_validates(self, repo_inventory: dict[str, object]) -> None:
        issues = _validate_all(repo_inventory)
        assert issues == [], f"Inventory issues: {issues}"

    def test_repo_sscp_pack_validates(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        issues = _validate_all(repo_inventory, rule_pack=repo_sscp_pack)
        assert issues == [], f"SSCP pack issues: {issues}"

    def test_repo_feedback_validates(
        self,
        repo_inventory: dict[str, object],
        repo_feedback: dict[str, object],
    ) -> None:
        issues = _validate_all(repo_inventory, feedback=repo_feedback)
        assert issues == [], f"Feedback issues: {issues}"


class TestSourceInventoryValidation:
    def test_missing_required_field_fails(
        self, repo_inventory: dict[str, object]
    ) -> None:
        bad = copy.deepcopy(repo_inventory)
        bad["sources"][0].pop("issuer")  # type: ignore[union-attr,index]
        issues = _validate_all(bad)
        assert any("issuer" in i.lower() for i in issues), f"Expected issuer error; got: {issues}"

    def test_invalid_source_type_enum_fails(
        self, repo_inventory: dict[str, object]
    ) -> None:
        bad = copy.deepcopy(repo_inventory)
        bad["sources"][0]["source_type"] = "BOGUS_TYPE"  # type: ignore[union-attr,index]
        issues = _validate_all(bad)
        assert any("source_type" in i for i in issues), f"Expected source_type error; got: {issues}"

    def test_invalid_ingestion_status_enum_fails(
        self, repo_inventory: dict[str, object]
    ) -> None:
        bad = copy.deepcopy(repo_inventory)
        bad["sources"][0]["ingestion_status"] = "almost_uploaded"  # type: ignore[union-attr,index]
        issues = _validate_all(bad)
        assert any("ingestion_status" in i for i in issues), (
            f"Expected ingestion_status error; got: {issues}"
        )

    def test_uploaded_local_without_hash_fails(
        self, repo_inventory: dict[str, object]
    ) -> None:
        bad = copy.deepcopy(repo_inventory)
        bad["sources"][0]["ingestion_status"] = "uploaded_local"  # type: ignore[union-attr,index]
        bad["sources"][0]["local_path_optional"] = "docs/guidance/dummy.pdf"  # type: ignore[union-attr,index]
        bad["sources"][0]["sha256_optional"] = None  # type: ignore[union-attr,index]
        issues = _validate_all(bad)
        assert any("sha256" in i.lower() and "uploaded_local" in i for i in issues), (
            f"Expected uploaded_local-missing-hash error; got: {issues}"
        )

    def test_not_uploaded_with_local_hash_fails(
        self, repo_inventory: dict[str, object]
    ) -> None:
        bad = copy.deepcopy(repo_inventory)
        bad["sources"][0]["ingestion_status"] = "not_uploaded"  # type: ignore[union-attr,index]
        bad["sources"][0]["local_path_optional"] = "docs/guidance/imaginary.pdf"  # type: ignore[union-attr,index]
        bad["sources"][0]["sha256_optional"] = "a" * 64  # type: ignore[union-attr,index]
        issues = _validate_all(bad)
        assert any("not_uploaded" in i for i in issues), (
            f"Expected not_uploaded-with-local-data error; got: {issues}"
        )

    def test_not_uploaded_with_nulls_passes(
        self, repo_inventory: dict[str, object]
    ) -> None:
        # The repo entry is already not_uploaded with null path/hash.
        # Add a second one and confirm it still passes.
        good = copy.deepcopy(repo_inventory)
        good["sources"].append(  # type: ignore[union-attr]
            {
                "source_id": "test-extra-not-uploaded",
                "title": "Test source",
                "issuer": "EC",
                "version_date": "2024-01-01",
                "document_family": "SSCP",
                "source_type": "MDCG",
                "official_url": "https://example.org/doc.pdf",
                "local_path_optional": None,
                "sha256_optional": None,
                "redistribution_note": "freely redistributable per EC notice",
                "ingestion_status": "not_uploaded",
            }
        )
        issues = _validate_all(good)
        assert issues == [], f"Expected no issues; got: {issues}"

    def test_duplicate_source_id_fails(
        self, repo_inventory: dict[str, object]
    ) -> None:
        bad = copy.deepcopy(repo_inventory)
        bad["sources"].append(copy.deepcopy(bad["sources"][0]))  # type: ignore[union-attr,index]
        issues = _validate_all(bad)
        assert any("duplicate" in i.lower() and "source_id" in i for i in issues), (
            f"Expected duplicate-source_id error; got: {issues}"
        )

    def test_unknown_document_family_fails(
        self, repo_inventory: dict[str, object]
    ) -> None:
        bad = copy.deepcopy(repo_inventory)
        bad["sources"][0]["document_family"] = "BOGUS_FAMILY"  # type: ignore[union-attr,index]
        issues = _validate_all(bad)
        assert any("document_family" in i for i in issues), (
            f"Expected document_family error; got: {issues}"
        )


class TestRulePackValidation:
    def test_rule_with_unknown_source_id_fails(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(repo_sscp_pack)
        bad_pack["rules"].append(  # type: ignore[union-attr,index]
            _make_test_rule(source_id="ghost-source-does-not-exist")
        )
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any("ghost-source-does-not-exist" in i for i in issues), (
            f"Expected unknown source_id error; got: {issues}"
        )

    def test_invalid_modal_strength_fails(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(repo_sscp_pack)
        rule = _make_test_rule(modal_strength="mandatory")
        bad_pack["rules"].append(rule)  # type: ignore[union-attr,index]
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any("modal_strength" in i for i in issues), (
            f"Expected modal_strength error; got: {issues}"
        )

    def test_invalid_automation_readiness_fails(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(repo_sscp_pack)
        bad_pack["rules"].append(  # type: ignore[union-attr,index]
            _make_test_rule(automation_readiness="probably_works")
        )
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any("automation_readiness" in i for i in issues), (
            f"Expected automation_readiness error; got: {issues}"
        )

    def test_ai_assisted_observation_cannot_be_implemented(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        """V-R8: critical boundary — AI-assisted obs cannot become a deterministic finding."""
        bad_pack = copy.deepcopy(repo_sscp_pack)
        bad_pack["rules"].append(  # type: ignore[union-attr,index]
            _make_test_rule(
                automation_readiness="ai_assisted_observation",
                implementation_status="implemented",
            )
        )
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any(
            "ai_assisted_observation" in i and "implemented" in i for i in issues
        ), f"Expected ai_assisted_observation/implemented boundary error; got: {issues}"

    def test_ai_assisted_observation_cannot_carry_eco_finding_family(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(repo_sscp_pack)
        bad_pack["rules"].append(  # type: ignore[union-attr,index]
            _make_test_rule(
                automation_readiness="ai_assisted_observation",
                finding_family="ECO-CITE",
            )
        )
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any(
            "ai_assisted_observation" in i and "finding_family" in i for i in issues
        ), f"Expected ai_assisted_observation/finding_family boundary error; got: {issues}"

    def test_ai_assisted_observation_spec_only_non_eco_passes(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        """V-R8 positive case — the buyer-facing claim that 'AI observations
        are clearly separated from ECO findings' requires V-R8 to ACCEPT the
        valid shape, not just reject the invalid ones. Without this test we
        cannot prove V-R8 distinguishes good inputs from bad."""
        good_pack = copy.deepcopy(repo_sscp_pack)
        good_pack["rules"].append(  # type: ignore[union-attr,index]
            _make_test_rule(
                rule_id="test.r8.positive.spec_only.non_eco",
                automation_readiness="ai_assisted_observation",
                implementation_status="spec_only",
                finding_family=None,
            )
        )
        issues = _validate_all(repo_inventory, rule_pack=good_pack)
        # No V-R8 issue should appear for the well-formed rule. Other rules
        # in the pack must also stay clean (the repo pack is empty, so issues
        # would only come from the appended rule).
        v_r8_issues = [i for i in issues if "V-R8" in i]
        assert v_r8_issues == [], (
            f"V-R8 unexpectedly fired on a valid spec_only/non-ECO "
            f"ai_assisted_observation rule: {v_r8_issues}"
        )

    def test_human_review_only_must_be_spec_only(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(repo_sscp_pack)
        bad_pack["rules"].append(  # type: ignore[union-attr,index]
            _make_test_rule(
                automation_readiness="human_review_only",
                implementation_status="implemented",
            )
        )
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any(
            "human_review_only" in i and "spec_only" in i for i in issues
        ), f"Expected human_review_only/spec_only error; got: {issues}"

    def test_rule_quoting_not_uploaded_source_fails(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        """V-R7: can't quote a source we haven't uploaded."""
        bad_pack = copy.deepcopy(repo_sscp_pack)
        # Phase 6C flipped the first MDCG source to uploaded_local. Look up
        # the first source that is still not_uploaded so V-R7 has a target.
        not_uploaded_sid = next(
            s["source_id"]  # type: ignore[index]
            for s in repo_inventory["sources"]  # type: ignore[union-attr,index]
            if s.get("ingestion_status") == "not_uploaded"  # type: ignore[union-attr]
        )
        bad_pack["rules"].append(  # type: ignore[union-attr,index]
            _make_test_rule(
                source_id=not_uploaded_sid,
                source_hash="a" * 64,
                exact_excerpt="Some exact quote from a source we haven't uploaded.",
            )
        )
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any(
            "not_uploaded" in i and ("source_hash" in i or "excerpt" in i)
            for i in issues
        ), f"Expected not_uploaded source-hash/excerpt error; got: {issues}"

    def test_duplicate_rule_id_within_pack_fails(
        self,
        repo_inventory: dict[str, object],
        repo_sscp_pack: dict[str, object],
    ) -> None:
        bad_pack = copy.deepcopy(repo_sscp_pack)
        rule = _make_test_rule(rule_id="dup.rule.x")
        bad_pack["rules"].append(rule)  # type: ignore[union-attr,index]
        bad_pack["rules"].append(copy.deepcopy(rule))  # type: ignore[union-attr,index]
        issues = _validate_all(repo_inventory, rule_pack=bad_pack)
        assert any("duplicate" in i.lower() and "rule_id" in i for i in issues), (
            f"Expected duplicate-rule_id error; got: {issues}"
        )


class TestFeedbackValidation:
    def test_feedback_validates(
        self,
        repo_inventory: dict[str, object],
        repo_feedback: dict[str, object],
    ) -> None:
        issues = _validate_all(repo_inventory, feedback=repo_feedback)
        assert issues == [], f"Feedback issues: {issues}"

    def test_invalid_feedback_class_fails(
        self,
        repo_inventory: dict[str, object],
        repo_feedback: dict[str, object],
    ) -> None:
        bad = copy.deepcopy(repo_feedback)
        bad["feedback_items"].append(  # type: ignore[union-attr,index]
            {
                "feedback_id": "fb-bad-class-001",
                "created_date": "2026-05-24",
                "source": "test",
                "class": "totally_invalid",
                "related_rule_id": None,
                "related_fixture": None,
                "description": "test",
                "proposed_action": "test",
                "status": "new",
                "notes": None,
            }
        )
        issues = _validate_all(repo_inventory, feedback=bad)
        assert any("class" in i and "totally_invalid" in i for i in issues), (
            f"Expected feedback class error; got: {issues}"
        )

    def test_empty_feedback_description_fails(
        self,
        repo_inventory: dict[str, object],
        repo_feedback: dict[str, object],
    ) -> None:
        bad = copy.deepcopy(repo_feedback)
        bad["feedback_items"].append(  # type: ignore[union-attr,index]
            {
                "feedback_id": "fb-empty-desc-001",
                "created_date": "2026-05-24",
                "source": "test",
                "class": "missing_rule",
                "related_rule_id": None,
                "related_fixture": None,
                "description": "",
                "proposed_action": "test",
                "status": "new",
                "notes": None,
            }
        )
        issues = _validate_all(repo_inventory, feedback=bad)
        assert any("description" in i for i in issues), (
            f"Expected empty description error; got: {issues}"
        )


class TestValidationScript:
    def test_script_exits_zero_on_repo_files(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--inventory",
                str(INVENTORY_PATH),
                "--rules",
                str(SSCP_RULE_PACK_PATH),
                "--feedback",
                str(FEEDBACK_PATH),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"Script failed on repo files. stdout: {result.stdout!r} stderr: {result.stderr!r}"
        )
        assert "validated" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_script_exits_nonzero_on_invalid_fixture(self, tmp_path: Path) -> None:
        bad_inventory = {
            "_schema_version": "guidance.source_inventory.v1",
            "sources": [
                {
                    "source_id": "bogus",
                    "title": "Bogus",
                    "issuer": "test",
                    "version_date": "2026-01-01",
                    "document_family": "SSCP",
                    "source_type": "INVALID_TYPE",
                    "official_url": None,
                    "local_path_optional": None,
                    "sha256_optional": None,
                    "redistribution_note": "test",
                    "ingestion_status": "not_uploaded",
                }
            ],
        }
        bad_inventory_path = tmp_path / "bad_inventory.json"
        _write_json(bad_inventory_path, bad_inventory)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--inventory", str(bad_inventory_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0, (
            f"Script should fail on invalid inventory; stdout: {result.stdout!r}"
        )
        assert "source_type" in (result.stdout + result.stderr)


class TestForbiddenLanguageInRulePackProse:
    def test_rule_pack_prose_has_no_forbidden_verdict_language(
        self, repo_sscp_pack: dict[str, object]
    ) -> None:
        # Walk all string fields in the SSCP pack and check.
        offenders: list[str] = []
        for rule in repo_sscp_pack.get("rules", []):  # type: ignore[union-attr]
            for field in ("paraphrase", "exact_excerpt", "notes"):
                text = (rule.get(field) or "").lower()
                for term in RULE_PACK_FORBIDDEN_VERDICT_LANGUAGE:
                    if term in text:
                        offenders.append(f"{rule.get('rule_id')!r}.{field}: {term!r}")
        assert not offenders, f"Forbidden verdict language in rule pack: {offenders}"


def _make_test_rule(
    *,
    rule_id: str = "test.rule.x",
    source_id: str | None = None,
    automation_readiness: str = "deterministic",
    implementation_status: str = "spec_only",
    modal_strength: str = "required",
    finding_family: str | None = "ECO-COMPL",
    source_hash: str | None = None,
    exact_excerpt: str | None = None,
) -> dict[str, object]:
    """Build a minimally valid rule candidate, overridden by kwargs.

    Defaults reference the first not_uploaded source from the repo inventory
    (no source_hash, no excerpt) so the base rule passes V-R7. Phase 6C
    flipped sources[0] to uploaded_local; look up by ingestion_status
    rather than positional index so this helper stays correct across
    inventory state changes.
    """
    if source_id is None:
        inventory = _load(INVENTORY_PATH)
        source_id = next(
            s["source_id"]  # type: ignore[index]
            for s in inventory["sources"]  # type: ignore[union-attr,index]
            if s.get("ingestion_status") == "not_uploaded"  # type: ignore[union-attr]
        )
    return {
        "rule_id": rule_id,
        "source_id": source_id,
        "source_title": "Test source title",
        "source_version": "v1",
        "source_url_or_local_path": "https://example.org/test",
        "source_hash": source_hash,
        "document_family": "SSCP",
        "target_document_type": "SSCP",
        "exact_excerpt": exact_excerpt,
        "paraphrase": "Test paraphrase.",
        "modal_strength": modal_strength,
        "automation_readiness": automation_readiness,
        "finding_family": finding_family,
        "implementation_status": implementation_status,
        "RA_review_status": "unreviewed",
        "notes": None,
    }
