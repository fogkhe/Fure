from pydantic import Field, Secret
from pydantic_settings import BaseSettings

from fure.environment import DATA_PATH


class Settings(BaseSettings):
    database_url: Secret[str] = Field(
        default=Secret(f"sqlite+aiosqlite:///{DATA_PATH / 'fure.db'}"),
    )


settings = Settings()
