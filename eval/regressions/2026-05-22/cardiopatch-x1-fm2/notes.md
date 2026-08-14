# DRAFT - REVIEW REQUIRED

## FM-2 Regression Notes — Classification Pattern: Multi-Word Adjectival Chain

**Run:** 2026-05-22 / synthetic-cardiopatch-x1
**Failure category:** `claim_missed`
**Source pattern:** `src/locuslab/extract/patterns.py` lines 74-76

---

### Failure mode summary

The corpus contains three spans asserting Class IIb classification. The pipeline produced
zero classification claims across all three spans. The dogfood report identified this as
RC-1 and nominated it as the primary skillification target.

Live ingestion was run against the input directory to verify span IDs. The dogfood report
contained one ID error: `"Class IIb (synthetic assumption)"` is in `doc_2ec6b7b9fdadb3d4`
(CER), not `doc_921318243dfcba8b` (GSPR). The GSPR document contains no Class IIb text at
the span level. All three span IDs below are authoritative as of 2026-05-22.

---

### The three failing spans

**Span 1 — CER `span_7e7e95e42d14b4de` (`doc_2ec6b7b9fdadb3d4`)**

```
The CardioPatch X1 is classified as a Class IIb non-invasive active medical device
under MDR rule 10. The product is supplied sterile-free, single-patient use, and
communicates with a validated reader application.
```

Root cause: `CLASS_IIA = re.compile(r"Class\s+II[ab]?\s+\w+\s+medical\s+device", re.IGNORECASE)`.
The pattern requires exactly one `\w+` token between the class label and `medical device`.
The text has `non-invasive active` — two tokens, with a hyphen that terminates the first
`\w+` match (hyphens are not word characters). The regex engine matches `non` for `\w+`,
then looks for `\s+medical` but finds `-invasive`, fails, and backtracks to no match.

This is the primary actionable failure for the RC-1 fix. The proposed relaxation covers
it without introducing false positives on the tested candidates.

**Span 2 — CER `span_668416228dda6a2b` (`doc_2ec6b7b9fdadb3d4`)**

```
Class IIb (synthetic assumption)
```

Root cause: no `medical device` phrase in the span at all. All three CLASS_* patterns
require the phrase `medical device`. This span cannot be matched by any relaxation of the
existing patterns that still require `medical device`. Capturing bare `Class IIb` labels
requires a distinct pattern with higher false-positive risk and is not in scope for the
RC-1 fix. Documenting as a separate known gap.

**Span 3 — SSCP `span_da304b49e8591d07` (`doc_d66317f5eb97d245`)**

```
This synthetic document is inspired by SSCP structure but CardioPatch X1 is modelled
as a Class IIb non-implantable device. It is included only to test cross-document
consistency and public-facing claim control.
```

Root cause: the span uses `non-implantable device`, not `non-implantable medical device`.
The word `medical` is absent. The RC-1 fix (relaxing adjective count) does not reach this
span. Matching it requires making `medical` optional. That change carries additional
false-positive risk (e.g., `"Class IIb device"` in a non-regulatory context) and requires
a separate false-positive review before landing.

---

### Root cause — regex structure

Current pattern (line 74):

```python
CLASS_IIA = re.compile(r"Class\s+II[ab]?\s+\w+\s+medical\s+device", re.IGNORECASE)
```

The `\w+` component matches a single contiguous word character sequence. It cannot match:
- Hyphenated adjectives: `non-invasive` (hyphen breaks `\w+` after `non`)
- Two-token chains: `non-invasive active` (requires two `\w+` slots)

`CLASS_III` (line 75) and `CLASS_I` (line 76) are calibrated the same way and have the
same structural limitation, though `CLASS_I` uses a broader `.*?` between the label and
`medical device` and would match span 1 if `\b` anchoring allowed it — but live
verification shows it does not match any of the three spans.

---

### Proposed pattern relaxation for RC-1 (span 1 only)

**Scope:** span 1 only (`Class IIb non-invasive active medical device`). This change
covers multi-word adjectival chains between the class label and the mandatory phrase
`medical device`.

```python
# Proposed replacement for CLASS_IIA
# Tolerates zero or more hyphenated or plain word tokens before 'medical device'.
# Example matches: 'Class IIb medical device', 'Class IIb active medical device',
#   'Class IIb non-invasive active medical device'.
CLASS_IIA = re.compile(r"Class\s+II[ab]?\s+(?:[\w-]+\s+)*medical\s+device", re.IGNORECASE)
```

The same relaxation should be applied symmetrically to `CLASS_III`:

```python
CLASS_III = re.compile(r"Class\s+III\s+(?:[\w-]+\s+)*medical\s+device", re.IGNORECASE)
```

`CLASS_I` already uses `\b.*?\b` and is less affected by this specific failure, but should
be reviewed for consistency.

This is a DRAFT proposal only. Do not modify `patterns.py` until reviewed.

---

### False positive analysis for the proposed pattern

The proposed `(?:[\w-]+\s+)*` change was tested against the following candidates:

| Input | Match | Expected |
|---|---|---|
| `Class IIb non-invasive active medical device` | YES | YES |
| `Class IIb active medical device` | YES | YES |
| `Class IIb non-invasive medical device` | YES | YES |
| `Class IIa long-term implantable medical device` | YES | YES |
| `Class action lawsuit involving medical device` | NO | NO |
| `first class medical device service` | NO | NO |
| `Class IIc non-invasive active medical device` | NO | NO (IIc is not a valid MDR class) |

The pattern correctly excludes `Class IIc` because the character class `II[ab]?` only
allows `IIa`, `IIb`, and `II` (no letter suffix). `IIc` is not a valid MDR classification
and must not be matched.

### Patterns the new regex must NOT match

- `Class action` — no `II[ab]?` label
- `Class room` — no `II[ab]?` label
- `Class IIc medical device` — `IIc` is not a valid MDR class; `[ab]?` excludes `c`
- `Class IIb device` alone without `medical` — not reached by the current fix scope
- Extremely long adjective chains (unbounded `*` could match unexpectedly long pre-phrases;
  consider adding a length guard such as `{0,5}` if validation shows false positives in
  larger corpora)

---

### Out-of-scope items

- Span 2 (`Class IIb (synthetic assumption)`) — bare label without `medical device`; needs
  separate pattern design and false-positive review.
- Span 3 (`Class IIb non-implantable device`) — `medical` absent; requires optional
  `medical` with separate false-positive review.
- FM-1 (REF-NNN citation gap) — spec boundary; not a regression.
- FM-3 (GSPR DOCX completeness) — V1 XLSX-only boundary; not a regression.

---

### Dogfood report ID discrepancy

The dogfood report listed the GSPR document (`doc_921318243dfcba8b`) as the source of
`"Class IIb (synthetic assumption)"`. Live ingestion shows this text is a paragraph in the
CER (`doc_2ec6b7b9fdadb3d4`, `span_668416228dda6a2b`). The GSPR document
(`doc_921318243dfcba8b`, 153 spans) contains no Class IIb text. The span IDs in
`regression.jsonl` reflect the live-verified values.
