# DRAFT - REVIEW REQUIRED

## Doc Updates — FM-2 Pattern Fix

These comment/docstring changes belong in `src/locuslab/extract/patterns.py`.
Apply only after the regex change is reviewed and accepted.

---

### Line 74 — `CLASS_IIA`

Current comment (none):

```python
CLASS_IIA = re.compile(r"Class\s+II[ab]?\s+\w+\s+medical\s+device", re.IGNORECASE)
```

Proposed (after fix):

```python
# Matches MDR Class IIa / IIb device classification assertions.
# Tolerates zero or more adjective tokens (plain or hyphenated) between the class label
# and the mandatory phrase 'medical device'.
# Examples: 'Class IIb medical device', 'Class IIb active medical device',
#   'Class IIb non-invasive active medical device'.
# Does NOT match: 'Class IIc' (not a valid MDR class), bare 'Class IIb' without
#   'medical device', or 'Class action'.
# Regression: cardiopatch-x1-fm2 / span_7e7e95e42d14b4de (2026-05-22).
CLASS_IIA = re.compile(r"Class\s+II[ab]?\s+(?:[\w-]+\s+)*medical\s+device", re.IGNORECASE)
```

---

### Line 75 — `CLASS_III`

Current:

```python
CLASS_III = re.compile(r"Class\s+III\s+\w+\s+medical\s+device", re.IGNORECASE)
```

Proposed (symmetric fix):

```python
# Symmetric with CLASS_IIA: tolerates multi-word adjectival chains before 'medical device'.
CLASS_III = re.compile(r"Class\s+III\s+(?:[\w-]+\s+)*medical\s+device", re.IGNORECASE)
```

---

### Line 76 — `CLASS_I`

Current `CLASS_I` uses `\b.*?\bmedical\s+device` which is already flexible but
unbounded. Add a clarifying comment:

```python
# Broader than CLASS_IIA/CLASS_III: lazy wildcard between class label and 'medical device'.
# Review for false positive risk if corpus grows to include multi-paragraph spans.
CLASS_I = re.compile(r"Class\s+I\b.*?\bmedical\s+device", re.IGNORECASE)
```

No change to the pattern itself in this PR — flag for review separately.
