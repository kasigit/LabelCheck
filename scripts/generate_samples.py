#!/usr/bin/env python3
"""Generate the sample label set used by the golden-sample and performance tests.

Produces, under ``samples/``:
  - ``labels/*.png``        — rendered alcohol labels of varying content and quality
  - ``applications.csv``    — one application row per image (the batch upload format)
  - ``expected.json``       — the expected per-field outcome for each image

The images are *drawn* (not photographed) so the repo stays self-contained and the set is
reproducible with no external services — in keeping with the project's offline constraint.
Each case corresponds to a row in the `testing` skill's minimum-case table.

Run:  python scripts/generate_samples.py
Requires Pillow (``pip install pillow`` or the backend's ``dev`` extra).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = REPO_ROOT / "samples"
LABELS = SAMPLES / "labels"

# The canonical 27 CFR Part 16 statement (kept identical to backend/app/services/warning.py).
WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

# Candidate system fonts (macOS / Linux). First existing wins.
_REGULAR_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_BOLD_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _first_existing(paths: list[str]) -> str:
    for p in paths:
        if Path(p).exists():
            return p
    raise SystemExit(
        "No usable TrueType font found. Install DejaVu/Liberation fonts or run on macOS."
    )


REGULAR = _first_existing(_REGULAR_CANDIDATES)
BOLD = _first_existing(_BOLD_CANDIDATES)

W, H = 1000, 1500
BG = (250, 248, 240)
FG = (20, 20, 20)


@dataclass
class LabelSpec:
    """Ground truth for one rendered label and the application it's checked against."""

    filename: str
    beverage_type: str
    # What is DRAWN on the label image:
    brand_on_label: str
    class_on_label: str
    abv_on_label: str  # "" to omit
    net_on_label: str
    bottler_on_label: str
    country_on_label: str  # "" to omit
    warning_text: str  # "" to omit the warning entirely
    warning_prefix_bold: bool
    # What the APPLICATION says (the expected side the agent typed):
    app: dict[str, str]
    # Expected outcome:
    expected_overall: str
    expected_fields: dict[str, str]
    # Image-quality distortion to apply after rendering:
    distortion: str = ""  # "", "angle", "glare", "blur"
    note: str = field(default="")


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD if bold else REGULAR, size)


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int
) -> list[str]:
    """Greedy word wrap to fit max_w pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w and current:
            current = trial
        elif not current:
            current = word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _centered(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont) -> int:
    w = draw.textlength(text, font=font)
    draw.text(((W - w) / 2, y), text, font=font, fill=FG)
    ascent, descent = font.getmetrics()
    return y + ascent + descent + 10


def render(spec: LabelSpec) -> Image.Image:
    """Render a label image from its spec, then apply any quality distortion."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    y = 90
    draw.rectangle([40, 40, W - 40, H - 40], outline=(150, 130, 90), width=4)

    y = _centered(draw, y, spec.brand_on_label, _font(True, 74))
    y += 10
    for line in _wrap(draw, spec.class_on_label, _font(False, 40), W - 200):
        y = _centered(draw, y, line, _font(False, 40))
    y += 30
    if spec.abv_on_label:
        y = _centered(draw, y, spec.abv_on_label, _font(False, 38))
    y = _centered(draw, y, spec.net_on_label, _font(False, 38))
    y += 20
    for line in _wrap(draw, spec.bottler_on_label, _font(False, 30), W - 200):
        y = _centered(draw, y, line, _font(False, 30))
    if spec.country_on_label:
        y = _centered(draw, y, spec.country_on_label, _font(False, 30))

    # Government warning block near the bottom: bold prefix + regular body.
    # Body is rendered at a size/spacing that the OCR detector separates reliably — tight
    # spacing makes detectors merge or drop lines, which would corrupt the wording check.
    # The block is bottom-anchored so there's always a clear margin below the last line.
    if spec.warning_text:
        body_font = _font(False, 30)
        prefix_font = _font(spec.warning_prefix_bold, 32)
        step = 56
        prefix, _, body = spec.warning_text.partition(": ")
        prefix += ":"
        body_lines = _wrap(draw, body, body_font, 800)
        wy = (H - 40) - (len(body_lines) + 1) * step - 20
        # Prefix line (bold or not, per spec) — this is what the bold check measures.
        draw.text((70, wy), prefix, font=prefix_font, fill=FG)
        wy += step
        for line in body_lines:
            draw.text((70, wy), line, font=body_font, fill=FG)
            wy += step

    return _distort(img, spec.distortion)


