"""FastAPI app entrypoint — implements DESIGN.md §2 (Overview) and §4 (Interface Contracts).

This service: authenticates clients (M2), enqueues indexing jobs (M1), and
proxies query requests as SSE to the Agent service (M2). The frontend talks
to this gateway exclusively — never directly to the agent or DB.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dcode_api.routes import query, repos
from dcode_api.settings import api_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # TODO(M2): warm DB / Redis / RabbitMQ / agent-client pools per DESIGN.md §2.6.
    yield


app = FastAPI(
    title="Dcode API Gateway",
    version="0.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origins_list,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(repos.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Shallow liveness probe — does not check dependent services."""
    return {"status": "ok"}
