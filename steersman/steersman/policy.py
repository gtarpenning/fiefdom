from fastapi import Request

from steersman.errors import AppError


def check(request: Request, capability: str) -> bool:
    capabilities = getattr(request.state, "capabilities", set())
    if not isinstance(capabilities, set):
        return False
    return capability in capabilities


def require(request: Request, capability: str) -> None:
    if not check(request, capability):
        raise AppError(
            kind="auth_denied",
            message=f"Missing capability: {capability}",
            status_code=403,
            retryable=False,
        )


def capability_dependency(capability: str):
    def _dependency(request: Request) -> None:
        require(request, capability)

    return _dependency
