"""Phase 6C helper - extract text from a local guidance PDF (offline).

Reads a PDF from `--in` using pypdf (already in pyproject) and writes a
plain-text page-by-page dump to `--out` (default: stdout). The output is a
review artifact for an RA reviewer who wants to confirm a verbatim excerpt
against the canonical source; it is NOT used by `locus verify` or by any
rule-pack consumer.

Usage:
    python scripts/extract_guidance_pdf_text.py \\
        --in docs/guidance/sources/mdcg/md_mdcg_2019_9_sscp_en.pdf \\
        --out tmp/mdcg_2019_9_text.txt

Exit codes:
    0  success
    2  missing input file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make src/ importable so a future helper that imports locuslab works.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pypdf import PdfReader  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract_guidance_pdf_text",
        description=(
            "Extract text from a local guidance PDF, page by page. "
            "Output is a review artifact, never fed to a runtime LLM."
        ),
    )
    parser.add_argument(
        "--in",
        dest="input_path",
        type=Path,
        required=True,
        help="Path to the input PDF.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output text file (default: stdout).",
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help=(
            "Optional 1-indexed page filter, comma or hyphen-range syntax. "
            "Examples: '11', '11,12', '11-15', '1,3-5,12'. Default: all pages."
        ),
    )
    return parser


def parse_pages_spec(spec: str, total_pages: int) -> list[int]:
    """Parse '1,3-5,12' into a sorted, deduplicated 1-indexed page list.

    Out-of-range pages are silently dropped; an empty spec is rejected.
    """
    selected: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            for pg in range(start, end + 1):
                if 1 <= pg <= total_pages:
                    selected.add(pg)
        else:
            pg = int(part)
            if 1 <= pg <= total_pages:
                selected.add(pg)
    return sorted(selected)


def extract_pages(pdf_path: Path, page_filter: list[int] | None = None) -> list[tuple[int, str]]:
    """Return (page_number_1indexed, text) tuples. Filter optional."""
    reader = PdfReader(str(pdf_path))
    if page_filter is None:
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    return [
        (pg, reader.pages[pg - 1].extract_text() or "")
        for pg in page_filter
        if 1 <= pg <= len(reader.pages)
    ]


def render(pages: list[tuple[int, str]]) -> str:
    parts: list[str] = []
    for pg, text in pages:
        parts.append(f"===PAGE {pg}===")
        parts.append(text)
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.input_path.is_file():
        sys.stderr.write(f"Input PDF not found: {args.input_path}\n")
        return 2

    page_filter: list[int] | None = None
    if args.pages is not None:
        reader = PdfReader(str(args.input_path))
        page_filter = parse_pages_spec(args.pages, len(reader.pages))
        if not page_filter:
            sys.stderr.write(
                f"--pages {args.pages!r} resolved to no valid pages "
                f"(PDF has {len(reader.pages)} pages).\n"
            )
            return 2

    pages = extract_pages(args.input_path, page_filter=page_filter)
    output = render(pages)

    if args.out is None:
        sys.stdout.write(output)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        sys.stdout.write(
            f"Extracted {len(pages)} page(s) from {args.input_path} -> {args.out}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
