# How to Verify LabelCheck

A step-by-step guide to confirming the app works, using the sample data in `samples/`. No
coding needed — everything is done in the browser.

**Before you start**
1. Start the app (either one):
   - Docker: `docker build -t labelcheck . && docker run -p 8000:8000 labelcheck`, then open **http://localhost:8000**
   - Or dev mode (backend + `npm run dev`), then open **http://localhost:5173**
2. The sample files are in the `samples/` folder:
   - `samples/labels/*.png` — the label images
   - `samples/applications.csv` — the application data for every label
   - `samples/images.zip` — all the images zipped (for the batch test)

**How to read a result:** every field shows a status — ✓ **Match** (green), ⚠ **Needs
review** (amber), ✗ **Mismatch** (red), ? **Not found** (grey). The **Overall** is the
worst status across all fields. The tool flags; the agent decides.

---

## Part 1 — Single image

Go to the **Check one label** tab. For each test below: choose the image from
`samples/labels/`, type the values exactly as shown, then click **Check label**.

> Leave a field blank where the table says *(leave blank)*.

### Test 1 — Everything correct (expect: ✓ Match)

Image: **`clean.png`**

| Field on screen | Value to type |
|---|---|
| Beverage type | Spirits |
| Brand name | `Old Tom Distillery` |
| Class / type | `Kentucky Straight Bourbon Whiskey` |
| Alcohol content | `45% Alc./Vol.` |
| Net contents | `750 mL` |
| Bottler / producer name & address | `Old Tom Distillery, Louisville, KY` |
| Country of origin | *(leave blank)* |

**Expected:** Overall **Match**. Every field green, including all three Government-Warning
sub-checks (wording / capitals / bold).

---

### Test 2 — Wrong alcohol content (expect: ✗ Mismatch)

Image: **`wrong_abv.png`** (the label prints 40%, the application says 45%)

| Field on screen | Value to type |
|---|---|
| Beverage type | Spirits |
| Brand name | `Old Tom Distillery` |
| Class / type | `Kentucky Straight Bourbon Whiskey` |
| Alcohol content | `45% Alc./Vol.` |
| Net contents | `750 mL` |
| Bottler / producer name & address | `Old Tom Distillery, Louisville, KY` |
| Country of origin | *(leave blank)* |

**Expected:** Overall **Mismatch**. **Alcohol content** is red with a reason like
"Label says 40%, application says 45%." Everything else matches.

---

### Test 3 — Different units, still correct (expect: ✓ Match)

Image: **`units.png`** (the label prints **75 cl**, the application says **750 mL**)

| Field on screen | Value to type |
|---|---|
| Beverage type | Spirits |
| Brand name | `Old Tom Distillery` |
| Class / type | `Kentucky Straight Bourbon Whiskey` |
| Alcohol content | `45% Alc./Vol.` |
| Net contents | `750 mL` |
| Bottler / producer name & address | `Old Tom Distillery, Louisville, KY` |
| Country of origin | *(leave blank)* |

**Expected:** Overall **Match**. **Net contents** matches — the app converts 75 cl to
750 mL before comparing.

---

### Test 4 — Government Warning not in capitals (expect: ✗ Mismatch)

Image: **`warning_titlecase.png`** (the label says "Government Warning:" in title case)

| Field on screen | Value to type |
|---|---|
| Beverage type | Spirits |
| Brand name | `Old Tom Distillery` |
| Class / type | `Kentucky Straight Bourbon Whiskey` |
| Alcohol content | `45% Alc./Vol.` |
| Net contents | `750 mL` |
| Bottler / producer name & address | `Old Tom Distillery, Louisville, KY` |
| Country of origin | *(leave blank)* |

