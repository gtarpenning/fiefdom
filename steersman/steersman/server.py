import ipaddress
import logging

import uvicorn

from steersman.app import create_app
from steersman.config import Settings


def is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return ip.is_loopback


def assert_loopback_host(host: str) -> None:
    if not is_loopback_host(host):
        raise ValueError(f"Refusing non-loopback bind host: {host}")


def run(settings: Settings | None = None) -> None:
    app_settings = settings or Settings()
    assert_loopback_host(app_settings.host)

    logging.basicConfig(
        level=getattr(logging, app_settings.log_level.upper(), logging.INFO),
        format="%(levelname)s:     %(name)s - %(message)s",
    )

    uvicorn.run(
        create_app(app_settings),
        host=app_settings.host,
        port=app_settings.port,
        log_level=app_settings.log_level,
    )
