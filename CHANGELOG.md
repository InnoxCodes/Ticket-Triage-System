# Changelog

Notable changes to TriageAI. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-09-13

Initial release.

### Added

- Dual TF-IDF + logistic regression classifiers for ticket category (94.6%
  accuracy) and urgency (73.2%, 94.3% within one severity level), trained on
  a 1,400-ticket synthetic corpus with realistic label noise and a
  stated-vs-implicit-impact split — see [MODEL.md](MODEL.md).
- Selective prediction: predictions below a measured confidence threshold
  (0.55 category / 0.45 urgency) are flagged for human review instead of
  routed silently.
- FastAPI backend with async SQLite/SQLAlchemy storage, full ticket CRUD,
  filtering and pagination, and an analytics endpoint aggregating volume,
  distributions, SLA breaches, resolution time, and override reliability.
- Live ticket feed over a native WebSocket, with polling fallback and
  jittered-backoff reconnection on the client.
- React 19 + TypeScript dashboard: drag-and-drop Kanban queue, a ticket
  detail slide-over with confidence breakdowns and one-click override, an
  analytics view with the full model-performance report, and a customer-
  facing submission form with a live classification preview.
- Traffic simulator that injects fresh, model-unseen demo tickets on a
  timer, toggleable from the dashboard.
- 41 backend tests (preprocessing, model contract, dataset generator, API,
  WebSocket serialization).
- Docker images for both services, `docker-compose.yml` for a same-origin
  local stack, and Railway/Vercel deploy configs — see
  [DEPLOYMENT.md](DEPLOYMENT.md).
- GitHub Actions CI (lint + test for both services), Dependabot, issue/PR
  templates.

### Fixed during development

- **Template leakage in the training data.** The first dataset generator
  drew tickets from a small fixed pool of sentence templates, so both
  classifiers scored a meaningless 100% on the held-out set — the corpus was
  rebuilt with compositional phrasing, implicit-urgency tickets, and
  simulated annotator disagreement.
- **The live feed silently delivered nothing.** WebSocket payloads containing
  a `datetime` failed Starlette's plain `send_json`, and that failure was
  indistinguishable from a dead client, so every connected browser was
  quietly dropped. Payloads are now encoded once with `jsonable_encoder`
  before any send.
- **`CORS_ORIGINS` as a comma-separated env var crashed the server at boot.**
  pydantic-settings JSON-decodes list-typed settings by default, which
  rejects the comma-separated form every PaaS environment-variable UI
  produces — any real deployment would have failed to start.
