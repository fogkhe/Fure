import json
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from fure.core.types import JSONValue
from fure.database.connection import Database
from fure.database.models import VariableRow
from fure.database.repositories import paginate
from fure.services.errors import Conflict, InvalidInput, NotFound, Unavailable


@dataclass(frozen=True, slots=True)
class VariableInfo:
    name: str
    secret: bool
    value: JSONValue
    updated_at: datetime


class VariableService:
    def __init__(self, database: Database, key: str | None = None) -> None:
        self.database = database
        try:
            self._cipher = Fernet(key) if key else None
        except ValueError, TypeError:
            raise ValueError(
                "VARIABLES_ENCRYPTION_KEY must be a valid Fernet key"
            ) from None

    @staticmethod
    def _info(row: VariableRow) -> VariableInfo:
        return VariableInfo(
            row.name, row.secret, None if row.secret else row.payload, row.updated_at
        )

    def _payload(self, value: JSONValue, *, secret: bool) -> JSONValue:
        try:
            serialized = json.dumps(value, allow_nan=False)
        except ValueError, RecursionError:
            raise InvalidInput("Variable value must be valid JSON") from None
        if not secret:
            return value
        if not isinstance(value, str) or not value:
            raise InvalidInput("A secret variable requires a non-empty string")
        if self._cipher is None:
            raise Unavailable("Secret variable encryption is not configured")
        return self._cipher.encrypt(serialized.encode()).decode("ascii")

    async def list(self, *, page: int, size: int) -> tuple[list[VariableInfo], int]:
        async with self.database.sessions() as session:
            rows, total = await paginate(
                session, select(VariableRow).order_by(VariableRow.name), [], page, size
            )
            return [self._info(row) for row in rows], total

    async def create(
        self, name: str, value: JSONValue, *, secret: bool
    ) -> VariableInfo:
        row = VariableRow(
            name=name,
            secret=secret,
            payload=self._payload(value, secret=secret),
            updated_at=datetime.now(UTC),
        )
        try:
            async with self.database.sessions.begin() as session:
                session.add(row)
        except IntegrityError:
            raise Conflict("Variable name is already in use") from None
        return self._info(row)

    async def replace(self, name: str, value: JSONValue) -> VariableInfo:
        async with self.database.sessions.begin() as session:
            if self.database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN IMMEDIATE"))
            row = await session.get(VariableRow, name, with_for_update=True)
            if row is None:
                raise NotFound("Variable not found")
            row.payload = self._payload(value, secret=row.secret)
            row.updated_at = datetime.now(UTC)
            return self._info(row)

    async def delete(self, name: str) -> None:
        async with self.database.sessions.begin() as session:
            deleted = await session.scalar(
                delete(VariableRow)
                .where(VariableRow.name == name)
                .returning(VariableRow.name)
            )
            if deleted is None:
                raise NotFound("Variable not found")

    async def execution_values(self) -> tuple[dict[str, JSONValue], bool]:
        async with self.database.sessions() as session:
            rows = (await session.scalars(select(VariableRow))).all()
        values: dict[str, JSONValue] = {}
        has_secrets = False
        for row in rows:
            if not row.secret:
                values[row.name] = row.payload
                continue
            has_secrets = True
            if self._cipher is None:
                raise Unavailable("Secret variable encryption is not configured")
            if not isinstance(row.payload, str):
                raise Unavailable("Secret variables could not be decrypted")
            try:
                values[row.name] = json.loads(
                    self._cipher.decrypt(row.payload.encode())
                )
            except InvalidToken, ValueError:
                raise Unavailable("Secret variables could not be decrypted") from None
        return values, has_secrets
