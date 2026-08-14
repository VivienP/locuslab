"""SSCP guidance rule pack and review checklist tests (offline)."""

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

from locuslab.guidance import (  # noqa: E402
    OUTPUT_BOUNDARY,
    REVIEW_STATUS,
    GuidanceValidationError,
    build_checklist,
    validate_rule_pack,
)
from locuslab.report.language import REPORT_FORBIDDEN_LANGUAGE  # noqa: E402

INVENTORY_PATH = REPO_ROOT / "docs" / "guidance" / "source_inventory.json"
SSCP_RULE_PACK_PATH = REPO_ROOT / "docs" / "rules" / "guidance" / "sscp" / "rule_pack.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "render_guidance_review.py"

_RULE_PACK_MODAL_EXCEPTIONS = frozenset({"must ", "shall "})
RULE_PACK_FORBIDDEN_VERDICT_LANGUAGE = (
    REPORT_FORBIDDEN_LANGUAGE - _RULE_PACK_MODAL_EXCEPTIONS
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def repo_inventory() -> dict[str, object]:
    return _load(INVENTORY_PATH)


@pytest.fixture()
def sscp_pack() -> dict[str, object]:
    return _load(SSCP_RULE_PACK_PATH)


def _approved_rule_template(inventory: Mapping[str, object]) -> dict[str, object]:
    """Build a valid RA_approved-shaped rule for V-R10 positive testing.

    Uses an in-test 'uploaded_local' source so V-R7 does not fire on the
    excerpt+hash combination.
    """
    return {
        "rule_id": "test.r10.positive",
        "source_id": "test-uploaded-source",
        "source_title": "Test uploaded source",
        "source_version": "v1.0",
        "source_url_or_local_path": "docs/guidance/test.pdf",
        "source_hash": "a" * 64,
        "document_family": "SSCP",
        "target_document_type": "SSCP",
        "exact_excerpt": "The SSCP shall include the Basic UDI-DI.",
        "source_excerpt_pending": False,
        "paraphrase": "Test paraphrase: include Basic UDI-DI in SSCP.",
        "modal_strength": "required",
        "automation_readiness": "deterministic",
        "finding_family": "ECO-COMPL",
        "implementation_status": "spec_only",
        "RA_review_status": "RA_approved",
        "notes": None,
    }


def _make_inventory_with_uploaded_source(base: Mapping[str, object]) -> dict[str, object]:
    inv = copy.deepcopy(base)
    inv["sources"].append(  # type: ignore[union-attr,index]
        {
            "source_id": "test-uploaded-source",
            "title": "Test uploaded source",
            "issuer": "test",
            "version_date": "2026-01-01",
            "document_family": "SSCP",
            "source_type": "internal_checklist",
            "official_url": None,
            "local_path_optional": "docs/guidance/test.pdf",
            "sha256_optional": "a" * 64,
            "redistribution_note": "test fixture",
            "ingestion_status": "uploaded_local",
        }
    )
    return inv


class TestSscpRulePackShape:
    def test_pack_validates_against_repo_inventory(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        issues = validate_rule_pack(sscp_pack, repo_inventory)
        assert issues == [], f"SSCP pack should validate cleanly: {issues}"

    def test_pack_contains_between_8_and_12_rules(
        self, sscp_pack: dict[str, object]
    ) -> None:
        rules = sscp_pack.get("rules") or []
        assert isinstance(rules, list)
        assert 8 <= len(rules) <= 12, (
            f"Phase 6B brief mandates 8-12 candidates; got {len(rules)}"
        )

    def test_rule_ids_are_unique(self, sscp_pack: dict[str, object]) -> None:
        rules = sscp_pack.get("rules") or []
        ids = [r.get("rule_id") for r in rules]  # type: ignore[union-attr]
        assert len(ids) == len(set(ids)), f"Duplicate rule_ids: {ids}"

    def test_every_rule_references_a_known_source(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        known = {
            s["source_id"]  # type: ignore[index]
            for s in repo_inventory["sources"]  # type: ignore[union-attr,index]
        }
        for rule in sscp_pack["rules"]:  # type: ignore[union-attr,index]
            assert rule["source_id"] in known, (  # type: ignore[index]
                f"Rule {rule.get('rule_id')!r} references unknown source"
            )


class TestVRulesV10ToV12:
    def test_v_r10_ra_approved_without_excerpt_fails(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        inv = _make_inventory_with_uploaded_source(repo_inventory)
        rule = _approved_rule_template(inv)
        rule["exact_excerpt"] = None
        pack = copy.deepcopy(sscp_pack)
        pack["rules"].append(rule)  # type: ignore[union-attr,index]
        issues = validate_rule_pack(pack, inv)
        assert any("V-R10" in i and "exact_excerpt" in i for i in issues), (
            f"Expected V-R10 excerpt failure; got: {issues}"
        )

    def test_v_r10_ra_approved_without_source_hash_fails(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        inv = _make_inventory_with_uploaded_source(repo_inventory)
        rule = _approved_rule_template(inv)
        rule["source_hash"] = None
        pack = copy.deepcopy(sscp_pack)
        pack["rules"].append(rule)  # type: ignore[union-attr,index]
        issues = validate_rule_pack(pack, inv)
        assert any("V-R10" in i and "source_hash" in i for i in issues), (
            f"Expected V-R10 source_hash failure; got: {issues}"
        )

    def test_v_r10_ra_approved_well_formed_passes(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        inv = _make_inventory_with_uploaded_source(repo_inventory)
        rule = _approved_rule_template(inv)
        pack = copy.deepcopy(sscp_pack)
        pack["rules"].append(rule)  # type: ignore[union-attr,index]
        issues = validate_rule_pack(pack, inv)
        v_r10_issues = [i for i in issues if "V-R10" in i]
        assert v_r10_issues == [], (
            f"Well-formed RA_approved rule should not trip V-R10: {v_r10_issues}"
        )

    def test_v_r11_null_excerpt_without_pending_flag_fails(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        pack = copy.deepcopy(sscp_pack)
        rules = pack["rules"]  # type: ignore[index]
        assert rules, "SSCP pack must not be empty for this test"
        # Phase 6C made the first 4 rules RA_approved with non-null excerpts;
        # target the first rule that still has exact_excerpt=null so V-R11
        # has a legitimate target.
        idx = next(
            (i for i, r in enumerate(rules) if r.get("exact_excerpt") in (None, "")),  # type: ignore[union-attr]
            None,
        )
        assert idx is not None, "SSCP pack must contain at least one null-excerpt rule"
        rules[idx]["source_excerpt_pending"] = False  # type: ignore[index]
        issues = validate_rule_pack(pack, repo_inventory)
        assert any("V-R11" in i for i in issues), (
            f"Expected V-R11 to fire on null excerpt + missing pending flag: {issues}"
        )

    def test_v_r11_null_excerpt_with_pending_flag_passes(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        # Phase 6C: 4 rules are RA_approved with non-null excerpts (V-R11 not
        # applicable). The remaining 6 carry exact_excerpt=null and
        # source_excerpt_pending=true; these are the V-R11 positive cases.
        # The shipped pack as a whole must validate cleanly under V-R11.
        issues = validate_rule_pack(sscp_pack, repo_inventory)
        v_r11_issues = [i for i in issues if "V-R11" in i]
        assert v_r11_issues == [], (
            f"Shipped pack rules should not trip V-R11: {v_r11_issues}"
        )

    def test_v_r12_ra_approved_with_pending_flag_fails(
        self,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        inv = _make_inventory_with_uploaded_source(repo_inventory)
        rule = _approved_rule_template(inv)
        rule["source_excerpt_pending"] = True
        pack = copy.deepcopy(sscp_pack)
        pack["rules"].append(rule)  # type: ignore[union-attr,index]
        issues = validate_rule_pack(pack, inv)
        assert any("V-R12" in i for i in issues), (
            f"Expected V-R12 (RA_approved + pending) failure; got: {issues}"
        )


class TestRulePackProseLanguage:
    def test_no_forbidden_verdict_language_in_rule_pack_prose(
        self, sscp_pack: dict[str, object]
    ) -> None:
        offenders: list[str] = []
        rules = sscp_pack.get("rules") or []
        for rule in rules:  # type: ignore[union-attr]
            for field in ("paraphrase", "exact_excerpt", "notes"):
                text = (rule.get(field) or "").lower()
                for term in RULE_PACK_FORBIDDEN_VERDICT_LANGUAGE:
                    if term in text:
                        offenders.append(f"{rule.get('rule_id')!r}.{field}: {term!r}")
        assert not offenders, f"Forbidden verdict language in rule pack: {offenders}"


def _run_renderer(
    *,
    document_family: str,
    out_dir: Path,
    run_dir: Path | None = None,
    rule_pack: Path = SSCP_RULE_PACK_PATH,
    inventory: Path = INVENTORY_PATH,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(SCRIPT_PATH),
        "--document-family",
        document_family,
        "--rule-pack",
        str(rule_pack),
        "--inventory",
        str(inventory),
        "--out",
        str(out_dir),
    ]
    if run_dir is not None:
        args.extend(["--run-dir", str(run_dir)])
    return subprocess.run(args, capture_output=True, text=True, check=False)


class TestChecklistBuilder:
    def test_build_checklist_marks_every_item_needs_human_confirmation(
        self, sscp_pack: dict[str, object]
    ) -> None:
        checklist = build_checklist(rule_pack=sscp_pack, document_family="SSCP")
        items = checklist["review_items"]
        assert isinstance(items, list) and items
        for item in items:
            assert item["review_status"] == REVIEW_STATUS
            assert item["output_boundary"] == OUTPUT_BOUNDARY

    def test_build_checklist_carries_pack_metadata(
        self, sscp_pack: dict[str, object]
    ) -> None:
        checklist = build_checklist(rule_pack=sscp_pack, document_family="SSCP")
        assert checklist["pack_id"] == sscp_pack["pack_id"]
        assert checklist["pack_version"] == sscp_pack["pack_version"]
        assert checklist["document_family"] == "SSCP"
        assert checklist["n_review_items"] == len(sscp_pack["rules"])  # type: ignore[arg-type]


class TestRenderScript:
    @pytest.fixture()
    def fake_run_dir(self, tmp_path: Path) -> Path:
        run_dir = tmp_path / "fake_verify_run"
        run_dir.mkdir()
        # Match the Phase 5 report.json shape: counts live under
        # `artifact_counts`, not as top-level n_* keys. Fixture must mirror
        # the real schema or the renderer's silent-None bug returns.
        report = {
            "run_id": "deadbeefcafebabe",
            "artifact_counts": {
                "claims": 18,
                "citations": 5,
                "sources": 3,
                "evidence_links": 18,
                "findings": 8,
                "graph_records": 105,
                "documents": 4,
                "spans": 22,
            },
        }
        (run_dir / "report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        # Pre-existing finding file we will compare against post-call to
        # confirm the renderer never modifies the run dir.
        (run_dir / "findings.jsonl").write_text("{}\n", encoding="utf-8")
        return run_dir

    def test_renderer_writes_both_artifacts(self, tmp_path: Path) -> None:
        out = tmp_path / "checklist_out"
        result = _run_renderer(document_family="SSCP", out_dir=out)
        assert result.returncode == 0, (
            f"renderer failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert (out / "guidance_review.json").is_file()
        assert (out / "guidance_review.md").is_file()

    def test_renderer_items_carry_needs_human_confirmation(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "checklist_out"
        _run_renderer(document_family="SSCP", out_dir=out)
        data = json.loads((out / "guidance_review.json").read_text(encoding="utf-8"))
        items = data["review_items"]
        assert items
        for item in items:
            assert item["review_status"] == "needs_human_confirmation"

    def test_renderer_items_carry_output_boundary(self, tmp_path: Path) -> None:
        out = tmp_path / "checklist_out"
        _run_renderer(document_family="SSCP", out_dir=out)
        data = json.loads((out / "guidance_review.json").read_text(encoding="utf-8"))
        for item in data["review_items"]:
            assert item["output_boundary"] == "not_an_ECO_finding"

    def test_renderer_does_not_modify_run_dir(
        self, tmp_path: Path, fake_run_dir: Path
    ) -> None:
        before = {
            p.name: p.read_bytes() for p in fake_run_dir.iterdir() if p.is_file()
        }
        out = tmp_path / "checklist_out"
        _run_renderer(
            document_family="SSCP", out_dir=out, run_dir=fake_run_dir
        )
        # Nothing inside the run dir may have changed; no new file either.
        after_names = {p.name for p in fake_run_dir.iterdir() if p.is_file()}
        assert after_names == set(before.keys()), (
            "renderer added or removed a file inside the run directory"
        )
        for name, content in before.items():
            assert (fake_run_dir / name).read_bytes() == content, (
                f"renderer mutated {name} inside run directory"
            )
        # Specifically: findings.jsonl must remain byte-equal.
        assert (fake_run_dir / "findings.jsonl").read_bytes() == before[
            "findings.jsonl"
        ]

    def test_renderer_includes_run_reference_when_report_present(
        self, tmp_path: Path, fake_run_dir: Path
    ) -> None:
        out = tmp_path / "checklist_out"
        _run_renderer(
            document_family="SSCP", out_dir=out, run_dir=fake_run_dir
        )
        data = json.loads((out / "guidance_review.json").read_text(encoding="utf-8"))
        ref = data["run_reference"]
        assert ref is not None
        assert ref["run_id"] == "deadbeefcafebabe"
        assert ref["n_findings"] == 8
        md = (out / "guidance_review.md").read_text(encoding="utf-8")
        assert "deadbeefcafebabe" in md
        assert "Verify-run reference" in md

    def test_renderer_emits_no_reference_when_no_run_dir(self, tmp_path: Path) -> None:
        out = tmp_path / "checklist_out"
        _run_renderer(document_family="SSCP", out_dir=out)
        data = json.loads((out / "guidance_review.json").read_text(encoding="utf-8"))
        assert data["run_reference"] is None

    def test_renderer_exits_nonzero_on_non_sscp_family(self, tmp_path: Path) -> None:
        out = tmp_path / "checklist_out"
        result = _run_renderer(document_family="CER", out_dir=out)
        assert result.returncode != 0
        assert "SSCP" in (result.stdout + result.stderr)

    def test_renderer_markdown_contains_no_forbidden_verdict_language(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "checklist_out"
        _run_renderer(document_family="SSCP", out_dir=out)
        md = (out / "guidance_review.md").read_text(encoding="utf-8").lower()
        offenders = [
            term for term in RULE_PACK_FORBIDDEN_VERDICT_LANGUAGE if term in md
        ]
        assert not offenders, f"Forbidden verdict language in rendered MD: {offenders}"

    def test_renderer_json_contains_no_forbidden_verdict_language(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "checklist_out"
        _run_renderer(document_family="SSCP", out_dir=out)
        js = (out / "guidance_review.json").read_text(encoding="utf-8").lower()
        offenders = [
            term for term in RULE_PACK_FORBIDDEN_VERDICT_LANGUAGE if term in js
        ]
        assert not offenders, f"Forbidden verdict language in rendered JSON: {offenders}"

    def test_renderer_fails_gracefully_on_invalid_rule_pack(
        self, tmp_path: Path, sscp_pack: dict[str, object]
    ) -> None:
        bad_pack = copy.deepcopy(sscp_pack)
        # Drop a required field to force validate_rule_pack to fail.
        bad_pack["rules"][0].pop("rule_id")  # type: ignore[union-attr,index]
        bad_path = tmp_path / "bad_pack.json"
        bad_path.write_text(json.dumps(bad_pack), encoding="utf-8")
        out = tmp_path / "checklist_out"
        result = _run_renderer(
            document_family="SSCP",
            out_dir=out,
            rule_pack=bad_path,
        )
        assert result.returncode == 3, (
            f"expected exit 3 on validation failure; got {result.returncode}, "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_renderer_exits_2_on_missing_rule_pack_file(self, tmp_path: Path) -> None:
        """Phase 6B reviewer F-2: exit code 2 (missing input) was not
        previously covered. Closes the gap symmetrically with exits 3 and 4."""
        ghost_rule_pack = tmp_path / "does_not_exist.json"
        out = tmp_path / "checklist_out"
        result = _run_renderer(
            document_family="SSCP",
            out_dir=out,
            rule_pack=ghost_rule_pack,
        )
        assert result.returncode == 2, (
            f"expected exit 2 on missing rule pack file; got {result.returncode}, "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()

    def test_renderer_exits_2_on_missing_inventory_file(self, tmp_path: Path) -> None:
        ghost_inventory = tmp_path / "does_not_exist_inventory.json"
        out = tmp_path / "checklist_out"
        result = _run_renderer(
            document_family="SSCP",
            out_dir=out,
            inventory=ghost_inventory,
        )
        assert result.returncode == 2, (
            f"expected exit 2 on missing inventory file; got {result.returncode}, "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )


class TestChecklistBuilderRaisesOnInvalidPack:
    def test_write_outputs_raises_validation_error_on_bad_pack(
        self,
        tmp_path: Path,
        repo_inventory: dict[str, object],
        sscp_pack: dict[str, object],
    ) -> None:
        from locuslab.guidance import write_checklist_outputs

        bad = copy.deepcopy(sscp_pack)
        bad["rules"][0].pop("rule_id")  # type: ignore[union-attr,index]
        with pytest.raises(GuidanceValidationError):
            write_checklist_outputs(
                rule_pack=bad,
                inventory=repo_inventory,
                run_dir=None,
                document_family="SSCP",
                out_dir=tmp_path / "out",
            )
