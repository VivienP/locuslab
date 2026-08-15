"""Reproducibility contract for the committed demo fixture seeder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from scripts.seed_demo_fixture import (
    FIXTURE_DIR,
    write_cer_docx,
    write_gspr_xlsx,
    write_minimal_pdf,
)


def test_seeded_ooxml_files_are_byte_stable_and_canonical(tmp_path: Path) -> None:
    first_docx = tmp_path / "first.docx"
    second_docx = tmp_path / "second.docx"
    first_xlsx = tmp_path / "first.xlsx"
    second_xlsx = tmp_path / "second.xlsx"

    write_cer_docx(first_docx)
    write_cer_docx(second_docx)
    write_gspr_xlsx(first_xlsx)
    write_gspr_xlsx(second_xlsx)

    assert first_docx.read_bytes() == second_docx.read_bytes()
    assert first_xlsx.read_bytes() == second_xlsx.read_bytes()
    for path in (first_docx, first_xlsx):
        with ZipFile(path) as archive:
            assert {entry.date_time for entry in archive.infolist()} == {
                (1980, 1, 1, 0, 0, 0)
            }


def test_committed_demo_binaries_match_canonical_seeder(tmp_path: Path) -> None:
    generated_docx = tmp_path / "CER.docx"
    generated_xlsx = tmp_path / "GSPR_mapping.xlsx"
    generated_pdf = tmp_path / "source-study.pdf"
    write_cer_docx(generated_docx)
    write_gspr_xlsx(generated_xlsx)
    write_minimal_pdf(generated_pdf)

    assert generated_docx.read_bytes() == (FIXTURE_DIR / "CER.docx").read_bytes()
    assert generated_xlsx.read_bytes() == (
        FIXTURE_DIR / "GSPR_mapping.xlsx"
    ).read_bytes()
    assert generated_pdf.read_bytes() == (
        FIXTURE_DIR / "bibliography" / "source-study.pdf"
    ).read_bytes()


def test_gold_metadata_pins_current_seed_script() -> None:
    repository_root = Path(__file__).resolve().parent.parent
    seed_script = repository_root / "scripts" / "seed_demo_fixture.py"
    gold_documents = json.loads(
        (repository_root / "fixtures" / "gold" / "demo_documents.json").read_text(
            encoding="utf-8"
        )
    )

    assert gold_documents["seed_script_sha256"] == hashlib.sha256(
        seed_script.read_bytes()
    ).hexdigest()
