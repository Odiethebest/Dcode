"""FastAPI gateway entrypoint and public routing boundary.

This service validates and enqueues indexing requests, serves read-only source
and graph inspection, and proxies query requests as SSE to the agent. The
frontend talks to this gateway exclusively — never directly to the agent or DB.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dcode_shared.internal import internal_api_key_error
from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from dcode_api import deps, readiness
from dcode_api.auth import auth_configuration_error, require_session
from dcode_api.routes import auth, inspector, internal, query, repos
from dcode_api.settings import api_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Refuse to start a gate that cannot be enforced. Serving the workbench
    # openly because a secret was missing is the failure this prevents, and it
    # is one that looks fine from the outside.
    misconfigured = auth_configuration_error() or internal_api_key_error(
        api_settings.internal_api_key,
        # The gate being on is this process's best available signal that it is
        # a real deployment rather than someone's laptop.
        strict=api_settings.auth_enabled,
    )
    if misconfigured is not None:
        raise RuntimeError(misconfigured)

    # Own the shared Redis + agent-client lifecycle: warm at startup, release on
    # shutdown. (DB uses the shared SQLAlchemy engine pool; RabbitMQ connects per
    # publish on the submit path.)
    deps.warm_pools()
    try:
        yield
    finally:
        await deps.close_pools()


def create_app() -> FastAPI:
    """Build the gateway. A function so the docs switch is testable.

    `app` below is what uvicorn imports; nothing else should call this except
    tests that need a second instance under different settings.
    """
    application = FastAPI(
        title="Dcode API Gateway",
        version="0.0.0",
        lifespan=lifespan,
        # /docs, /redoc and /openapi.json enumerate the /internal/* retrieval
        # and graph surface. Handy locally, an advertisement in production.
        docs_url="/docs" if api_settings.docs_enabled else None,
        redoc_url="/redoc" if api_settings.docs_enabled else None,
        openapi_url="/openapi.json" if api_settings.docs_enabled else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.cors_origins_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    # The gate. `require_session` is a no-op while AUTH_ENABLED is false, so
    # the default local stack and the existing tests see no change; with it on,
    # every route below returns 401 without a valid session cookie.
    gated = [Depends(require_session)]

    # Not gated: signing in cannot require being signed in.
    application.include_router(auth.router, prefix="/api/v1")

    application.include_router(repos.router, prefix="/api/v1", dependencies=gated)
    application.include_router(query.router, prefix="/api/v1", dependencies=gated)
    application.include_router(inspector.router, prefix="/api/v1", dependencies=gated)
    # /internal/* is not part of the session gate: it is service-to-service and
    # carries its own shared-key check, and the agent has no cookie to present.
    application.include_router(internal.router, prefix="/internal")

    @application.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        """Shallow liveness probe — does not check dependent services.

        Deliberately shallow: a liveness probe that fails when a dependency is
        down gets the process restarted, which fixes nothing and loses the logs.
        Use /readyz to decide whether it can serve.
        """
        return {"status": "ok"}

    @application.get("/readyz", tags=["meta"])
    async def readyz(response: Response) -> dict[str, object]:
        """Deep probe: database, Redis, and the embedding-dimension agreement.

        503 when anything fails, with a per-check reason. Open like /healthz —
        it reports whether this process works, not anything about the corpus.
        """
        checks = await readiness.run_checks()
        ready = all(check.ok for check in checks)
        if not ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "ready" if ready else "not ready",
            "checks": [
                {"name": check.name, "ok": check.ok, "detail": check.detail}
                for check in checks
            ],
        }

    return application


app = create_app()
