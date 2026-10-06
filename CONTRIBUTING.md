# Contributing

## Setup

```bash
make install   # backend venv + pip install, frontend npm ci
make seed      # 90 demo tickets
make api       # http://localhost:8000
make web       # http://localhost:5173, in a second terminal
```

See the [README](README.md) for the full local-setup walkthrough and
[ARCHITECTURE.md](ARCHITECTURE.md) for how a ticket flows through the system.

## Before opening a PR

```bash
make lint   # ruff (backend) + ESLint + tsc (frontend)
make test   # backend pytest suite
```

Both also run in CI (`.github/workflows/`) on every push and PR.

## Changing the ML pipeline

`backend/app/ml/preprocess.py` is imported by both training and serving —
never duplicate its logic. If you touch `backend/ml/` (the dataset generator,
training, or evaluation), regenerate the artifacts and commit the result:

```bash
make dataset   # only if you changed the generator or templates
make train     # always, if training/evaluation code changed
```

This rewrites `backend/app/ml/artifacts/{category,urgency}_model.joblib` and
`metrics.json`, which are committed so the app runs without a training step.
Include the new metrics in your PR description if they moved.

## Changing the API contract

`frontend/src/lib/types.ts` is hand-written to mirror
`backend/app/schemas/*.py`. There's no code generation step, so update both
sides in the same PR.

## Commit style

Conventional-ish prefixes (`feat`, `fix`, `chore`, `docs`, `test`, `ci`,
`build`, `refactor`) with a scope, e.g. `fix(realtime): ...`. Look at
`git log` for the pattern. Prefer several small, single-purpose commits over
one large one — it makes `git bisect` and review both easier.
