from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fure.core.auth import APIKey, Permission, Role, User
from fure.database.models import APIKeyRow, RoleRow, UserRow
from fure.database.repositories import paginate


def role_from_row(row: RoleRow) -> Role:
    return Role.restore(
        id=row.id,
        name=row.name,
        permissions=frozenset(map(Permission, row.permissions)),
        protected=row.protected,
        created_at=row.created_at,
    )


def user_from_row(row: UserRow) -> User:
    return User.restore(
        id=row.id,
        username=row.username,
        enabled=row.enabled,
        roles=tuple(
            role_from_row(role)
            for role in sorted(row.roles, key=lambda role: role.name)
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def key_from_row(row: APIKeyRow) -> APIKey:
    return APIKey.restore(
        **{
            field: getattr(row, field)
            for field in (
                "id",
                "user_id",
                "name",
                "prefix",
                "created_at",
                "expires_at",
                "revoked_at",
            )
        },
        permissions=frozenset(map(Permission, row.permissions)),
        function_ids=frozenset(map(UUID, row.function_ids)),
    )


class UserRepository:
    def __init__(self, session):
        self.session = session

    async def get(self, id: UUID) -> UserRow | None:
        return await self.session.scalar(
            select(UserRow).options(selectinload(UserRow.roles)).where(UserRow.id == id)
        )

    async def by_username(self, username: str) -> UserRow | None:
        return await self.session.scalar(
            select(UserRow)
            .options(selectinload(UserRow.roles))
            .where(UserRow.username == username)
        )

    async def list(self, *, page, size):
        return await paginate(
            self.session,
            select(UserRow)
            .options(selectinload(UserRow.roles))
            .order_by(UserRow.created_at.desc(), UserRow.id.desc()),
            [],
            page,
            size,
        )


class RoleRepository:
    def __init__(self, session):
        self.session = session

    async def get(self, id: UUID):
        return await self.session.get(RoleRow, id)

    async def list(self, *, page, size):
        return await paginate(
            self.session, select(RoleRow).order_by(RoleRow.name), [], page, size
        )


class APIKeyRepository:
    def __init__(self, session):
        self.session = session

    async def list(self, user_id, *, page, size):
        return await paginate(
            self.session,
            select(APIKeyRow).order_by(
                APIKeyRow.created_at.desc(), APIKeyRow.id.desc()
            ),
            [APIKeyRow.user_id == user_id],
            page,
            size,
        )

    async def get(self, id: UUID, user_id: UUID):
        return await self.session.scalar(
            select(APIKeyRow).where(APIKeyRow.id == id, APIKeyRow.user_id == user_id)
        )
