from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from fure.database.models.base import Base


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Datetime must be timezone-aware")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return (
            value.replace(tzinfo=UTC)
            if value.utcoffset() is None
            else value.astimezone(UTC)
        )


class FunctionRow(Base):
    __tablename__ = "functions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("revisions.id", name="fk_functions_revision", use_alter=True)
    )
    enabled: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    version: Mapped[int] = mapped_column(Integer, default=1)
    revision: Mapped[RevisionRow | None] = relationship(
        foreign_keys=[revision_id], lazy="raise"
    )

    __table_args__ = (
        Index(
            "uq_functions_active_name",
            "name",
            unique=True,
            sqlite_where=deleted_at.is_(None),
            postgresql_where=deleted_at.is_(None),
        ),
        Index("ix_functions_created", "created_at", "id"),
    )


class RevisionRow(Base):
    __tablename__ = "revisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    function_id: Mapped[UUID] = mapped_column(ForeignKey("functions.id"))
    implementation: Mapped[dict] = mapped_column(JSON)
    runner_options: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    function: Mapped[FunctionRow] = relationship(
        foreign_keys=[function_id], lazy="raise"
    )

    __table_args__ = (
        Index("ix_revisions_function_created", "function_id", "created_at", "id"),
    )


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("revisions.id"))
    input: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    status: Mapped[str] = mapped_column(String(16))
    output: Mapped[object | None] = mapped_column(JSON(none_as_null=True))
    meta: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    duration: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    worker_id: Mapped[UUID | None] = mapped_column(Uuid)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revision: Mapped[RevisionRow] = relationship(lazy="raise")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_runs_status",
        ),
        CheckConstraint("duration IS NULL OR duration >= 0", name="ck_runs_duration"),
        Index("ix_runs_revision_created", "revision_id", "created_at", "id"),
        Index("ix_runs_status_heartbeat", "status", "heartbeat_at"),
        Index("ix_runs_created", "created_at", "id"),
    )
