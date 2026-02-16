class AppError(Exception):
    def __init__(
        self,
        *,
        kind: str,
        message: str,
        status_code: int,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
