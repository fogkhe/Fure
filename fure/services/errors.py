from uuid import UUID


class ServiceError(Exception):
    def __init__(
        self, message: str, *, code: str = "internal_error", run_id: UUID | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.run_id = run_id


class NotFound(ServiceError):
    pass


class Conflict(ServiceError):
    pass


class InvalidInput(ServiceError):
    pass


class ExecutionFailed(ServiceError):
    pass


class ProviderFailed(ServiceError):
    pass


class ExecutionTimedOut(ServiceError):
    pass


class ExecutionCancelled(ServiceError):
    pass


class Unavailable(ServiceError):
    pass