**Expected:** Overall **Mismatch**. In the **Government Health Warning** section, the
**ALL CAPITALS prefix** sub-check is red ("Prefix must be all capitals; label shows
'Government Warning:'"). The wording and bold sub-checks still pass.

---

### Test 5 — Beer with no ABV on the label (expect: ✓ Match)

Image: **`beer_no_abv.png`** (beer doesn't require alcohol content; leave it blank)

| Field on screen | Value to type |
|---|---|
| Beverage type | Beer |
| Brand name | `River Bend Lager` |
| Class / type | `Craft Lager` |
| Alcohol content | *(leave blank)* |
| Net contents | `355 mL` |
| Bottler / producer name & address | `River Bend Brewing Co., Portland, OR` |
| Country of origin | *(leave blank)* |

**Expected:** Overall **Match**. **Alcohol content** shows **Not required** (grey) because
beer doesn't require it and you left it blank — not a failure.

---

### Test 6 — Imported wine with country of origin (expect: ✓ Match)

Image: **`import_wine.png`**

| Field on screen | Value to type |
|---|---|
| Beverage type | Wine |
| Brand name | `Chateau Mirage` |
| Class / type | `Bordeaux Red Wine` |
| Alcohol content | `13.5% Alc./Vol.` |
| Net contents | `750 mL` |
| Bottler / producer name & address | `Fine Wine Imports, Chicago, IL` |
| Country of origin | `France` |

**Expected:** Overall **Match**. **Country of origin** matches even though the label reads
"Product of France" (the app recognizes the country within the phrase).

---

### Test 7 — Brand misspelled by one letter (expect: ⚠ Needs review)

Image: **`misspelled.png`** (the label reads "OLD TOM DISTILLARY" — note the *a*)

| Field on screen | Value to type |
|---|---|
| Beverage type | Spirits |
| Brand name | `Old Tom Distillery` |
| Class / type | `Kentucky Straight Bourbon Whiskey` |
| Alcohol content | `45% Alc./Vol.` |
| Net contents | `750 mL` |
| Bottler / producer name & address | `Old Tom Distillery, Louisville, KY` |
| Country of origin | *(leave blank)* |

**Expected:** Overall **Needs review**. **Brand name** is amber ("Close match — check
spelling…"), so a one-letter difference is surfaced for the agent rather than silently
passed or hard-failed.

---

### Test 8 — Unreadable photo (expect: ? Not found, with a clear message)

Image: **`blurry.png`** (heavily blurred)

| Field on screen | Value to type |
|---|---|
| Beverage type | Spirits |
| Brand name | `Old Tom Distillery` |
| Class / type | `Kentucky Straight Bourbon Whiskey` |
| Alcohol content | `45% Alc./Vol.` |
| Net contents | `750 mL` |
| Bottler / producer name & address | `Old Tom Distillery, Louisville, KY` |
| Country of origin | *(leave blank)* |

**Expected:** A plain message — "We couldn't read this image clearly. Try a straight,
well-lit photo of the label." The app says it can't read the image instead of guessing.

### Also worth trying: bad upload (error handling)
On the **Check one label** tab, choose a non-image file (e.g. `samples/applications.csv`)
as the label and click **Check label**. You should get a plain-English error: *"This file
isn't an image. Upload a JPG or PNG."* — never a stack trace or error code.

---

## Part 2 — Batch

The batch flow checks many labels at once from one CSV and one ZIP of images.

Go to the **Check a batch** tab and:

1. **Applications file (CSV):** choose **`samples/applications.csv`**
2. **Label images (ZIP):** choose **`samples/images.zip`**
   - `samples/images.zip` already contains all 15 sample images. If you've regenerated the
     samples and need to rebuild it: `cd samples/labels && zip ../images.zip *.png`
3. Click **Check all labels**.

**What to expect:**
- A short validation summary (for this clean set, no problems — all 15 pair up).
- A progress bar filling in ("15 of 15 checked").
- A results table, one row per label, with an **Overall** status badge.

**Then verify the batch tools:**
- **Filter by status** — click **Mismatch**; you should see 5 rows:
  `wrong_abv.png`, `bad_proof.png`, `warning_titlecase.png`, `warning_reworded.png`,
  `warning_not_bold.png`. Click **Needs review** to see `misspelled.png`.
- **Open a row** — click **Open** on any row to drill into its full per-field result, then
  **← Back to all results**.
- **Download results (CSV)** — downloads every field result for every label.

**Expected overall distribution for the sample set (15 labels):**

| Overall status | Count | Labels |
|---|---|---|
| ✓ Match | 7 | clean, stones_throw, units, beer_no_abv, import_wine, angle, glare |
| ✗ Mismatch | 5 | wrong_abv, bad_proof, warning_titlecase, warning_reworded, warning_not_bold |
| ? Not found | 2 | blurry, warning_missing |
| ⚠ Needs review | 1 | misspelled |

### Batch error handling (optional)
Upload a CSV missing a column, or a ZIP whose images don't match the CSV rows, and the app
reports **all** the problems up front (e.g. "Image 'x.png' has no row in the CSV.") before
processing anything.

---

## What "passing" looks like

- Every single-image test above produces the **Expected** result.
- The batch run completes, the filter/open/download tools work, and the overall counts
  match the table (7 / 5 / 2 / 1).
- Each label comes back in well under 5 seconds (typically a fraction of a second).

The expected result for every sample is also recorded in `samples/expected.json`, which the
automated golden-sample tests check against (`cd backend && pytest`).
