---
name: testing
description: Test strategy for LabelCheck — pytest unit and golden-sample tests, the 5-second performance test, Vitest component tests, Playwright end-to-end flows, and how to build the sample label set. Use when writing or running tests, adding sample labels, or setting up CI.
---

# Testing

## Layers

| Layer | Tool | Location | Runs in CI |
|---|---|---|---|
| Matching & warning rules (pure functions) | pytest | `backend/tests/test_matching.py`, `test_warning.py` | ✓ |
| Parsing (ABV, net contents, CSV rows) | pytest | `backend/tests/test_parsing.py` | ✓ |
| Golden samples (real images, full pipeline) | pytest | `backend/tests/test_samples.py` | ✓ |
| Performance | pytest | `backend/tests/test_performance.py` | ✓ |
| API contract | pytest + FastAPI `TestClient` | `backend/tests/test_api.py` | ✓ |
| Components | Vitest + React Testing Library | `frontend/src/**/*.test.tsx` | ✓ |
| End to end | Playwright | `frontend/e2e/` | ✓ (against the Docker image) |

## Sample label set (`samples/`)

```
samples/
  labels/              # PNG/JPG images
  applications.csv     # one row per image, same schema as batch upload
  expected.json        # { "<image_filename>": { "overall": "...", "fields": { "<field>": "<status>" } } }
```

Minimum cases (create with an AI image generator, keep each under ~1 MB):

| # | Case | Expected |
|---|---|---|
| 1 | Clean spirits label, everything correct (OLD TOM DISTILLERY sample) | all `match` |
| 2 | Brand in caps on label, title case in application (STONE'S THROW) | brand `match` |
| 3 | Wrong ABV (label 40%, application 45%) | alcohol `mismatch` |
| 4 | Proof inconsistent with ABV | alcohol `mismatch` |
| 5 | Net contents in different units (75 cl vs 750 mL) | net `match` |
| 6 | Warning in title case ("Government Warning:") | warning caps `mismatch` |
| 7 | Warning reworded | warning wording `mismatch` |
| 8 | Warning missing | warning `not_found` |
| 9 | Warning prefix not bold | warning bold `mismatch` |
| 10 | Photo at an angle | all `match` (or `review`) |
| 11 | Photo with glare | all `match` (or `review`) |
| 12 | Beer label without ABV, application blank | alcohol `not_required` |
| 13 | Imported wine with country of origin | country `match` |
| 14 | Unreadable/blurred image | fields `not_found`, clear message |
| 15 | Brand misspelled by one letter | brand `review` |

`test_samples.py` parametrizes over `expected.json`. Image-quality cases (10, 11) accept `match` **or** `review`;
everything else must match exactly. When a sample fails, decide whether the rule or the expectation is wrong —
don't loosen `expected.json` just to go green.

## Performance test

```python
@pytest.mark.parametrize("image", ALL_SAMPLE_IMAGES)
def test_single_label_under_budget(client, image):
    t = time.perf_counter()
    r = client.post("/api/verify", files=..., data=...)
    assert r.status_code == 200
    assert (time.perf_counter() - t) < 5.0
```

Also assert `timings_ms["total"] < 4000` so there's headroom on slower hosting. Warm up the model once in a
session fixture so cold start isn't counted.

## Frontend tests

- Query by role and visible text — this doubles as an accessibility check.
- Cover: every status badge renders icon + word; error messages render server `detail`; buttons disable while loading;
  batch validation problems list; progress bar text ("143 of 212 checked").
- Mock the API at the `api/client.ts` boundary, not `fetch`.

## Playwright e2e (keep to a few high-value flows)

1. Single check: upload sample #1, fill form, click "Check label", see all Match.
2. Single check failure: sample #6, see the warning's capitals check marked Mismatch with a plain reason.
3. Batch: upload `applications.csv` + ZIP of samples, wait for completion, download results CSV.
4. Bad upload: upload a .txt as the image, see a plain-English error.

## Before saying a change is done

```bash
cd backend && uv run ruff check . && uv run pytest
cd frontend && npm run lint && npm run test
```

Run Playwright when you've touched the API shape or a page flow.
