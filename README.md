# LabelCheck

> 📖 **Prefer a nicely formatted version?** Open **[`docs/README.html`](docs/README.html)**
> in your browser for the full documentation as a styled site — a sidebar links this
> overview, the architecture & design docs, the verification guide, and the assumptions,
> with a rendered architecture diagram and light/dark support. (Download it and open
> locally, or browse the `docs/` folder.)

**AI-assisted alcohol-label verification for TTB compliance agents.**

An agent uploads a label image plus the application data it should match. LabelCheck reads
the label with on-device OCR and reports, field by field, whether the label matches the
application — including a strict check of the Government Health Warning. It supports single
checks and batch uploads (200–300 labels).

The tool **flags**; the agent makes the final call. Uncertain results are marked
**Needs review**, never a confident wrong answer.

> This is a standalone proof-of-concept. It does not integrate with COLA, stores nothing,
> and makes **no outbound network calls at runtime** — it runs entirely behind a firewall.

See [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) for the full write-up (what it does, the
architecture diagram, the tech-stack rationale, constraints) and
[docs/assumptions.md](docs/assumptions.md) for the assumptions made.

**Prefer reading in a browser?** Open **[docs/README.html](docs/README.html)** — a styled,
self-contained HTML version of the docs with a sidebar linking this overview, the full
documentation, the verification guide, and the assumptions (rendered architecture diagram,
light/dark support). Regenerate it after editing any `.md` with
`python scripts/build_docs_html.py`.

---

## What you need

- **Python 3.12+** and **Node 20+**
- About 300 MB of disk for the OCR model + Python deps (installed once, from PyPI)
- No GPU, no cloud account, no API keys

Everything runs locally on CPU.

---

## Quick start (Docker — one command)

The simplest way to see the whole app (API + UI in one container):

```bash
docker build -t labelcheck .
docker run -p 8000:8000 labelcheck
```

Then open **http://localhost:8000**.

The container bakes the OCR models in at build time, so the running container needs no
network access.

### Deploy to Railway

The repo is Railway-ready: Railway detects the `Dockerfile`, builds the image, and runs it.
1. Create a new Railway project → **Deploy from GitHub repo** → pick this repo.
2. Railway builds from the `Dockerfile` automatically; no extra build config needed.
3. The container binds to Railway's `$PORT` (see the `CMD` in the `Dockerfile`), so the
   public URL works out of the box. Generate a domain under the service's **Settings →
   Networking** and share that URL for others to test.

---

## Run it locally for development

Two terminals: the backend API on `:8000`, and the Vite dev server on `:5173` (which
proxies `/api` to the backend).

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                             # installs deps + OCR models + test tools
python ../scripts/generate_samples.py               # create the sample labels (one time)
uvicorn app.main:app --reload --port 8000
```

The first start downloads nothing at runtime but takes a few seconds to load the OCR model
(watch for `OCR model loaded.` in the log). Check it:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","ocr_model_loaded":true}
```

> `uv` works too if you prefer it: `uv sync` then `uv run uvicorn app.main:app --reload`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

---

## Try it (how to verify it works)

> For a full step-by-step verification script (exact values to type for several single
> images, plus the batch flow), see **[docs/HOW_TO_VERIFY.md](docs/HOW_TO_VERIFY.md)**.

### Single label, in the UI
1. Go to **Check one label**.
2. Choose a sample image from `samples/labels/` — e.g. `clean.png`.
3. Pick **Spirits**, then fill the fields to match (or copy the matching row from
   `samples/applications.csv`). For `clean.png`:
   - Brand name: `Old Tom Distillery`
   - Class / type: `Kentucky Straight Bourbon Whiskey`
   - Alcohol content: `45% Alc./Vol.`
   - Net contents: `750 mL`
   - Bottler: `Old Tom Distillery, Louisville, KY`
4. Click **Check label**. You should see **Overall: Match** with a green badge per field.

Now try a failing one: upload `wrong_abv.png` with the same data — the alcohol field comes
back **Mismatch** ("Label says 40%, application says 45%"). Or `warning_titlecase.png` —
the Government Warning's **ALL CAPITALS** sub-check fails.

### Batch, in the UI
1. Zip the sample images: `cd samples/labels && zip ../images.zip *.png`
2. Go to **Check a batch**, upload `samples/applications.csv` and `samples/images.zip`,
   click **Check all labels**.
3. Watch the progress bar fill, filter by **Mismatch**, open any row, and
   **Download results (CSV)**.

### From the command line
```bash
# Single verify
curl -X POST http://localhost:8000/api/verify \
  -F "image=@samples/labels/clean.png;type=image/png" \
  -F 'application={"beverage_type":"spirits","brand_name":"Old Tom Distillery",
       "class_type":"Kentucky Straight Bourbon Whiskey","alcohol_content":"45% Alc./Vol.",
       "net_contents":"750 mL","bottler_name_address":"Old Tom Distillery, Louisville, KY"}'
```

---

## Run the tests

```bash
# Backend: unit rules, parsing, API contract, golden samples, and the 5-second budget
cd backend
python ../scripts/generate_samples.py   # golden-sample tests need the images
ruff check . && ruff format --check .
pytest

# Frontend: component + interaction tests, lint, and a production build
cd frontend
npm run lint
npm run test
npm run build
```

The golden-sample test (`tests/test_samples.py`) runs the full pipeline over every image
in `samples/` and checks the result against `samples/expected.json`. The performance test
(`tests/test_performance.py`) asserts every label returns in under 5 seconds (it runs in a
few hundred milliseconds on a laptop).

---

## Project layout

```
backend/     FastAPI app, OCR + matching pipeline, tests   (see .claude/skills/backend)
frontend/    React + TypeScript UI                         (see .claude/skills/frontend)
scripts/     generate_samples.py — builds the sample set
samples/     labels/*.png, applications.csv, expected.json (test data)
docs/        full documentation, architecture, assumptions
Dockerfile   single-container build (API serves the UI)
```

The domain rules (TTB field matching, the Government Warning check) live in
[.claude/skills/label-rules](.claude/skills/label-rules/SKILL.md).
