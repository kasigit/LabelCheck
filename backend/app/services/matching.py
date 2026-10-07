"""Field comparison: fuzzy text, numeric ABV, and unit-aware net contents.

Every function here is pure (inputs -> outputs, no globals, no I/O) so the domain rules
are trivial to unit-test. Each rule in the `label-rules` skill maps to a branch here and
to at least one test in tests/test_matching.py.

The guiding principle from the skill: when a rule is ambiguous, prefer REVIEW over a
confident wrong answer. The tool flags; the agent decides.
"""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

from app.models import FieldStatus

# Thresholds (kept as named constants so tests and docs can reference them).
FUZZY_REVIEW_THRESHOLD = 85  # token ratio >= this but not exact -> REVIEW
LOW_OCR_CONFIDENCE = 0.80  # below this, a number read is only trustworthy enough for REVIEW
NET_CONTENTS_TOLERANCE = 0.01  # 1% tolerance absorbs fl-oz rounding


# --------------------------------------------------------------------------------------
# Text normalization + fuzzy text fields (brand, class/type, bottler, country)
# --------------------------------------------------------------------------------------
def normalize_text(value: str) -> str:
    """Normalize a string for comparison.

    Steps (per the skill): Unicode NFKC, casefold, curly -> straight quotes/apostrophes,
    collapse whitespace, strip leading/trailing punctuation. This is what makes
    "STONE'S THROW" and "Stone's Throw" compare equal.
    """
    text = unicodedata.normalize("NFKC", value)
    # Curly quotes/apostrophes -> straight.
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'}))
    text = text.casefold()
    # Treat common separators as spaces so "Distillery, Louisville, KY" tokenizes as three
    # words — this makes token-based comparison robust to how addresses are punctuated.
    text = re.sub(r"[,;/\\|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(".,;:!?-–—'\"()[]")
    return text


def match_text(
    expected: str,
    found: str | None,
    *,
    use_token_set: bool = False,
) -> tuple[FieldStatus, str]:
    """Compare a free-text field and return (status, plain-English reason).

    `use_token_set=True` is for the bottler address, where labels reorder/split lines, so
    token_set_ratio is more forgiving than token_sort_ratio.
    """
    if not found:
        return FieldStatus.NOT_FOUND, "Couldn't find this on the label."

    norm_expected = normalize_text(expected)
    norm_found = normalize_text(found)

    if norm_expected == norm_found:
        # Equal after normalization. Note if only capitalization/punctuation differed.
        if expected.strip() != found.strip():
            return FieldStatus.MATCH, "Matches (capitalization or punctuation differs only)."
        return FieldStatus.MATCH, "Matches."

    # Some OCR engines glue runs of all-caps text together ("OLDTOMDISTILLERY"). Comparing
    # with all spaces removed catches that so it isn't penalised as a spelling difference.
    exp_nospace, found_nospace = norm_expected.replace(" ", ""), norm_found.replace(" ", "")
    if exp_nospace == found_nospace:
        return FieldStatus.MATCH, "Matches (spacing differs only)."

    # For set-based fields (bottler address, country) the expected value is often a subset
    # of what's on the label — "Scotland" inside "Product of Scotland", or the address line
    # with an "Imported by" prefix. If the whole expected value appears contiguously in the
    # label text (ignoring spaces), that's a match.
    if use_token_set and exp_nospace and exp_nospace in found_nospace:
        return FieldStatus.MATCH, "Matches (found within the label text)."

    scorer = fuzz.token_set_ratio if use_token_set else fuzz.token_sort_ratio
    # Score on the spaced form and the spaces-removed form; the latter keeps a one-letter
    # difference on glued OCR text ("OLDTOMDISTILLARY" vs "Old Tom Distillery") a REVIEW
    # rather than a MISMATCH, instead of being dragged down by the tokenization mismatch.
    score = max(scorer(norm_expected, norm_found), fuzz.ratio(exp_nospace, found_nospace))

    # A perfect token score means the same words in a different order (common for
    # addresses split/reordered across label lines) — treat that as a match.
    if score >= 99.5:
        return FieldStatus.MATCH, "Matches (wording order or spacing differs only)."

    if score >= FUZZY_REVIEW_THRESHOLD:
        return (
            FieldStatus.REVIEW,
            f"Close match — check spelling: label says '{found}', application says '{expected}'.",
        )
    return (
        FieldStatus.MISMATCH,
        f"Label says '{found}', application says '{expected}'.",
    )


# --------------------------------------------------------------------------------------
# Alcohol content (ABV + optional proof)
# --------------------------------------------------------------------------------------
# Matches "45%", "45.0% ABV", "ALC 45% BY VOL", "ALC. 45% VOL", etc.
_ABV_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
# Matches "(90 Proof)", "90 PROOF".
_PROOF_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*proof", re.IGNORECASE)


def parse_alcohol(text: str) -> tuple[float | None, float | None]:
    """Extract (abv_percent, proof) from a string. Either may be None."""
    abv_match = _ABV_RE.search(text)
    proof_match = _PROOF_RE.search(text)
    abv = float(abv_match.group(1)) if abv_match else None
    proof = float(proof_match.group(1)) if proof_match else None
    return abv, proof


def match_alcohol(
    expected: str,
    found: str | None,
    *,
    found_confidence: float = 1.0,
) -> tuple[FieldStatus, str]:
    """Compare alcohol content numerically. ABV is a hard value — never fuzzed.

    Rules:
      - %ABV compared numerically (45% == 45.0%).
      - If proof is present on the label, proof must equal 2 x ABV, else MISMATCH.
      - Any numeric ABV difference -> MISMATCH.
      - If the number was read with low OCR confidence -> REVIEW.
    """
    if not found:
        return FieldStatus.NOT_FOUND, "Couldn't find the alcohol content on the label."

    exp_abv, _ = parse_alcohol(expected)
    found_abv, found_proof = parse_alcohol(found)

    if found_abv is None:
        return FieldStatus.NOT_FOUND, "Couldn't read an alcohol percentage on the label."
    if exp_abv is None:
        # The application value itself has no parseable percentage; defer to the agent.
        return (
            FieldStatus.REVIEW,
            f"Couldn't read a percentage in the application value '{expected}'.",
        )

    # Proof/ABV internal consistency on the label itself.
    if found_proof is not None and abs(found_proof - 2 * found_abv) > 0.1:
        return (
            FieldStatus.MISMATCH,
            f"Label is inconsistent: {found_abv:g}% should be {2 * found_abv:g} proof, "
            f"but it reads {found_proof:g} proof.",
        )

    if abs(found_abv - exp_abv) < 0.05:  # equal to within rounding
        if found_confidence < LOW_OCR_CONFIDENCE:
            return FieldStatus.REVIEW, "Number is hard to read on the image — please confirm."
        return FieldStatus.MATCH, f"Matches at {exp_abv:g}%."

    if found_confidence < LOW_OCR_CONFIDENCE:
        return FieldStatus.REVIEW, "Number is hard to read on the image — please confirm."
    return (
        FieldStatus.MISMATCH,
        f"Label says {found_abv:g}%, application says {exp_abv:g}%.",
    )


# --------------------------------------------------------------------------------------
# Net contents (value + unit, converted to mL)
# --------------------------------------------------------------------------------------
_ML_PER_UNIT = {
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "millilitre": 1.0,
    "cl": 10.0,
    "centiliter": 10.0,
    "l": 1000.0,
    "liter": 1000.0,
    "litre": 1000.0,
    "floz": 29.5735,  # US fluid ounce
    "f[l]oz": 29.5735,
}
# Capture number + unit, tolerating spaces/dots: "750 mL", "750ML", "75 cl",
# "1 L", "12 FL OZ", "25.4 fl. oz.".
_QTY_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(ml|cl|l|milliliters?|millilitres?|centiliters?|lit(?:er|re)s?|fl\.?\s*oz\.?)",
    re.IGNORECASE,
)


