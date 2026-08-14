"""SSCP guidance evaluator consumes the Markdown spine (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from locuslab.guidance.evaluate_sscp import (  # noqa: E402
    DETERMINISTIC_RULE_IDS,
    evaluate_sscp_rules,
)
from locuslab.guidance.excerpt_anchor import SourceAnchor, locate_excerpt  # noqa: E402
from locuslab.pipeline import verify_dossier  # noqa: E402

DEMO_DOSSIER = REPO_ROOT / "fixtures" / "demo_dossier"
SYNTHETIC_SSCP_DOSSIER = (
    REPO_ROOT / "tests" / "fixtures" / "sscp_synthetic" / "by_filename"
)
RULE_PACK_PATH = REPO_ROOT / "docs" / "rules" / "guidance" / "sscp" / "rule_pack.json"
MDCG_MD_PATH = REPO_ROOT / "docs" / "guidance" / "sources" / "mdcg" / "md_mdcg_2019_9_sscp_en.md"
MDCG_MD_AVAILABLE = MDCG_MD_PATH.is_file()


class TestExcerptAnchorUnit:
    def test_verbatim_match_returns_anchor(self) -> None:
        md = "<!-- page=1 -->\nLine A\nThe device must be present.\nLine C\n"
        anchor = locate_excerpt(
            excerpt="The device must be present.",
            md_text=md,
            md_path="fake.md",
        )
        assert anchor is not None
        assert isinstance(anchor, SourceAnchor)
        assert anchor.matched_via == "verbatim"
        assert anchor.page_anchor == 1
        assert anchor.line_number == 3

    def test_whitespace_normalised_match_finds_excerpt_across_line_breaks(self) -> None:
        # Excerpt is one line; MD has a mid-sentence line break.
        md = "<!-- page=5 -->\nThe device shall be presented,\nincluding its principles.\n"
        anchor = locate_excerpt(
            excerpt="The device shall be presented, including its principles.",
            md_text=md,
            md_path="fake.md",
        )
        assert anchor is not None
        assert anchor.matched_via == "whitespace_normalised"
        assert anchor.page_anchor == 5

    def test_footnote_marker_does_not_block_match(self) -> None:
        md = "Header\nthe NB's single\n52identification number\nFooter\n"
        anchor = locate_excerpt(
            excerpt="the NB's single identification number",
            md_text=md,
            md_path="fake.md",
        )
        assert anchor is not None

    def test_unknown_excerpt_returns_none(self) -> None:
        md = "<!-- page=1 -->\nNothing relevant here.\n"
        assert locate_excerpt(
            excerpt="A wholly unrelated regulatory clause about widgets",
            md_text=md,
            md_path="fake.md",
        ) is None

    def test_empty_inputs_return_none(self) -> None:
        assert locate_excerpt(excerpt="", md_text="abc", md_path="fake.md") is None
        assert locate_excerpt(excerpt="abc", md_text="", md_path="fake.md") is None

    def test_curly_apostrophe_normalised(self) -> None:
        md = "<!-- page=2 -->\nThe device’s purpose is described.\n"
        anchor = locate_excerpt(
            excerpt="The device's purpose is described.",  # ASCII apostrophe
            md_text=md,
            md_path="fake.md",
        )
        assert anchor is not None


@pytest.mark.skipif(not MDCG_MD_AVAILABLE, reason="MDCG MD not available")
class TestEvaluatorAttachesAnchorsToShippedRules:
    @pytest.fixture()
    def rule_pack(self) -> dict[str, object]:
        return json.loads(RULE_PACK_PATH.read_text(encoding="utf-8"))

    @pytest.fixture()
    def md_text_by_source_id(self) -> dict[str, tuple[str, str]]:
        return {
            "mdcg-sscp-public-guidance": (
                "docs/guidance/sources/mdcg/md_mdcg_2019_9_sscp_en.md",
                MDCG_MD_PATH.read_text(encoding="utf-8"),
            )
        }

    def test_four_approved_rules_all_get_anchors(
        self,
        rule_pack: dict[str, object],
        md_text_by_source_id: dict[str, tuple[str, str]],
    ) -> None:
        evals = evaluate_sscp_rules(
            rule_pack=rule_pack,
            spans=[],
            md_text_by_source_id=md_text_by_source_id,
        )
        rules_by_id = {r["rule_id"]: r for r in rule_pack["rules"]}  # type: ignore[union-attr,index]
        md_text = md_text_by_source_id["mdcg-sscp-public-guidance"][1]
        for rid in DETERMINISTIC_RULE_IDS:
            anchor = evals[rid]["source_anchor"]
            assert anchor is not None, f"{rid} missing source_anchor"
            assert anchor["page_anchor"] in (11, 12), (
                f"{rid} anchor landed on page {anchor['page_anchor']}, "
                "expected page 11 (section 1 / 1.9 metadata) or "
                "page 12 (section 2.1 intended_purpose / 3.1 device_description)"
            )
            # Phase 6E reviewer W-1: back-mapping must be byte-correct.
            # Verify the preview head (first 40 chars, whitespace + apostrophe
            # normalised) actually echoes the excerpt prefix, not some
            # unrelated clause that happens to live on the same page. The
            # MD renderer:0.2.0 applies smart_quotes_to_ascii so curly
            # apostrophes in the rule pack excerpt become ASCII in the
            # preview — normalise both sides for the comparison.
            excerpt = rules_by_id[rid]["exact_excerpt"]
            def _norm(s: str) -> str:
                return " ".join(s.replace("’", "'").replace("‘", "'").split())
            excerpt_head = _norm(excerpt[:40])
            preview = anchor["preview"]
            preview_head = _norm(preview[:160])
            assert excerpt_head in preview_head, (
                f"{rid}: preview head does not echo excerpt head. "
                f"excerpt_head={excerpt_head!r}; preview_head={preview_head!r}"
            )
            # Round-trip: the preview substring of the original md_text
            # must actually appear at the recorded char_offset.
            offset = anchor["char_offset"]
            assert md_text[offset : offset + 120] == preview[:120], (
                f"{rid}: preview at char_offset {offset} does not match md_text"
            )

    def test_pending_rules_do_not_get_anchors(
        self,
        rule_pack: dict[str, object],
        md_text_by_source_id: dict[str, tuple[str, str]],
    ) -> None:
        """RA_pending rules have exact_excerpt=null, so no anchor can be
        produced; the field must be present and None."""
        evals = evaluate_sscp_rules(
            rule_pack=rule_pack,
            spans=[],
            md_text_by_source_id=md_text_by_source_id,
        )
        for rid, ev in evals.items():
            if rid not in DETERMINISTIC_RULE_IDS:
                assert ev["source_anchor"] is None

    def test_evaluator_without_md_returns_none_anchors(
        self, rule_pack: dict[str, object]
    ) -> None:
        """When md_text_by_source_id is None, anchors are None — Phase 6D
        callers that have not been updated still work."""
        evals = evaluate_sscp_rules(rule_pack=rule_pack, spans=[])
        for ev in evals.values():
            assert ev["source_anchor"] is None


class TestPipelineEmitsAnchorsForSscpDossier:
    @pytest.fixture()
    def sscp_run(self, tmp_path: Path) -> Path:
        verify_dossier(dossier_dir=SYNTHETIC_SSCP_DOSSIER, output_dir=tmp_path)
        return tmp_path

    def test_guidance_review_carries_source_anchor_field(self, sscp_run: Path) -> None:
        data = json.loads(
            (sscp_run / "guidance_review.json").read_text(encoding="utf-8")
        )
        approved_items = [
            it for it in data["review_items"]
            if it["rule_id"] in DETERMINISTIC_RULE_IDS
        ]
        assert len(approved_items) == 4
        for it in approved_items:
            anchor = it.get("source_anchor")
            assert isinstance(anchor, dict), (
                f"{it['rule_id']} should carry a source_anchor dict; got {anchor!r}"
            )
            assert isinstance(anchor["page_anchor"], int)
            assert anchor["page_anchor"] in (11, 12)
            assert anchor["md_path"].endswith("md_mdcg_2019_9_sscp_en.md")
            assert anchor["matched_via"] in ("verbatim", "whitespace_normalised")

    def test_pending_items_carry_explicit_null_anchor(self, sscp_run: Path) -> None:
        data = json.loads(
            (sscp_run / "guidance_review.json").read_text(encoding="utf-8")
        )
        for it in data["review_items"]:
            if it["rule_id"] not in DETERMINISTIC_RULE_IDS:
                assert it["source_anchor"] is None

    def test_guidance_md_renders_anchor_section(self, sscp_run: Path) -> None:
        md = (sscp_run / "guidance_review.md").read_text(encoding="utf-8")
        assert "Source anchor (Phase 6E spine consumer)" in md
        assert "md_mdcg_2019_9_sscp_en.md" in md

    def test_findings_jsonl_unchanged_by_phase_6e(
        self, sscp_run: Path, tmp_path: Path
    ) -> None:
        """Phase 6E must not change findings.jsonl, AND must preserve the
        Phase 6D byte-equality on guidance_review.json across two runs.
        Phase 6E reviewer S-1: extend the existing test to also assert
        guidance_review.json byte-equality (Phase 6D already asserted
        this property; Phase 6E source_anchor dicts are serialised with
        sort_keys=True so should not break the contract)."""
        control = tmp_path / "control"
        verify_dossier(dossier_dir=SYNTHETIC_SSCP_DOSSIER, output_dir=control)
        assert (sscp_run / "findings.jsonl").read_bytes() == (
            control / "findings.jsonl"
        ).read_bytes()
        assert (sscp_run / "guidance_review.json").read_bytes() == (
            control / "guidance_review.json"
        ).read_bytes(), (
            "guidance_review.json must remain byte-equal across two runs "
            "on the same SSCP dossier (Phase 6D W-2 + Phase 6E S-1)"
        )


class TestDemoDossierUnchangedByPhase6E:
    def test_demo_dossier_emits_no_guidance(self, tmp_path: Path) -> None:
        result = verify_dossier(dossier_dir=DEMO_DOSSIER, output_dir=tmp_path)
        assert result.n_guidance_review_items is None, (
            "Non-SSCP dossier must skip guidance review (Phase 6D contract preserved)"
        )
