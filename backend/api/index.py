"""Vercel entry point.

Serverless instances do not run the ASGI lifespan, so the first request
creates the schema, loads the models and seeds demo data into the instance's
/tmp database before handing off to the normal FastAPI app.
"""

import asyncio

from app.main import app as fastapi_app

_ready = False
_lock = asyncio.Lock()


async def _prepare() -> None:
    global _ready
    if _ready:
        return
    async with _lock:
        if _ready:
            return
        from app.db.session import init_db
        from app.ml.predictor import warm_up
        from scripts.seed import seed

        await init_db()
        warm_up()
        await seed(count=60, days=14, reset=False, seed_value=7, if_empty=True)
        _ready = True


async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        await _prepare()
    await fastapi_app(scope, receive, send)
