"""graph.jsonl and audit_manifest.json tests (offline)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

DEMO_DOSSIER = Path(__file__).parent.parent / "fixtures" / "demo_dossier"

GRAPH_FAMILIES = (
    "audit_run",
    "document",
    "span",
    "claim",
    "citation",
    "source",
    "evidence_link",
    "finding",
)

PHASE_1_3_ARTIFACTS = (
    "claims.jsonl",
    "citations.jsonl",
    "sources.jsonl",
    "evidence_links.jsonl",
    "findings.jsonl",
    "findings.csv",
)

WALL_CLOCK_KEYS = frozenset(
    {"generated_at", "timestamp", "created_at", "completed_at", "started_at"}
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run verify_dossier once on the demo dossier and return the output dir."""
    from locuslab.pipeline import verify_dossier

    run_dir = tmp_path_factory.mktemp("phase4_demo_run")
    verify_dossier(DEMO_DOSSIER, run_dir)
    return run_dir


@pytest.fixture(scope="module")
def demo_graph_records(demo_run: Path) -> list[dict[str, object]]:
    return _read_jsonl(demo_run / "graph.jsonl")


@pytest.fixture(scope="module")
def demo_manifest(demo_run: Path) -> dict[str, object]:
    return json.loads((demo_run / "audit_manifest.json").read_text(encoding="utf-8"))


class TestArtifactsExist:
    def test_all_eight_artifacts_written(self, demo_run: Path) -> None:
        expected = PHASE_1_3_ARTIFACTS + ("graph.jsonl", "audit_manifest.json")
        for fname in expected:
            assert (demo_run / fname).exists(), f"Missing artifact: {fname}"


class TestGraphExportFamilies:
    def test_all_eight_families_present(
        self, demo_graph_records: list[dict[str, object]]
    ) -> None:
        observed = {rec["record_type"] for rec in demo_graph_records}
        for family in GRAPH_FAMILIES:
            assert family in observed, (
                f"Family {family!r} missing; observed {sorted(observed)}"
            )

    def test_every_record_has_envelope(
        self, demo_graph_records: list[dict[str, object]]
    ) -> None:
        for rec in demo_graph_records:
            assert "record_type" in rec
            assert "record_id" in rec
            assert rec["schema_version"] == "graph.v1"

    def test_audit_run_is_exactly_one_record(
        self, demo_graph_records: list[dict[str, object]]
    ) -> None:
        audit_runs = [r for r in demo_graph_records if r["record_type"] == "audit_run"]
        assert len(audit_runs) == 1
        rec = audit_runs[0]
        assert rec["record_id"].startswith("run_")  # type: ignore[union-attr]
        assert "dossier_path" in rec
        assert "artifact_counts" in rec
        assert "graph_records" in rec["artifact_counts"]  # type: ignore[operator]

    def test_record_families_are_in_canonical_order(
        self, demo_graph_records: list[dict[str, object]]
    ) -> None:
        seen_order: list[str] = []
        for rec in demo_graph_records:
            family = rec["record_type"]
            if not seen_order or seen_order[-1] != family:
                seen_order.append(family)  # type: ignore[arg-type]
        for fam in seen_order:
            assert fam in GRAPH_FAMILIES, f"Unknown family {fam!r}"
        ranks = [GRAPH_FAMILIES.index(f) for f in seen_order]
        assert ranks == sorted(ranks), (
            f"Families out of canonical order: {seen_order}"
        )

    def test_records_within_family_sorted_by_id(
        self, demo_graph_records: list[dict[str, object]]
    ) -> None:
        for family in GRAPH_FAMILIES:
            ids = [
                rec["record_id"]
                for rec in demo_graph_records
                if rec["record_type"] == family
            ]
            assert ids == sorted(ids), f"{family} records not sorted by record_id"


