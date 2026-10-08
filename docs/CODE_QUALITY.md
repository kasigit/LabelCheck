# Code Quality by Design — LabelCheck

_As of 2026-10-08_

Code quality in LabelCheck is a design constraint, not a cleanup phase. Five mechanisms
enforce it from the start: strict layer boundaries, typed contracts, automated gates on
every push, a layered test suite, and the stakeholder non-negotiables written directly
into the code rather than left to discipline.

## 1. Architecture & clear boundaries

Each layer has one job, so a change stays local and every piece is testable in isolation.

- **Thin routes.** API handlers only validate input, call a service, and shape the
  response. No business logic lives in a route or a React component.
- **Pure services.** The matching, parsing, and warning logic are pure functions (inputs
  to outputs, no I/O or globals), which is why the domain rules are trivial to unit-test.
- **Single orchestrator.** One `pipeline.verify()` sequences preprocess, OCR, extract,
  match, and warning; callers run it off the event loop so the server stays responsive.
- **Centralized config.** All tunable knobs live in one typed settings object with safe
  defaults, rather than scattered environment reads, so the app runs with zero
  configuration.

## 2. Contracts & type safety

The API shape is defined once and reused on both sides, so frontend and backend cannot
silently drift.

- **One source of truth.** Pydantic models define the request/response contract, which
  drives the OpenAPI schema the TypeScript types are generated from.
- **Typed throughout.** Modern Python typing (future annotations, `X | None` unions,
  enums) on the backend; the frontend builds under TypeScript `strict` with unused-locals
  and unused-parameters enabled.
- **Validation at the edge.** Inputs are parsed into models at the boundary; blanks are
  normalized consistently, and invalid data is rejected with a plain-English message
  instead of a stack trace.

## 3. Automated quality gates

Style and correctness are enforced by tools, not reviewers, so standards are consistent
and non-negotiable.

- **Linting & formatting.** Ruff lints and format-checks the Python; ESLint runs with
  `--max-warnings 0` on the frontend. Both fail the build on any violation.
- **CI on every push and PR.** Separate jobs run backend lint + tests, frontend
  lint + tests + build, and a Docker image build as a release gate, so the deployable
  artifact is proven on each change.
- **Deterministic environment.** Dependencies are pinned, OCR models are baked into the
  image, and the container is built the same way CI builds it.

## 4. Layered testing strategy

Tests are matched to risk: fast pure-logic tests for the domain rules, heavier
integration tests behind capability checks.

- **Pure unit tests** cover the matching, warning, and parsing logic, where the domain
  rules live and most subtle bugs hide.
- **Golden-sample tests** run real labels end to end and compare against expected results,
  catching regressions across the full pipeline.
- **A performance test** asserts every sample label verifies within the 5-second budget
  (end-to-end under 5s, server-measured under 4s), with the model warmed first so cold
  start is not counted.
- **API-contract and frontend tests** check validation responses and component/page
  behavior.
- **Graceful skips.** Tests needing the OCR engine or generated samples skip cleanly when
  those are absent, so the suite stays green on a minimal install while CI exercises
  everything.

## 5. Reliability, security & the non-negotiables

The stakeholder non-negotiables are encoded in the code, so they hold by construction
rather than by reminder.

- **No runtime network.** OCR models ship inside the dependencies and are baked into the
  image; the optional cloud path is off by default. The app works fully behind a firewall.
- **No persistent storage.** Uploads are processed in memory and never written to disk;
  batch results live in an in-memory store with a TTL and a background sweeper. No
  database.
- **Flags, never auto-rejects.** Uncertain outcomes are reported as REVIEW rather than
  MISMATCH, so the agent keeps the final call.
- **Hardened inputs.** Batch uploads are guarded against zip-slip and zip bombs, with
  per-file and total size caps; one bad label never sinks a batch.
- **Friendly failure.** Errors surface a plain-English message and never leak a stack
  trace.
- **Accessible by design.** For non-technical users, status is always conveyed by icon,
  word, and color together; controls are large with labeled inputs.
