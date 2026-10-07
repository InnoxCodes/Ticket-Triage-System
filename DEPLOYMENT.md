# Deployment

TriageAI deploys as two independent services: a Dockerized FastAPI backend
and a static frontend build. Neither needs the other to build, only to run —
the frontend reads the API's URL from an environment variable at build time.

## Backend → Railway

1. Create a new Railway project, then **New Service → GitHub Repo**, and set
   the root directory to `backend/`. Railway picks up `railway.json` and
   builds from the `Dockerfile` automatically.
2. **Attach a volume** mounted at `/data`. This is where the SQLite file
   lives (`DATABASE_URL=sqlite+aiosqlite:////data/triageai.db`, already set
   in the Dockerfile) — without a volume, the database resets on every
   redeploy.
3. Set environment variables:
   | Variable | Value |
   |---|---|
   | `CORS_ORIGINS` | Your frontend's deployed URL, e.g. `https://triageai.vercel.app` (comma-separated if there's more than one) |
   | `ENVIRONMENT` | `production` |
4. Keep **one replica**. The live-ticket WebSocket hub (`app/core/events.py`)
   is in-process; a second worker would never see events published on the
   first. Scaling that out needs a Redis pub/sub backplane first (see the
   known-limits table in [ARCHITECTURE.md](ARCHITECTURE.md)).
5. Deploy. The container seeds ~80 demo tickets on first boot if the volume
   is empty (`scripts/seed.py --if-empty`), and stays quiet on every boot
   after that. Check `https://<your-service>.up.railway.app/api/health` —
   `model_loaded` should be `true`.

## Frontend → Vercel

1. Import the repo, set the **root directory** to `frontend/`. `vercel.json`
   already handles SPA routing (client-side routes like `/analytics` and
   `/submit` resolve to `index.html`) and long-lived caching for fingerprinted
   assets.
2. Set the build-time environment variable:
   | Variable | Value |
   |---|---|
   | `VITE_API_URL` | Your Railway service's URL, e.g. `https://triageai-api.up.railway.app` |
3. Deploy. Vercel's default build command (`npm run build`) and output
   directory (`dist`) are both correct as-is.

## Verifying the connection

Once both are live:

1. Open the Vercel URL — the queue should load (even if empty).
2. Open `/submit` in a new tab, submit a ticket, and confirm it appears on
   the dashboard's Open column without a manual refresh. This exercises the
   classify → create → WebSocket broadcast path across both services and
   both origins in one action, which is the thing most likely to be
   misconfigured (a missing origin in `CORS_ORIGINS`, or a `VITE_API_URL`
   typo) if something's wrong.
3. Check the browser console for WebSocket connection errors — the dashboard
   also falls back to polling every 8 seconds if the socket can't connect, so
   a misconfigured `CORS_ORIGINS` shows up as a stale-looking queue rather
   than an obvious crash.

## Running the whole stack locally with Docker

No cloud accounts needed — this is what `docker-compose.yml` is for:

```bash
make up     # builds both images, runs them together
```

nginx (the frontend image) proxies `/api` and `/ws` to the backend
container, so the browser only ever talks to one origin
(`http://localhost:8080`) and CORS never enters the picture locally. API docs
are still reachable directly at `http://localhost:8000/docs`.

```bash
make down   # stop and remove the containers
```

The SQLite file persists in a named Docker volume (`triageai-data`) across
`make down` / `make up` cycles; delete it with `docker volume rm
triageai_triageai-data` to start over.
