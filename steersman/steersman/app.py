from fastapi import FastAPI

from steersman.config import Settings
from steersman.kernel import install_kernel
from steersman.routes.v1 import create_v1_router
from steersman.skills import default_registry


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    app = FastAPI(title="steersman", version="0.1.0")

    app.state.settings = app_settings
    app.state.idempotency_store = {}
    app.state.skill_registry = default_registry()

    install_kernel(app)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "steersman",
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/healthz",
            "host": app_settings.host,
            "port": str(app_settings.port),
        }

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_v1_router())

    return app