class TestGraphExportCompleteness:
    def test_every_input_object_appears_as_graph_record(
        self, demo_run: Path, demo_graph_records: list[dict[str, object]]
    ) -> None:
        claims_ids = {
            obj["claim_id"] for obj in _read_jsonl(demo_run / "claims.jsonl")
        }
        citations_ids = {
            obj["mention_id"] for obj in _read_jsonl(demo_run / "citations.jsonl")
        }
        sources_ids = {
            obj["source_id"] for obj in _read_jsonl(demo_run / "sources.jsonl")
        }
        links_ids = {
            obj["evidence_link_id"]
            for obj in _read_jsonl(demo_run / "evidence_links.jsonl")
        }
        findings_ids = {
            obj["eco_id"] for obj in _read_jsonl(demo_run / "findings.jsonl")
        }

        by_family: dict[str, set[object]] = {f: set() for f in GRAPH_FAMILIES}
        for rec in demo_graph_records:
            by_family[rec["record_type"]].add(rec["record_id"])  # type: ignore[index]

        assert by_family["claim"] == claims_ids
        assert by_family["citation"] == citations_ids
        assert by_family["source"] == sources_ids
        assert by_family["evidence_link"] == links_ids
        assert by_family["finding"] == findings_ids
        # documents + spans: at least the documents referenced by claims are present
        document_ids_from_claims = {
            obj["document_id"] for obj in _read_jsonl(demo_run / "claims.jsonl")
        }
        assert document_ids_from_claims.issubset(by_family["document"])
        span_ids_from_claims = {
            obj["span_id"] for obj in _read_jsonl(demo_run / "claims.jsonl")
        }
        assert span_ids_from_claims.issubset(by_family["span"])

    def test_missing_sources_retain_resolvable_gspr_origin_spans(
        self, demo_graph_records: list[dict[str, object]]
    ) -> None:
        graph_ids = {rec["record_id"] for rec in demo_graph_records}
        missing_sources = [
            rec
            for rec in demo_graph_records
            if rec["record_type"] == "source"
            and rec["availability_status"] == "missing_file"
        ]

        assert missing_sources
        for source in missing_sources:
            origin_span_ids = source["origin_span_ids"]
            assert origin_span_ids
            assert set(origin_span_ids).issubset(graph_ids)  # type: ignore[arg-type]


class TestFindingAffectedIdsResolve:
    def test_finding_affected_ids_resolve_to_graph_records_or_are_surfaced(
        self,
        demo_run: Path,
        demo_graph_records: list[dict[str, object]],
        demo_manifest: dict[str, object],
    ) -> None:
        graph_ids = {rec["record_id"] for rec in demo_graph_records}
        unresolved_in_manifest = set(demo_manifest["unresolved_affected_ids"])  # type: ignore[arg-type]

        findings = _read_jsonl(demo_run / "findings.jsonl")
        for f in findings:
            for aid in f["affected_object_ids"]:  # type: ignore[union-attr]
                assert aid in graph_ids or aid in unresolved_in_manifest, (
                    f"Affected id {aid!r} from finding {f['eco_id']!r} is "
                    f"neither in the graph nor in unresolved_affected_ids"
                )


class TestGraphExportDeterminism:
    def test_two_runs_produce_byte_equal_graph_jsonl(self, tmp_path: Path) -> None:
        from locuslab.pipeline import verify_dossier

        run_a = tmp_path / "run_a"
        run_b = tmp_path / "run_b"
        verify_dossier(DEMO_DOSSIER, run_a)
        verify_dossier(DEMO_DOSSIER, run_b)
        assert (run_a / "graph.jsonl").read_bytes() == (
            run_b / "graph.jsonl"
        ).read_bytes()


class TestManifestPresenceAndShape:
    def test_required_top_level_keys_present(
        self, demo_manifest: dict[str, object]
    ) -> None:
        required = {
            "manifest_schema_version",
            "run_id",
            "input_documents",
            "artifact_hashes",
            "artifact_counts",
            "extraction_methods",
            "checker_ids",
            "linking_methods",
            "unresolved_affected_ids",
            "known_limitations",
        }
        missing = required - demo_manifest.keys()
        assert not missing, f"Manifest missing required keys: {missing}"

    def test_schema_version_is_pinned(self, demo_manifest: dict[str, object]) -> None:
        assert demo_manifest["manifest_schema_version"] == "audit.v1"

    def test_input_documents_have_required_fields(
        self, demo_manifest: dict[str, object]
    ) -> None:
        for entry in demo_manifest["input_documents"]:  # type: ignore[union-attr]
            for key in (
                "document_id",
                "path",
                "kind",
                "sha256",
                "parser",
                "parse_warning_codes",
                "parse_warnings",
            ):
                assert key in entry, f"input_documents entry missing {key!r}"

    def test_structured_parser_warnings_are_preserved_across_outputs(
        self,
        demo_run: Path,
        demo_manifest: dict[str, object],
        demo_graph_records: list[dict[str, object]],
    ) -> None:
        report = json.loads((demo_run / "report.json").read_text(encoding="utf-8"))
        manifest_documents = {
            document["document_id"]: document
            for document in demo_manifest["input_documents"]  # type: ignore[union-attr]
        }
        report_documents = {
            document["document_id"]: document
            for document in report["input_documents"]
        }
        graph_documents = {
            record["document_id"]: record
            for record in demo_graph_records
            if record["record_type"] == "document"
        }

        warned = [
            document
            for document in manifest_documents.values()
            if document["parse_warnings"]
        ]
        assert warned, "Demo fixture should retain at least one parser diagnostic"
        for document in warned:
            document_id = document["document_id"]
            warnings = document["parse_warnings"]
            assert warnings == report_documents[document_id]["parse_warnings"]
            assert warnings == graph_documents[document_id]["parse_warnings"]
            assert set(warnings[0]) == {"code", "message", "path", "location"}

    def test_known_limitations_match_canonical_list(
        self, demo_manifest: dict[str, object]
    ) -> None:
        """Manifest's known_limitations must match the canonical KNOWN_LIMITATIONS."""
        from locuslab.audit import KNOWN_LIMITATIONS

        assert demo_manifest["known_limitations"] == list(KNOWN_LIMITATIONS)


