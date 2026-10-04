## What this changes

<!-- One or two sentences: what, and why. -->

## Checklist

- [ ] `make lint` passes (ruff + ESLint + tsc)
- [ ] `make test` passes (backend pytest suite)
- [ ] If this touches `backend/ml/`, `make dataset && make train` was run and the
      new `metrics.json` / artifacts are included
- [ ] If this changes the API contract, `frontend/src/lib/types.ts` was updated to match
- [ ] Docs updated if behavior, setup, or architecture changed (`README.md`,
      `ARCHITECTURE.md`, `MODEL.md`)

## Screenshots

<!-- For UI changes, a before/after screenshot or short clip. -->
