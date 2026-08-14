"""Guidance Markdown source-spine tests.

Tests are ordered to match the spec §9 test contract:
  1 & 2  — golden + determinism (skip-gated on pdfplumber)
  3 & 4  — frontmatter roundtrip + malformed rejection (always-run)
  5-9    — validators V-S7..V-S10 + derived_md_review_status enum (always-run)
  10     — sources_loader SourceRecord with cross_refs (always-run)
  11     — backward compat: V-R13 still passes for the 4 RA_approved SSCP rules
  12     — reindex --check exits 0 clean / 1 on drift (always-run)
  13     — import extract_md succeeds without pdfplumber (always-run)
  14     — RuntimeError when pdfplumber absent (inverse-skip: only runs if absent)
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

INVENTORY_PATH = REPO_ROOT / "docs" / "guidance" / "source_inventory.json"
SSCP_RULE_PACK_PATH = REPO_ROOT / "docs" / "rules" / "guidance" / "sscp" / "rule_pack.json"
MDCG_SSCP_PDF = REPO_ROOT / "docs" / "guidance" / "sources" / "mdcg" / "md_mdcg_2019_9_sscp_en.pdf"
MDCG_SSCP_MD = REPO_ROOT / "docs" / "guidance" / "sources" / "mdcg" / "md_mdcg_2019_9_sscp_en.md"
GOLDEN_MD = REPO_ROOT / "tests" / "fixtures" / "extractor_golden" / "md_mdcg_2019_9_sscp_en.md"
ART32_MD = REPO_ROOT / "docs" / "guidance" / "sources" / "eurlex" / "article_32.md"
ART61_MD = REPO_ROOT / "docs" / "guidance" / "sources" / "eurlex" / "article_61.md"

has_pdfplumber = importlib.util.find_spec("pdfplumber") is not None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests 1 & 2: golden snapshot and determinism (skip-gated on pdfplumber)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not has_pdfplumber, reason="pdfplumber not installed")
def test_golden_mdcg_2019_9_sscp(request: pytest.FixtureRequest) -> None:
    """Test 1: extract_md output matches golden snapshot."""
    from locuslab.guidance.extract_md import extract_md  # type: ignore[import]

    if not MDCG_SSCP_PDF.is_file():
        pytest.skip("MDCG SSCP PDF not on disk")

    result = extract_md(MDCG_SSCP_PDF, parser_version="pdfplumber:test")

    if request.config.getoption("--update-goldens", default=False):
        GOLDEN_MD.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_MD.write_text(result.markdown_text, encoding="utf-8")
        return

    assert GOLDEN_MD.is_file(), f"Golden file missing: {GOLDEN_MD}; run with --update-goldens"
    golden = GOLDEN_MD.read_text(encoding="utf-8")
    assert result.markdown_text == golden, (
        "extract_md output does not match golden. "
        "If renderer changed intentionally, run: pytest --update-goldens"
    )


@pytest.mark.skipif(not has_pdfplumber, reason="pdfplumber not installed")
def test_determinism_extract_md() -> None:
    """Test 2: two extract_md calls on same PDF produce byte-equal output."""
    from locuslab.guidance.extract_md import extract_md  # type: ignore[import]

    if not MDCG_SSCP_PDF.is_file():
        pytest.skip("MDCG SSCP PDF not on disk")

    r1 = extract_md(MDCG_SSCP_PDF, parser_version="pdfplumber:test")
    r2 = extract_md(MDCG_SSCP_PDF, parser_version="pdfplumber:test")
    assert r1.markdown_text == r2.markdown_text, "extract_md is not deterministic"


# ---------------------------------------------------------------------------
# Tests 3 & 4: frontmatter parser (always-run)
# ---------------------------------------------------------------------------


def test_frontmatter_roundtrip() -> None:
    """Test 3: parse_frontmatter(dump_frontmatter(fm, body)) == (fm, body)."""
    from locuslab.guidance.frontmatter import (  # noqa: PLC0415
        CrossRef,
        Frontmatter,
        dump_frontmatter,
        parse_frontmatter,
    )

    fm = Frontmatter(
        source_id="eu-mdr-2017-745-art-32",
        document_family="SSCP",
        derived_from_source_id="eu-mdr-2017-745-full-text",
        derived_md_review_status="machine_generated",
        cross_refs=[
            CrossRef(
                source_id="eu-mdr-2017-745-art-61-annex-xiv",
                relation="sscp_uses_clinical_evaluation_summary",
                cited_at="Art. 32(2)(f)",
            ),
            CrossRef(
                source_id="mdcg-sscp-public-guidance",
                relation="interpretive_guidance",
                cited_at="SSCP content aspects (a)-(h)",
            ),
        ],
    )
    body = "# Article 32\n\nSome content here.\n"
    serialized = dump_frontmatter(fm, body)
    fm2, body2 = parse_frontmatter(serialized)
    assert fm2 == fm, f"Frontmatter mismatch: {fm2!r} != {fm!r}"
    assert body2 == body, f"Body mismatch: {body2!r} != {body!r}"


def test_frontmatter_rejects_malformed() -> None:
    """Test 4: parse_frontmatter raises ValueError on bad input."""
    from locuslab.guidance.frontmatter import parse_frontmatter

    # Missing opening delimiter
    with pytest.raises(ValueError, match="frontmatter"):
        parse_frontmatter("source_id: foo\n---\nbody")

    # Unknown relation value
    bad_relation = (
        "---\n"
        "source_id: eu-mdr-2017-745-art-32\n"
        "document_family: SSCP\n"
        "derived_from_source_id: eu-mdr-2017-745-full-text\n"
        "derived_md_review_status: machine_generated\n"
        "cross_refs:\n"
        "  - source_id: some-other-source\n"
        "    relation: INVALID_RELATION_VALUE\n"
        "    cited_at: somewhere\n"
        "---\n"
        "body text"
    )
    with pytest.raises(ValueError, match="relation"):
        parse_frontmatter(bad_relation)

    # Missing closing delimiter
    with pytest.raises(ValueError, match="frontmatter"):
        parse_frontmatter("---\nsource_id: foo\n")

    # Missing required field
    with pytest.raises(ValueError):
        parse_frontmatter("---\ndocument_family: SSCP\n---\nbody")


# ---------------------------------------------------------------------------
# Tests 5-9: validators V-S7..V-S10 (always-run)
# ---------------------------------------------------------------------------


_DEFAULT_MD_CONTENT = (
    "---\n"
    "source_id: eu-mdr-2017-745-art-32\n"
    "document_family: SSCP\n"
    "derived_from_source_id: eu-mdr-2017-745-full-text\n"
    "derived_md_review_status: machine_generated\n"
    "---\n"
    "body"
)


def _make_inventory_with_md(
    tmp_path: Path,
    *,
    md_content: str = _DEFAULT_MD_CONTENT,
    sha256_override: str | None = None,
    extra_sources: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], Path]:
    """Create a minimal inventory with a temporary .md file."""
    md_file = tmp_path / "article_32.md"
    # Write as bytes to avoid platform line-ending conversion; then compute sha256
    # from the exact bytes on disk so validator and test agree.
    md_bytes = md_content.encode("utf-8")
    md_file.write_bytes(md_bytes)
    actual_sha256 = hashlib.sha256(md_bytes).hexdigest()
    sha256 = sha256_override if sha256_override is not None else actual_sha256

    base_sources: list[dict[str, object]] = [
        {
            "source_id": "eu-mdr-2017-745-art-32",
            "title": "MDR Article 32",
            "issuer": "EU",
            "version_date": "2017-04-05",
            "document_family": "SSCP",
            "source_type": "MDR",
            "official_url": None,
            "local_path_optional": "docs/guidance/sources/eurlex/article_32.txt",
            "sha256_optional": "abc123",
            "redistribution_note": "public",
            "ingestion_status": "uploaded_local",
            "derived_md_path_optional": str(md_file),
            "derived_md_sha256_optional": sha256,
            "derived_md_parser": "manual",
            "derived_md_review_status": "machine_generated",
            "cross_refs_present": True,
            "derived_from_source_id": "eu-mdr-2017-745-full-text",
        },
        {
            "source_id": "eu-mdr-2017-745-full-text",
            "title": "MDR full text",
            "issuer": "EU",
            "version_date": "2017-04-05",
            "document_family": "OTHER",
            "source_type": "MDR",
            "official_url": None,
            "local_path_optional": None,
            "sha256_optional": None,
            "redistribution_note": "public",
            "ingestion_status": "not_uploaded",
        },
    ]
    if extra_sources:
        base_sources.extend(extra_sources)

    inventory: dict[str, object] = {"sources": base_sources}
    return inventory, md_file


def test_vs7_derived_md_file_exists_and_hash(tmp_path: Path) -> None:
    """Test 5: V-S7 fires when path missing or hash mismatches; clean on valid."""
    from locuslab.guidance.validate import validate_inventory

    # Clean state: no issues
    inventory, md_file = _make_inventory_with_md(tmp_path)
    issues = validate_inventory(inventory)
    assert not any("V-S7" in i for i in issues), f"Unexpected V-S7 issues on clean state: {issues}"

    # File missing
    missing_path = str(tmp_path / "nonexistent.md")
    inv_missing = copy.deepcopy(inventory)
    inv_missing["sources"][0]["derived_md_path_optional"] = missing_path  # type: ignore[index]
    issues = validate_inventory(inv_missing)
    assert any("V-S7" in i and "not found" in i for i in issues), (
        f"Expected V-S7 file-not-found: {issues}"
    )

    # Hash mismatch
    inv_bad_hash = copy.deepcopy(inventory)
    inv_bad_hash["sources"][0]["derived_md_sha256_optional"] = "deadbeef" * 8  # type: ignore[index]
    issues = validate_inventory(inv_bad_hash)
    assert any("V-S7" in i and "mismatch" in i for i in issues), (
        f"Expected V-S7 mismatch: {issues}"
    )


def test_vs8_crossref_source_resolution(tmp_path: Path) -> None:
    """Test 6: V-S8 fires when frontmatter cross_ref source_id not in inventory."""
    from locuslab.guidance.validate import validate_inventory

    md_content = (
        "---\n"
        "source_id: eu-mdr-2017-745-art-32\n"
        "document_family: SSCP\n"
        "derived_from_source_id: eu-mdr-2017-745-full-text\n"
        "derived_md_review_status: machine_generated\n"
        "cross_refs:\n"
        "  - source_id: nonexistent-source-id\n"
        "    relation: interpretive_guidance\n"
        "    cited_at: somewhere\n"
        "---\n"
        "body"
    )
    inventory, _ = _make_inventory_with_md(tmp_path, md_content=md_content)
    issues = validate_inventory(inventory)
    assert any("V-S8" in i and "nonexistent-source-id" in i for i in issues), (
        f"Expected V-S8 unknown cross_ref source_id: {issues}"
    )


def test_vs9_frontmatter_source_id_agreement(tmp_path: Path) -> None:
    """Test 7: V-S9 fires when frontmatter source_id != inventory source_id."""
    from locuslab.guidance.validate import validate_inventory

    md_content = (
        "---\n"
        "source_id: WRONG-SOURCE-ID\n"
        "document_family: SSCP\n"
        "derived_from_source_id: eu-mdr-2017-745-full-text\n"
        "derived_md_review_status: machine_generated\n"
        "---\n"
        "body"
    )
    inventory, _ = _make_inventory_with_md(tmp_path, md_content=md_content)
    issues = validate_inventory(inventory)
    assert any("V-S9" in i and "WRONG-SOURCE-ID" in i for i in issues), (
        f"Expected V-S9 source_id mismatch: {issues}"
    )


def test_vs10_derived_from_resolution(tmp_path: Path) -> None:
    """Test 8: V-S10 fires when frontmatter derived_from_source_id not in inventory."""
    from locuslab.guidance.validate import validate_inventory

    md_content = (
        "---\n"
        "source_id: eu-mdr-2017-745-art-32\n"
        "document_family: SSCP\n"
        "derived_from_source_id: nonexistent-parent-source\n"
        "derived_md_review_status: machine_generated\n"
        "---\n"
        "body"
    )
    inventory, _ = _make_inventory_with_md(tmp_path, md_content=md_content)
    issues = validate_inventory(inventory)
    assert any("V-S10" in i and "nonexistent-parent-source" in i for i in issues), (
        f"Expected V-S10 unresolved derived_from: {issues}"
    )


def test_derived_md_review_status_enum(tmp_path: Path) -> None:
    """Test 9: Only machine_generated, RA_reviewed, rejected accepted."""
    from locuslab.guidance.validate import validate_inventory

    # Valid values
    for valid_status in ("machine_generated", "RA_reviewed", "rejected"):
        md_content = (
            f"---\n"
            f"source_id: eu-mdr-2017-745-art-32\n"
            f"document_family: SSCP\n"
            f"derived_from_source_id: eu-mdr-2017-745-full-text\n"
            f"derived_md_review_status: {valid_status}\n"
            f"---\n"
            f"body"
        )
        inventory, _ = _make_inventory_with_md(tmp_path, md_content=md_content)
        inventory["sources"][0]["derived_md_review_status"] = valid_status  # type: ignore[index]
        issues = validate_inventory(inventory)
        assert not any("derived_md_review_status" in i for i in issues), (
            f"Unexpected issue for valid status {valid_status!r}: {issues}"
        )

    # Invalid value
    inv_bad, _ = _make_inventory_with_md(tmp_path)
    inv_bad["sources"][0]["derived_md_review_status"] = "invalid_status"  # type: ignore[index]
    issues = validate_inventory(inv_bad)
    assert any("derived_md_review_status" in i for i in issues), (
        f"Expected enum issue for invalid status: {issues}"
    )


# ---------------------------------------------------------------------------
# Test 10: sources loader (always-run)
# ---------------------------------------------------------------------------


def test_loader_load_source_with_xrefs() -> None:
    """Test 10: load_source_with_xrefs returns SourceRecord with cross_refs."""
    if not ART32_MD.is_file():
        pytest.skip("article_32.md not yet generated")

    from locuslab.guidance.sources_loader import load_source_with_xrefs

    record = load_source_with_xrefs("eu-mdr-2017-745-art-32")
    assert record.source_id == "eu-mdr-2017-745-art-32"
    assert record.md_path is not None
    assert record.md_path.is_file()
    assert record.frontmatter is not None
    # Should have cross_refs pointing to known sources
    assert len(record.frontmatter.cross_refs) > 0
    for xref in record.frontmatter.cross_refs:
        assert xref.source_id, "cross_ref source_id must be non-empty"
        assert xref.relation, "cross_ref relation must be non-empty"


# ---------------------------------------------------------------------------
# Test 11: backward compat V-R13 still passes for 4 RA_approved SSCP rules
# ---------------------------------------------------------------------------


EXPECTED_APPROVED_RULE_IDS = frozenset(
    {
        "guidance.sscp.required_section.intended_purpose",
        "guidance.sscp.required_section.device_description",
        "guidance.sscp.metadata.basic_udi_di_present",
        "guidance.sscp.metadata.notified_body_identifier",
    }
)


def test_backward_compat_sscp_rules_vr13() -> None:
    """Test 11: 4 RA_approved SSCP rules still pass V-R13 after inventory v2 bump."""
    from locuslab.guidance.validate import validate_rule_pack

    inventory = _load(INVENTORY_PATH)
    rule_pack = _load(SSCP_RULE_PACK_PATH)

    issues = validate_rule_pack(rule_pack, inventory)
    vr13_issues = [i for i in issues if "V-R13" in i]
    assert vr13_issues == [], (
        f"V-R13 fires on RA_approved rules after inventory v2 bump: {vr13_issues}"
    )

    # Also confirm the 4 approved rules are still present and RA_approved
    rules_by_id = {r["rule_id"]: r for r in rule_pack["rules"]}  # type: ignore[union-attr,index]
    for rid in EXPECTED_APPROVED_RULE_IDS:
        assert rid in rules_by_id, f"RA_approved rule {rid!r} missing from pack"
        assert rules_by_id[rid]["RA_review_status"] == "RA_approved", (  # type: ignore[index]
            f"{rid}: expected RA_approved"
        )


# ---------------------------------------------------------------------------
# Test 12: reindex CLI --check (always-run)
# ---------------------------------------------------------------------------


def test_reindex_check_clean_and_drift(tmp_path: Path) -> None:
    """Test 12: reindex --check exits 0 on clean state, 1 on sha256 drift."""
    import json as _json

    reindex_script = REPO_ROOT / "scripts" / "reindex_guidance_sources.py"
    if not reindex_script.is_file():
        pytest.fail(f"reindex script not found: {reindex_script}")

    # Build a minimal clean inventory with a real .md file
    md_content = (
        "---\n"
        "source_id: test-source\n"
        "document_family: SSCP\n"
        "derived_from_source_id: parent-source\n"
        "derived_md_review_status: machine_generated\n"
        "---\n"
        "body text"
    )
    md_file = tmp_path / "test.md"
    md_bytes = md_content.encode("utf-8")
    md_file.write_bytes(md_bytes)
    actual_sha256 = hashlib.sha256(md_bytes).hexdigest()

    inventory = {
        "_schema_version": "guidance.source_inventory.v2",
        "sources": [
            {
                "source_id": "test-source",
                "title": "Test",
                "issuer": "EU",
                "version_date": "2024-01-01",
                "document_family": "SSCP",
                "source_type": "MDR",
                "official_url": None,
                "local_path_optional": None,
                "sha256_optional": None,
                "redistribution_note": "public",
                "ingestion_status": "not_uploaded",
                "derived_md_path_optional": str(md_file),
                "derived_md_sha256_optional": actual_sha256,
                "derived_md_review_status": "machine_generated",
                "cross_refs_present": False,
            },
        ],
    }
    inv_path = tmp_path / "source_inventory.json"
    inv_path.write_text(_json.dumps(inventory), encoding="utf-8")

    # Clean state: should exit 0
    result = subprocess.run(
        [sys.executable, str(reindex_script), "--check", "--inventory", str(inv_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"reindex --check failed on clean state. "
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    # Introduce drift by changing the sha256 in inventory
    inventory["sources"][0]["derived_md_sha256_optional"] = "deadbeef" * 8  # type: ignore[index]
    inv_path.write_text(_json.dumps(inventory), encoding="utf-8")

    result_drift = subprocess.run(
        [sys.executable, str(reindex_script), "--check", "--inventory", str(inv_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result_drift.returncode == 1, (
        f"reindex --check should exit 1 on drift. "
        f"stdout: {result_drift.stdout!r}\nstderr: {result_drift.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Test 13: import extract_md succeeds without pdfplumber (always-run)
# ---------------------------------------------------------------------------


def test_optional_dep_import_succeeds() -> None:
    """Test 13: import locuslab.guidance.extract_md succeeds without pdfplumber."""
    import importlib

    # Force reimport (might be cached); just confirm no ImportError
    try:
        importlib.import_module("locuslab.guidance.extract_md")
    except ImportError as exc:
        pytest.fail(f"import locuslab.guidance.extract_md raised ImportError: {exc}")


# ---------------------------------------------------------------------------
# Test 14: RuntimeError when pdfplumber absent (inverse-skip)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(has_pdfplumber, reason="test requires pdfplumber absent")
def test_optional_dep_runtime_error(tmp_path: Path) -> None:
    """Test 14: extract_md() raises RuntimeError with install hint if pdfplumber absent."""
    from locuslab.guidance.extract_md import extract_md  # type: ignore[import]

    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
    with pytest.raises(RuntimeError, match=r"\.\[guidance-extract\]"):
        extract_md(dummy_pdf, parser_version="test")
