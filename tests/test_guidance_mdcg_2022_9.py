"""MDCG 2022-9 IVDR SSP Markdown derivation (offline)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

INVENTORY_PATH = REPO_ROOT / "docs" / "guidance" / "source_inventory.json"
MDCG_2022_9_PDF = REPO_ROOT / "docs" / "guidance" / "sources" / "mdcg" / "mdcg_2022-9_en.pdf"
MDCG_2022_9_MD = REPO_ROOT / "docs" / "guidance" / "sources" / "mdcg" / "mdcg_2022-9_en.md"
SOURCE_ID = "mdcg-2022-9-ivdr-ssp"


def _entry() -> dict[str, object]:
    inv = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    for src in inv["sources"]:
        if src["source_id"] == SOURCE_ID:
            return src  # type: ignore[no-any-return]
    raise AssertionError(f"source_id {SOURCE_ID} missing from inventory")


def test_inventory_entry_has_derived_md_fields() -> None:
    e = _entry()
    assert e["derived_md_path_optional"] == "docs/guidance/sources/mdcg/mdcg_2022-9_en.md"
    assert isinstance(e["derived_md_sha256_optional"], str)
    assert len(e["derived_md_sha256_optional"]) == 64
    assert "pdfplumber" in e["derived_md_parser"]
    assert e["derived_md_review_status"] == "machine_generated"
    assert e["cross_refs_present"] is False


def test_derived_md_file_exists() -> None:
    assert MDCG_2022_9_MD.is_file(), f"derived MD missing: {MDCG_2022_9_MD}"


def test_derived_md_sha256_matches_inventory() -> None:
    e = _entry()
    actual = hashlib.sha256(MDCG_2022_9_MD.read_bytes()).hexdigest()
    assert e["derived_md_sha256_optional"] == actual, (
        f"inventory derived_md_sha256_optional {e['derived_md_sha256_optional']!r} "
        f"does not match file {actual!r}"
    )


def test_version_date_corrected_to_rev1() -> None:
    """Phase 6E-prep-B fixes the inventory's stale 'May 2022' guess.
    The locally-pinned PDF title page reads 'MDCG 2022-9 / Rev.1' dated
    'April 2024'."""
    e = _entry()
    assert "April 2024" in str(e["version_date"]), (
        f"version_date should reflect MDCG 2022-9 Rev.1 publication "
        f"(April 2024); got {e['version_date']!r}"
    )


def test_loader_resolves_md_for_2022_9() -> None:
    """Phase 6E-prep-A sources_loader should now resolve a frontmatter
    for the IVDR SSP entry."""
    from locuslab.guidance.sources_loader import load_source_with_xrefs

    record = load_source_with_xrefs(SOURCE_ID)
    assert record.md_path is not None, "md_path should be resolved post Phase 6E-prep-B"
    assert record.frontmatter is not None
    assert record.frontmatter.source_id == SOURCE_ID
    assert record.frontmatter.derived_md_review_status == "machine_generated"
    # cross_refs_present is false, so the parsed list is empty.
    assert record.frontmatter.cross_refs == []


def test_validate_inventory_clean_after_extension() -> None:
    """V-S7..V-S10 must not surface any issue for the new MDCG 2022-9
    derived MD entry."""
    from locuslab.guidance import validate_inventory

    issues = validate_inventory(
        json.loads(INVENTORY_PATH.read_text(encoding="utf-8")),
        base_path=REPO_ROOT,
    )
    # Filter to just the 2022-9 entry's potential issues to be precise.
    relevant = [i for i in issues if SOURCE_ID in i or "2022-9" in i]
    assert relevant == [], f"unexpected V-S* issues on 2022-9 entry: {relevant}"
