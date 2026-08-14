"""Phase 6E-prep-A — Restricted YAML frontmatter parser and writer.

No PyYAML dependency. Implements only the subset of YAML required for
guidance source .md frontmatter (spec §7):
  - String scalars (unquoted or double-quoted).
  - Lists of strings (block style with ``- `` prefix).
  - Lists of dicts with string fields (block style, ``- key: value``).
  - Dicts with string fields (block style, ``key: value``).
  - Boolean values for ``cross_refs_present`` only.

Not accepted: anchors, aliases, nested lists, flow style, multi-line
scalars, tags, or comments inside values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from locuslab.guidance.schema import CROSS_REF_RELATION_VALUES, DERIVED_MD_REVIEW_STATUS_VALUES

_FM_OPEN = "---"
_FM_CLOSE = "---"


@dataclass(frozen=True)
class CrossRef:
    """A single cross-reference from a source .md to another source."""

    source_id: str
    relation: str
    cited_at: str


@dataclass(frozen=True)
class Frontmatter:
    """Parsed frontmatter block from a guidance source .md file."""

    source_id: str
    document_family: str
    derived_from_source_id: str
    derived_md_review_status: str
    cross_refs: list[CrossRef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------


def _unquote(value: str) -> str:
    """Strip surrounding double-quotes if present; otherwise return as-is."""
    v = value.strip()
    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
        return v[1:-1]
    return v


def _parse_scalar(value: str) -> str | bool:
    """Parse a scalar YAML value: bool for cross_refs_present, else string."""
    v = value.strip()
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    return _unquote(v)


def _parse_block_lines(lines: list[str]) -> dict[str, object]:
    """Parse a flat list of ``key: value`` lines into a dict.

    Supports:
    - ``key: scalar_value``  (top-level scalars)
    - ``key:`` followed by ``  - ...`` list items (block sequences)

    Raises ``ValueError`` on unsupported syntax.
    """
    result: dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        # Top-level key: value  or  key:
        if ":" not in line:
            raise ValueError(f"frontmatter: expected 'key: value', got: {line!r}")
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not key:
            raise ValueError(f"frontmatter: empty key in line: {line!r}")
        if rest == "":
            # Possibly a block sequence follows
            seq: list[object] = []
            i += 1
            while i < len(lines) and lines[i].startswith(" ") or (
                i < len(lines) and lines[i].startswith("\t")
            ):
                inner = lines[i].strip()
                if inner.startswith("- "):
                    item_text = inner[2:].strip()
                    # Check if this dict item has sub-keys on next lines
                    item_dict: dict[str, str] = {}
                    first_key, _, first_val = item_text.partition(":")
                    first_key = first_key.strip()
                    first_val = first_val.strip()
                    if first_key and first_val:
                        item_dict[first_key] = _unquote(first_val)
                        i += 1
                        # Collect more dict entries for this list item (indented with '    ')
                        while i < len(lines):
                            sub = lines[i]
                            # Must be deeper indented than the list item marker
                            if not (sub.startswith("    ") or sub.startswith("\t\t")):
                                break
                            sub = sub.strip()
                            if sub.startswith("- "):
                                # New list item starts
                                break
                            if ":" in sub:
                                sk, _, sv = sub.partition(":")
                                item_dict[sk.strip()] = _unquote(sv.strip())
                                i += 1
                            else:
                                raise ValueError(
                                    f"frontmatter: unexpected line in block dict: {sub!r}"
                                )
                        seq.append(item_dict)
                    elif first_key:
                        # ``- key`` scalar in list
                        seq.append(_unquote(first_key))
                        i += 1
                    else:
                        seq.append(_unquote(item_text))
                        i += 1
                elif inner == "":
                    i += 1
                else:
                    break
            result[key] = seq
        else:
            result[key] = _parse_scalar(rest)
            i += 1
    return result


def _extract_fm_block(md_text: str) -> tuple[str, str]:
    """Split ``---\\n...\\n---\\n`` into (fm_content, body).

    Raises ``ValueError`` if delimiters are missing or malformed.
    """
    if not md_text.startswith("---"):
        raise ValueError(
            "frontmatter: document does not start with '---'; "
            "no YAML frontmatter block found"
        )
    # Find the closing ---
    rest = md_text[3:]
    # Skip immediately after opening ---  (newline or nothing)
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        raise ValueError("frontmatter: opening '---' must be on its own line")

    # Search for closing ---
    close_idx = -1
    for candidate in ("---\r\n", "---\n", "---"):
        idx = rest.find("\n" + candidate)
        if idx != -1:
            close_idx = idx
            # Determine how many chars the closing marker takes
            marker_len = len(candidate) + 1  # +1 for the leading \n
            fm_content = rest[:close_idx]
            after_close = rest[close_idx + marker_len :]
            return fm_content, after_close
    raise ValueError(
        "frontmatter: closing '---' not found; "
        "YAML frontmatter block must be terminated by '---'"
    )


def _cross_ref_from_dict(d: object) -> CrossRef:
    """Convert a parsed dict into a CrossRef; raise ValueError on bad data."""
    if not isinstance(d, dict):
        raise ValueError(f"frontmatter: cross_ref item must be a dict, got: {type(d).__name__}")
    source_id = d.get("source_id", "")
    relation = d.get("relation", "")
    cited_at = d.get("cited_at", "")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError(f"frontmatter: cross_ref missing 'source_id': {d!r}")
    if not isinstance(relation, str) or not relation:
        raise ValueError(f"frontmatter: cross_ref missing 'relation': {d!r}")
    if relation not in CROSS_REF_RELATION_VALUES:
        raise ValueError(
            f"frontmatter: cross_ref 'relation' {relation!r} is not in the allowed "
            f"relation values: {sorted(CROSS_REF_RELATION_VALUES)}"
        )
    if not isinstance(cited_at, str) or not cited_at:
        raise ValueError(f"frontmatter: cross_ref missing 'cited_at': {d!r}")
    return CrossRef(source_id=source_id, relation=relation, cited_at=cited_at)


def parse_frontmatter(md_text: str) -> tuple[Frontmatter, str]:
    """Parse the ``---`` delimited frontmatter block.

    Returns ``(frontmatter, body)`` where body is the Markdown after the
    closing ``---``. Raises ``ValueError`` on malformed input.
    """
    fm_content, body = _extract_fm_block(md_text)
    raw_lines = fm_content.splitlines()
    parsed = _parse_block_lines(raw_lines)

    source_id = parsed.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError(
            f"frontmatter: required field 'source_id' is missing or empty (got {source_id!r})"
        )
    document_family = parsed.get("document_family")
    if not isinstance(document_family, str) or not document_family:
        raise ValueError(
            f"frontmatter: required field 'document_family' is missing or empty "
            f"(got {document_family!r})"
        )
    derived_from = parsed.get("derived_from_source_id")
    if not isinstance(derived_from, str) or not derived_from:
        raise ValueError(
            f"frontmatter: required field 'derived_from_source_id' is missing or empty "
            f"(got {derived_from!r})"
        )
    review_status = parsed.get("derived_md_review_status")
    if not isinstance(review_status, str) or not review_status:
        raise ValueError(
            f"frontmatter: required field 'derived_md_review_status' is missing or empty "
            f"(got {review_status!r})"
        )
    if review_status not in DERIVED_MD_REVIEW_STATUS_VALUES:
        raise ValueError(
            f"frontmatter: 'derived_md_review_status' {review_status!r} not in "
            f"{sorted(DERIVED_MD_REVIEW_STATUS_VALUES)}"
        )

    raw_xrefs = parsed.get("cross_refs", [])
    if not isinstance(raw_xrefs, list):
        raise ValueError(
            f"frontmatter: 'cross_refs' must be a list, got {type(raw_xrefs).__name__}"
        )
    cross_refs = [_cross_ref_from_dict(item) for item in raw_xrefs]

    return (
        Frontmatter(
            source_id=source_id,
            document_family=document_family,
            derived_from_source_id=derived_from,
            derived_md_review_status=review_status,
            cross_refs=cross_refs,
        ),
        body,
    )


def dump_frontmatter(fm: Frontmatter, body: str) -> str:
    """Serialize frontmatter + body back to Markdown text.

    ``parse_frontmatter(dump_frontmatter(fm, body))`` is idempotent.
    """
    lines: list[str] = ["---"]
    lines.append(f"source_id: {fm.source_id}")
    lines.append(f"document_family: {fm.document_family}")
    lines.append(f"derived_from_source_id: {fm.derived_from_source_id}")
    lines.append(f"derived_md_review_status: {fm.derived_md_review_status}")
    if fm.cross_refs:
        lines.append("cross_refs:")
        for xref in fm.cross_refs:
            lines.append(f"  - source_id: {xref.source_id}")
            lines.append(f"    relation: {xref.relation}")
            lines.append(f"    cited_at: {xref.cited_at}")
    lines.append("---")
    lines.append("")
    result = "\n".join(lines)
    return result + body