class TestManifestHashesMatch:
    def test_artifact_hashes_match_file_bytes(
        self, demo_run: Path, demo_manifest: dict[str, object]
    ) -> None:
        hashes = demo_manifest["artifact_hashes"]
        for fname in PHASE_1_3_ARTIFACTS + (
            "graph.jsonl",
            "report.json",
            "findings.xlsx",
            "report.docx",
        ):
            assert fname in hashes, f"Missing hash for {fname}"  # type: ignore[operator]
            expected = _sha256_bytes((demo_run / fname).read_bytes())
            assert hashes[fname] == expected, (  # type: ignore[index]
                f"hash mismatch for {fname}: manifest={hashes[fname]!r} vs "  # type: ignore[index]
                f"file={expected!r}"
            )


class TestManifestCountsMatch:
    def test_counts_match_actual_artifacts(
        self,
        demo_run: Path,
        demo_manifest: dict[str, object],
        demo_graph_records: list[dict[str, object]],
    ) -> None:
        counts = demo_manifest["artifact_counts"]
        assert counts["claims"] == len(_read_jsonl(demo_run / "claims.jsonl"))  # type: ignore[index]
        assert counts["citations"] == len(_read_jsonl(demo_run / "citations.jsonl"))  # type: ignore[index]
        assert counts["sources"] == len(_read_jsonl(demo_run / "sources.jsonl"))  # type: ignore[index]
        assert counts["evidence_links"] == len(  # type: ignore[index]
            _read_jsonl(demo_run / "evidence_links.jsonl")
        )
        assert counts["findings"] == len(_read_jsonl(demo_run / "findings.jsonl"))  # type: ignore[index]
        assert counts["graph_records"] == len(demo_graph_records)  # type: ignore[index]
        # documents and spans counts derive from in-memory pipeline state;
        # cross-check against graph records of those families.
        document_records = [
            r for r in demo_graph_records if r["record_type"] == "document"
        ]
        span_records = [r for r in demo_graph_records if r["record_type"] == "span"]
        assert counts["documents"] == len(document_records)  # type: ignore[index]
        assert counts["spans"] == len(span_records)  # type: ignore[index]


class TestManifestObservedMethods:
    def test_extraction_methods_match_claims(
        self, demo_run: Path, demo_manifest: dict[str, object]
    ) -> None:
        observed = sorted(
            {obj["extraction_method"] for obj in _read_jsonl(demo_run / "claims.jsonl")}
        )
        assert demo_manifest["extraction_methods"] == observed

    def test_checker_ids_match_findings(
        self, demo_run: Path, demo_manifest: dict[str, object]
    ) -> None:
        observed = sorted(
            {obj["checker_id"] for obj in _read_jsonl(demo_run / "findings.jsonl")}
        )
        assert demo_manifest["checker_ids"] == observed

    def test_linking_methods_match_evidence_links(
        self, demo_run: Path, demo_manifest: dict[str, object]
    ) -> None:
        observed = sorted(
            {
                obj["linking_method"]
                for obj in _read_jsonl(demo_run / "evidence_links.jsonl")
            }
        )
        assert demo_manifest["linking_methods"] == observed


class TestManifestExcludesSelfHash:
    def test_audit_manifest_not_in_artifact_hashes(
        self, demo_manifest: dict[str, object]
    ) -> None:
        hashes = demo_manifest["artifact_hashes"]
        assert "audit_manifest.json" not in hashes  # type: ignore[operator]


class TestManifestDeterminism:
    def test_two_runs_produce_byte_equal_manifest(self, tmp_path: Path) -> None:
        from locuslab.pipeline import verify_dossier

        run_a = tmp_path / "run_a"
        run_b = tmp_path / "run_b"
        verify_dossier(DEMO_DOSSIER, run_a)
        verify_dossier(DEMO_DOSSIER, run_b)
        assert (run_a / "audit_manifest.json").read_bytes() == (
            run_b / "audit_manifest.json"
        ).read_bytes()