def _distort(img: Image.Image, kind: str) -> Image.Image:
    """Apply a photographic imperfection to exercise the image-handling path."""
    if kind == "angle":
        return img.rotate(-8, expand=True, fillcolor=BG)
    if kind == "glare":
        overlay = Image.new("L", img.size, 0)
        od = ImageDraw.Draw(overlay)
        od.ellipse([W * 0.45, 80, W * 1.1, H * 0.5], fill=200)
        overlay = overlay.filter(ImageFilter.GaussianBlur(120))
        white = Image.new("RGB", img.size, (255, 255, 255))
        return Image.composite(white, img, overlay)
    if kind == "blur":
        # Heavy blur so the label is genuinely unreadable — this exercises the
        # "couldn't read this image" path, which must say so rather than guess.
        return img.filter(ImageFilter.GaussianBlur(14))
    return img


# --------------------------------------------------------------------------------------
# The 15 cases from the `testing` skill.
# --------------------------------------------------------------------------------------
BOURBON_CLASS = "Kentucky Straight Bourbon Whiskey"
BOTTLER = "Bottled by Old Tom Distillery, Louisville, KY"


def _spirits_app(**overrides) -> dict[str, str]:
    base = {
        "beverage_type": "spirits",
        "brand_name": "Old Tom Distillery",
        "class_type": BOURBON_CLASS,
        "alcohol_content": "45% Alc./Vol.",
        "net_contents": "750 mL",
        "bottler_name_address": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
    }
    base.update(overrides)
    return base


ALL_MATCH = {
    "brand_name": "match",
    "class_type": "match",
    "alcohol_content": "match",
    "net_contents": "match",
    "bottler_name_address": "match",
    "warning": "match",
}

