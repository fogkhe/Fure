from datetime import datetime

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from fure.core.types import JSONValue
from fure.database.models.base import Base
from fure.database.models.entities import UTCDateTime


class VariableRow(Base):
    __tablename__ = "variables"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    secret: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[JSONValue] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
