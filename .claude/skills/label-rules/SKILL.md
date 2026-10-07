---
name: label-rules
description: TTB label verification domain rules for LabelCheck — required fields by beverage type, how each field is matched (fuzzy text, numeric ABV, net contents units), and the strict Government Warning check (exact wording, all caps, bold). Use when working on matching.py, warning.py, extract.py, beverage_rules.yaml, or any test of matching behavior.
---

# Label verification rules

These are the domain core of the app. When a rule here is ambiguous, choose the outcome that sends the
label to **REVIEW** rather than a confident wrong answer, and note the assumption in `docs/assumptions.md`.

## Fields and when they're required

| Field | Beer | Wine | Spirits |
|---|---|---|---|
| Brand name | ✓ | ✓ | ✓ |
| Class/type designation | ✓ | ✓ | ✓ |
| Alcohol content | optional* | optional* | ✓ |
| Net contents | ✓ | ✓ | ✓ |
| Bottler/producer name & address | ✓ | ✓ | ✓ |
| Country of origin | imports only | imports only | imports only |
| Government Health Warning | ✓ | ✓ | ✓ |

\*Exceptions exist for some beers and wines. For the prototype: if the application gives a value, check it;
if the application leaves it blank, mark `NOT_REQUIRED`. Encode this table in `rules/beverage_rules.yaml`.
Country of origin is required when the application provides it (treat a non-blank value as "this is an import").

## Text fields (brand name, class/type, bottler, country)

Normalize both sides before comparing: Unicode NFKC, casefold, curly → straight quotes/apostrophes,
collapse whitespace, strip leading/trailing punctuation.

| Condition | Status | Example reason |
|---|---|---|
| Normalized strings equal | `MATCH` | "Matches (capitalization differs only)." when the raw strings differ |
| RapidFuzz `token_sort_ratio` ≥ 85 | `REVIEW` | "Close match — check spelling: 'Stone Throw' vs 'Stone's Throw'." |
| Below 85 | `MISMATCH` | "Label says 'Old Tom Distilery', application says 'Old Tom Distillery'." |
| Not found on label | `NOT_FOUND` | "Couldn't find the brand name on the label." |

The canonical case from the interviews: label `STONE'S THROW` vs application `Stone's Throw` → **MATCH**.

For bottler name & address, compare with `token_set_ratio` (labels often split or reorder address lines).

## Alcohol content

- Parse percentage and optional proof: `45% Alc./Vol. (90 Proof)`, `ALC 45% BY VOL`, `45.0% ABV`.
- Compare numerically: `45%` == `45.0%` → `MATCH`.
- If proof is present, check proof == 2 × ABV. Inconsistent → `MISMATCH` with reason.
- Any numeric difference → `MISMATCH` (ABV is a hard value; don't fuzz it).
- If OCR confidence on the number is < 0.8 → `REVIEW` ("Number is hard to read on the image.").

## Net contents

- Parse value + unit: `750 mL`, `750ML`, `75 cl`, `1 L`, `12 FL OZ`, `25.4 fl. oz.`
- Convert to mL and compare. Exact after conversion → `MATCH`. Within 1% (rounding of fl oz) → `MATCH` with
  reason noting the conversion. Otherwise → `MISMATCH`.

## Government Health Warning (strict)

Reference text (27 CFR Part 16). Verify against ttb.gov before release and keep it in one constant:

```
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

Three independent sub-checks, each with its own status in `WarningResult`:

### 1. Wording (word-for-word)
- Locate the warning block by finding "GOVERNMENT WARNING" (case-insensitive) in OCR lines, then join the
  following lines.
- Normalize whitespace and line breaks only. Do **not** casefold or strip punctuation for this check.
- Exact match → `MATCH`.
- Character-level edit distance ≤ 3 **and** the differing tokens have low OCR confidence → `REVIEW`
  ("Small differences that may be image quality — check by eye.").
- Otherwise → `MISMATCH`, and report the first differing words.
- Missing entirely → `NOT_FOUND` (overall result is never `MATCH` without a warning).

### 2. Capitals
- The prefix must be exactly `GOVERNMENT WARNING:` in capitals.
- `Government Warning`, `GOVERNMENT Warning`, etc. → `MISMATCH`. This was a real rejection cited in interviews.
- Missing colon → `MISMATCH`.

### 3. Bold
- OCR can't detect weight. Use stroke width: binarize the prefix's bounding box and the body text's boxes,
  run `cv2.distanceTransform`, compare median stroke width.
- Ratio prefix/body ≥ 1.25 → `MATCH`; 1.05–1.25 → `REVIEW`; < 1.05 → `MISMATCH` ("'GOVERNMENT WARNING:' doesn't appear to be bold.").
- If boxes are too small to measure reliably (< 12px text height) → `REVIEW`.

### Extra flag (non-blocking)
- If the warning text height is much smaller than other text on the label (< 40% of the median line height),
  add a note: "Warning text is very small compared with the rest of the label." Status stays as computed.

## Overall status

Worst status wins: `MISMATCH` > `NOT_FOUND` > `REVIEW` > `MATCH`. `NOT_REQUIRED` is ignored.

## Every rule needs a test

Each row in the tables above maps to at least one pytest case in `tests/test_matching.py` or
`tests/test_warning.py`. When you add or change a rule, add the test first.
