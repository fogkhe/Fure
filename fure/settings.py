from typing import Self

from pydantic import Field, Secret, model_validator
from pydantic_settings import BaseSettings

from fure.environment import DATA_PATH


class Settings(BaseSettings):
    database_url: Secret[str] = Field(
        default=Secret(f"sqlite+aiosqlite:///{DATA_PATH / 'fure.db'}"),
    )
    database_auto_migrate: bool = True
    execution_heartbeat_interval: float = Field(default=1, gt=0, allow_inf_nan=False)
    execution_lease_seconds: float = Field(default=30, ge=10, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_lease(self) -> Self:
        if self.execution_lease_seconds <= self.execution_heartbeat_interval * 3:
            raise ValueError("Execution lease must exceed three heartbeat intervals")
        return self


settings = Settings()