SPECS: list[LabelSpec] = [
    # 1. Clean spirits label, everything correct.
    LabelSpec(
        "clean.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(),
        "match",
        ALL_MATCH,
    ),
    # 2. Brand in caps on label, title case in application.
    LabelSpec(
        "stones_throw.png",
        "spirits",
        "STONE'S THROW",
        "Blended Scotch Whisky",
        "43% Alc./Vol. (86 Proof)",
        "750 mL",
        "Imported by Stone's Throw Imports, NY, NY",
        "Product of Scotland",
        WARNING,
        True,
        _spirits_app(
            brand_name="Stone's Throw",
            class_type="Blended Scotch Whisky",
            alcohol_content="43% Alc./Vol.",
            bottler_name_address="Stone's Throw Imports, NY, NY",
            country_of_origin="Scotland",
        ),
        "match",
        {**ALL_MATCH, "country_of_origin": "match"},
    ),
    # 3. Wrong ABV (label 40%, application 45%).
    LabelSpec(
        "wrong_abv.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "40% Alc./Vol. (80 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(alcohol_content="45% Alc./Vol."),
        "mismatch",
        {**ALL_MATCH, "alcohol_content": "mismatch"},
    ),
    # 4. Proof inconsistent with ABV.
    LabelSpec(
        "bad_proof.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (80 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(alcohol_content="45% Alc./Vol."),
        "mismatch",
        {**ALL_MATCH, "alcohol_content": "mismatch"},
    ),
    # 5. Net contents in different units (75 cl vs 750 mL).
    LabelSpec(
        "units.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "75 cl",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(net_contents="750 mL"),
        "match",
        ALL_MATCH,
    ),
    # 6. Warning in title case.
    LabelSpec(
        "warning_titlecase.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING.replace("GOVERNMENT WARNING:", "Government Warning:"),
        True,
        _spirits_app(),
        "mismatch",
        {**ALL_MATCH, "warning": "mismatch"},
    ),
    # 7. Warning reworded.
    LabelSpec(
        "warning_reworded.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING.replace("impairs your ability", "reduces your ability"),
        True,
        _spirits_app(),
        "mismatch",
        {**ALL_MATCH, "warning": "mismatch"},
    ),
    # 8. Warning missing.
    LabelSpec(
        "warning_missing.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        "",
        True,
        _spirits_app(),
        "not_found",
        {**ALL_MATCH, "warning": "not_found"},
    ),
    # 9. Warning prefix not bold.
    LabelSpec(
        "warning_not_bold.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        False,
        _spirits_app(),
        "mismatch",
        {**ALL_MATCH, "warning": "mismatch"},
    ),
    # 10. Photo at an angle (lenient: match or review).
    LabelSpec(
        "angle.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(),
        "match",
        ALL_MATCH,
        distortion="angle",
    ),
    # 11. Photo with glare (lenient).
    LabelSpec(
        "glare.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(),
        "match",
        ALL_MATCH,
        distortion="glare",
    ),
    # 12. Beer label without ABV, application blank.
    LabelSpec(
        "beer_no_abv.png",
        "beer",
        "RIVER BEND LAGER",
        "Craft Lager",
        "",
        "355 mL",
        "Brewed by River Bend Brewing Co., Portland, OR",
        "",
        WARNING,
        True,
        {
            "beverage_type": "beer",
            "brand_name": "River Bend Lager",
            "class_type": "Craft Lager",
            "alcohol_content": "",
            "net_contents": "355 mL",
            "bottler_name_address": "River Bend Brewing Co., Portland, OR",
            "country_of_origin": "",
        },
        "match",
        {
            "brand_name": "match",
            "class_type": "match",
            "alcohol_content": "not_required",
            "net_contents": "match",
            "bottler_name_address": "match",
            "warning": "match",
        },
    ),
    # 13. Imported wine with country of origin.
    LabelSpec(
        "import_wine.png",
        "wine",
        "CHATEAU MIRAGE",
        "Bordeaux Red Wine",
        "13.5% Alc./Vol.",
        "750 mL",
        "Imported by Fine Wine Imports, Chicago, IL",
        "Product of France",
        WARNING,
        True,
        {
            "beverage_type": "wine",
            "brand_name": "Chateau Mirage",
            "class_type": "Bordeaux Red Wine",
            "alcohol_content": "13.5% Alc./Vol.",
            "net_contents": "750 mL",
            "bottler_name_address": "Fine Wine Imports, Chicago, IL",
            "country_of_origin": "France",
        },
        "match",
        {
            "brand_name": "match",
            "class_type": "match",
            "alcohol_content": "match",
            "net_contents": "match",
            "bottler_name_address": "match",
            "country_of_origin": "match",
            "warning": "match",
        },
    ),
    # 14. Unreadable / blurred image.
    LabelSpec(
        "blurry.png",
        "spirits",
        "OLD TOM DISTILLERY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(),
        "not_found",
        {},
        distortion="blur",
    ),
    # 15. Brand misspelled by one letter (label 'Distillary').
    LabelSpec(
        "misspelled.png",
        "spirits",
        "OLD TOM DISTILLARY",
        BOURBON_CLASS,
        "45% Alc./Vol. (90 Proof)",
        "750 mL",
        BOTTLER,
        "",
        WARNING,
        True,
        _spirits_app(),
        "review",
        {**ALL_MATCH, "brand_name": "review"},
    ),
]

CSV_COLUMNS = [
    "image_filename",
    "beverage_type",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_name_address",
    "country_of_origin",
]


def main() -> None:
    LABELS.mkdir(parents=True, exist_ok=True)

    expected: dict[str, dict] = {}
    with (SAMPLES / "applications.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for spec in SPECS:
            render(spec).save(LABELS / spec.filename, "PNG", optimize=True)
            writer.writerow({"image_filename": spec.filename, **spec.app})
            expected[spec.filename] = {
                "overall": spec.expected_overall,
                "fields": spec.expected_fields,
            }

    with (SAMPLES / "expected.json").open("w", encoding="utf-8") as fh:
        json.dump(expected, fh, indent=2, sort_keys=True)

    print(f"Wrote {len(SPECS)} labels to {LABELS}")
    print(f"Wrote {SAMPLES / 'applications.csv'} and {SAMPLES / 'expected.json'}")


if __name__ == "__main__":
    main()
