# Assumptions

Decisions made where the requirements left things open, or where a domain rule needed a
concrete interpretation. Each is something a reviewer should be able to challenge. Where a
decision favors caution, it does so by sending a label to **Needs review** rather than
guessing.

## Where the application data comes from
There is no COLA integration, so the "expected" values come from the user:
- **Single check:** a form the agent fills in.
- **Batch:** a CSV (`applications.csv`), one row per label, paired with a ZIP of images by
  filename. The CSV columns are `image_filename, beverage_type, brand_name, class_type,
  alcohol_content, net_contents, bottler_name_address, country_of_origin`.

## Government Warning wording
The reference statement is the 27 CFR Part 16 text, kept as a single constant in
`backend/app/services/warning.py`:

> GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink
> alcoholic beverages during pregnancy because of the risk of birth defects. (2)
> Consumption of alcoholic beverages impairs your ability to drive a car or operate
> machinery, and may cause health problems.

**Verify this against ttb.gov before any production use** and update the one constant if it
changes.

## How the warning wording is compared
A literal character-for-character comparison is unworkable in practice: OCR routinely
drops or garbles whole lines even on clean images. Instead we compare at the **word**
level, in two directions:
- A word on the label that does **not** appear in the standard statement (e.g. "reduces"
  where the standard says "impairs") is treated as a genuine rewording → **Mismatch**.
  If the warning was read with low OCR confidence, this is downgraded to **Needs review**.
- Words the standard has that the label is **missing** are tolerated up to ~45% (usually a
  dropped OCR line, not a wrong label). Beyond that → **Needs review**, not a confident
  match.

The all-capitals and bold checks are separate and stricter (below).

## Detecting bold (the warning prefix)
OCR can't report font weight, so we estimate **stroke width**: binarize the prefix's
bounding box and the body text's boxes, run a distance transform, and compare the median
stroke width. Ratio ≥ 1.25 → bold; 1.05–1.25 → review; < 1.05 → not bold. Text too small
to measure (< 12 px tall) → review. This is a heuristic; borderline cases are sent to
review for the agent to judge.

## Beverage-type rules
Encoded in `backend/app/rules/beverage_rules.yaml`:
- **Alcohol content** is required for spirits; optional for beer and wine. The prototype
  trusts the application: if a value is provided we check it, if it is blank we mark the
  field **Not required**. (Real TTB rules have finer exceptions for specific beers/wines.)
- **Country of origin** applies to imports only. We treat a non-blank application value as
  "this is an import" and then require/check it. A blank value → **Not required**.
- All other listed fields are required for every beverage type.

## Matching tolerances
- **Text fields** (brand, class/type, bottler, country): normalized (Unicode NFKC,
  casefold, straightened quotes, separators→spaces, collapsed whitespace) then compared.
  Equal after normalization → match. RapidFuzz token ratio ≥ 85 but not equal → review.
  Below 85 → mismatch. The canonical case `STONE'S THROW` vs `Stone's Throw` → **match**.
- **Bottler address** and **country** use `token_set_ratio`, so reordered address lines
  and prefixes like "Product of France" (vs application "France") still match.
- **Alcohol content** is parsed to a number and compared numerically (never fuzzed). If a
  proof is printed, it must equal 2 × ABV. Low-confidence number reads → review.
- **Net contents** is converted to millilitres and compared; within 1% (fl-oz rounding) →
  match. So `75 cl`, `750 mL`, and `750ML` all match `750 mL`.

## Unreadable images
If OCR returns no text (too blurry/dark), the app does **not** guess. It returns a clear
"We couldn't read this image clearly" message and an overall status of **Not found**.

## Test data
The sample labels in `samples/` are generated (drawn) by `scripts/generate_samples.py`
rather than photographed, so the set is reproducible offline and needs no image-generation
service. They cover clean labels, unit differences, wrong/inconsistent ABV, all the
warning failure modes, and imperfect images (angle, glare, blur). `expected.json` records
the expected outcome for each.