class TestRunIdStability:
    def test_run_id_stable_across_runs(self, tmp_path: Path) -> None:
        from locuslab.pipeline import verify_dossier

        run_a = tmp_path / "run_a"
        run_b = tmp_path / "run_b"
        verify_dossier(DEMO_DOSSIER, run_a)
        verify_dossier(DEMO_DOSSIER, run_b)
        manifest_a = json.loads(
            (run_a / "audit_manifest.json").read_text(encoding="utf-8")
        )
        manifest_b = json.loads(
            (run_b / "audit_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest_a["run_id"] == manifest_b["run_id"]
        assert manifest_a["run_id"].startswith("run_")

    def test_run_id_appears_in_graph_audit_run_record(
        self,
        demo_graph_records: list[dict[str, object]],
        demo_manifest: dict[str, object],
    ) -> None:
        audit_runs = [r for r in demo_graph_records if r["record_type"] == "audit_run"]
        assert len(audit_runs) == 1
        assert audit_runs[0]["record_id"] == demo_manifest["run_id"]


class TestNoWallClockInGraph:
    def test_graph_has_no_wall_clock_keys(
        self, demo_graph_records: list[dict[str, object]]
    ) -> None:
        for rec in demo_graph_records:
            offending = WALL_CLOCK_KEYS & rec.keys()
            assert not offending, (
                f"Record {rec.get('record_id')!r} contains wall-clock key(s): "
                f"{sorted(offending)}"
            )

    def test_manifest_has_no_wall_clock_keys(
        self, demo_manifest: dict[str, object]
    ) -> None:
        offending = WALL_CLOCK_KEYS & demo_manifest.keys()
        assert not offending, (
            f"Manifest contains wall-clock key(s): {sorted(offending)}"
        )


class TestVerifyResultExposesGraphCount:
    def test_verify_result_carries_n_graph_records(self, tmp_path: Path) -> None:
        from locuslab.pipeline import verify_dossier

        run_dir = tmp_path / "vr_run"
        result = verify_dossier(DEMO_DOSSIER, run_dir)
        graph_records = _read_jsonl(run_dir / "graph.jsonl")
        assert result.n_graph_records == len(graph_records)  # type: ignore[attr-defined]


def _make_finding(eco_id: str, affected: tuple[str, ...]):  # type: ignore[no-untyped-def]
    """Minimal Finding fixture for closure unit tests (offline, no I/O)."""
    from locuslab.models import AdjudicationState, Finding, FindingSeverity

    return Finding(
        eco_id=eco_id,
        severity=FindingSeverity.MAJOR,
        checker_id="checker.test:v1",
        finding_type="test_finding",
        affected_object_ids=affected,
        evidence="test evidence",
        remediation_hint="test remediation",
        adjudication_state=AdjudicationState.PENDING,
    )


class TestClosureFunctions:
    """Direct unit tests for graph closure helpers (no pipeline call)."""

    def test_collect_record_ids_returns_all_record_ids(self) -> None:
        from locuslab.graph import collect_record_ids

        records: list[dict[str, object]] = [
            {"record_type": "document", "record_id": "doc_aaa"},
            {"record_type": "span", "record_id": "span_bbb"},
            {"record_type": "claim", "record_id": "claim_ccc"},
        ]
        assert collect_record_ids(records) == {"doc_aaa", "span_bbb", "claim_ccc"}

    def test_collect_record_ids_handles_empty_input(self) -> None:
        from locuslab.graph import collect_record_ids

        assert collect_record_ids([]) == set()

    def test_compute_unresolved_empty_when_no_findings(self) -> None:
        from locuslab.graph import compute_unresolved_affected_ids

        graph_ids = {"doc_aaa", "span_bbb"}
        assert compute_unresolved_affected_ids([], graph_ids) == []

    def test_compute_unresolved_empty_when_all_resolved(self) -> None:
        from locuslab.graph import compute_unresolved_affected_ids

        graph_ids = {"doc_aaa", "span_bbb", "claim_ccc"}
        findings = [
            _make_finding("ECO-T-00000001", ("doc_aaa", "claim_ccc")),
            _make_finding("ECO-T-00000002", ("span_bbb",)),
        ]
        assert compute_unresolved_affected_ids(findings, graph_ids) == []

    def test_compute_unresolved_surfaces_orphan_ids_sorted(self) -> None:
        from locuslab.graph import compute_unresolved_affected_ids

        graph_ids = {"doc_aaa", "span_bbb"}
        findings = [
            _make_finding("ECO-T-00000001", ("doc_aaa", "ghost_zzz")),
            _make_finding("ECO-T-00000002", ("orphan_yyy", "span_bbb")),
        ]
        assert compute_unresolved_affected_ids(findings, graph_ids) == [
            "ghost_zzz",
            "orphan_yyy",
        ]