def parse_net_contents(text: str) -> float | None:
    """Parse the first quantity in `text` and return it in millilitres, or None."""
    match = _QTY_RE.search(text)
    if not match:
        return None
    value = float(match.group(1))
    unit = re.sub(r"[.\s]", "", match.group(2)).lower()  # "fl oz" -> "floz"
    factor = _ML_PER_UNIT.get(unit)
    return value * factor if factor is not None else None


def match_net_contents(expected: str, found: str | None) -> tuple[FieldStatus, str]:
    """Compare net contents by converting both sides to millilitres."""
    if not found:
        return FieldStatus.NOT_FOUND, "Couldn't find the net contents on the label."

    exp_ml = parse_net_contents(expected)
    found_ml = parse_net_contents(found)

    if found_ml is None:
        return FieldStatus.NOT_FOUND, f"Couldn't read a volume on the label (saw '{found}')."
    if exp_ml is None:
        return FieldStatus.REVIEW, f"Couldn't read a volume in the application value '{expected}'."

    # Relative difference, so 1 L vs 999 mL is within tolerance.
    rel_diff = abs(found_ml - exp_ml) / max(exp_ml, 1e-9)
    if rel_diff < 1e-6:
        return FieldStatus.MATCH, f"Matches ({found.strip()} = {expected.strip()})."
    if rel_diff <= NET_CONTENTS_TOLERANCE:
        return (
            FieldStatus.MATCH,
            f"Matches after unit conversion ({found.strip()} ≈ {expected.strip()}).",
        )
    return (
        FieldStatus.MISMATCH,
        f"Label says {found.strip()} (~{found_ml:g} mL), application says "
        f"{expected.strip()} (~{exp_ml:g} mL).",
    )
