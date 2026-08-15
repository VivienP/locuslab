"""Command-line entry point for LocusLab."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from locuslab.ingest import DossierLoadError
from locuslab.pipeline import OutputDirectoryError, verify_dossier


def build_parser() -> argparse.ArgumentParser:
    """Build the LocusLab CLI parser."""
    parser = argparse.ArgumentParser(
        prog="locus",
        description="Run local LocusLab Evidence Trace Audit workflows.",
    )
    subparsers = parser.add_subparsers(dest="command")

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify a local MDR/IVDR dossier and write a run directory.",
    )
    verify_parser.add_argument("dossier_dir", type=Path, help="Local dossier directory.")
    verify_parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output run directory.",
    )

    return parser


def _run_verify(dossier_dir: Path, output_dir: Path) -> int:
    if not dossier_dir.exists():
        sys.stderr.write(f"Dossier directory not found: {dossier_dir}\n")
        return 2

    try:
        result = verify_dossier(dossier_dir=dossier_dir, output_dir=output_dir)
    except OutputDirectoryError as exc:
        sys.stderr.write(f"Output directory could not be prepared: {exc}\n")
        return 2
    except DossierLoadError as exc:
        sys.stderr.write(f"Dossier could not be loaded: {exc}\n")
        return 2

    guidance_suffix = (
        ", guidance review written"
        if result.n_guidance_review_items is not None
        else ""
    )
    sys.stdout.write(
        f"Verified: {result.n_claims} claims, {result.n_citations} citations, "
        f"{result.n_sources} sources, {result.n_links} evidence links, "
        f"{result.n_findings} findings, {result.n_graph_records} graph records, "
        f"report package written{guidance_suffix}. Output: {result.output_dir}\n"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    if args.command == "verify":
        return _run_verify(args.dossier_dir, args.out)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
