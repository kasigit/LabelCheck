# LabelCheck

AI-assisted alcohol label verification prototype for TTB compliance agents. An agent uploads a
label image plus the application data it should match; the app reads the label and reports, field by
field, whether it matches. Supports single checks and batch uploads (200–300 labels).

This is a **standalone proof-of-concept**. It does not integrate with COLA.

## Non-negotiables

These come straight from stakeholder interviews. Do not trade them away without asking.

1. **≤ 5 seconds per label**, end to end. A previous vendor pilot failed at 30–40 s and agents abandoned it.
2. **Usable by non-technical users** (half the team is over 50). Large, obvious controls; plain words; nothing hidden.
3. **No outbound network calls at runtime.** The agency firewall blocks most external domains. OCR runs locally;
   model files are baked into the Docker image. Any cloud AI feature must be optional, off by default, and the app
   must work fully without it.
4. **No persistent storage of uploads or results.** Process in memory or temp files deleted immediately. No database.
   Batch results live in memory with a TTL.
5. **The agent makes the final call.** The tool flags; it never auto-rejects. Uncertain results are `REVIEW`, not `MISMATCH`.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + TypeScript + Vite, Tailwind CSS, TanStack Query |
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| OCR | RapidOCR (PaddleOCR models on ONNX Runtime, CPU) |
| Image processing | OpenCV |
| Fuzzy matching | RapidFuzz |
| Tests | pytest, Vitest + React Testing Library, Playwright |
| Lint/format | Ruff (Python), ESLint + Prettier (TS) |
| Deploy | Single Docker container (FastAPI serves the React build) → Azure Container Apps |
| CI | GitHub Actions |

## Layout

```
backend/
  app/
    main.py              # FastAPI app, startup (loads OCR model once), static file serving
    api/                 # Route handlers only — thin, no business logic
    services/
      preprocess.py      # OpenCV: deskew, glare reduction, resize
      ocr.py             # RapidOCR wrapper → text lines with boxes
      extract.py         # OCR lines → candidate field values
      matching.py        # Field comparison (fuzzy, numeric, unit-aware)
      warning.py         # Government Warning: exact text, caps, bold check
      batch.py           # Worker pool, in-memory job store with TTL
    models.py            # Pydantic request/response + CSV row schema
    rules/beverage_rules.yaml   # Required fields per beverage type
  tests/
frontend/
  src/
    api/                 # Typed client (types generated from OpenAPI)
    components/
    pages/               # SingleCheck, BatchCheck, Results
samples/                 # Test labels, applications.csv, expected.json
Dockerfile
.github/workflows/ci.yml
```

## Commands

```bash
# Backend (from backend/)
uv sync                              # install deps
uv run fastapi dev app/main.py       # dev server on :8000
uv run pytest                        # tests
uv run ruff check . && uv run ruff format .

# Frontend (from frontend/)
npm install
npm run dev                          # Vite on :5173, proxies /api to :8000
npm run test                         # Vitest
npm run lint
npm run gen:api                      # regenerate TS types from backend OpenAPI
npx playwright test                  # e2e (needs both servers running)

# Full app
docker build -t labelcheck . && docker run -p 8000:8000 labelcheck
```

## Skills

Load the relevant skill before working in that area:

- `frontend` — UI conventions, accessibility rules, components, API client
- `backend` — API design, services, performance budget, batch processing
- `label-rules` — TTB field rules, matching logic, Government Warning check (the domain core)
- `testing` — test strategy, sample labels, performance tests

## Working conventions

- Run the relevant tests and linter before saying a change is done.
- When changing an API response shape, update the Pydantic model, run `npm run gen:api`, and fix the frontend types.
- Keep business logic out of route handlers and React components.
- Record any assumption you make about TTB rules in `docs/assumptions.md` (it feeds the README).
- Don't add dependencies that download models or call external services at runtime.
