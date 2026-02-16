from fastapi import FastAPI

from steersman.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    app = FastAPI(title="steersman", version="0.1.0")

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

    return app
