import asyncio
import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

from pwdlib import PasswordHash
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError

from fure.core.auth import Permission, Principal
from fure.database.auth import (
    APIKeyRepository,
    RoleRepository,
    UserRepository,
    key_from_row,
    role_from_row,
    user_from_row,
)
from fure.database.models import APIKeyRow, FunctionRow, RoleRow, SessionRow, UserRow
from fure.database.models.auth import user_roles
from fure.services.errors import (
    Conflict,
    Forbidden,
    InvalidInput,
    NotFound,
    Unauthorized,
)

PASSWORDS = PasswordHash.recommended()
# A missing username still performs a real password verification.
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(value: str) -> str:
    return secret_hash("csrf:" + value)


def require(principal: Principal, permission: Permission) -> None:
    if not principal.allows(permission):
        raise Forbidden(f"Permission required: {permission.value}")


def require_function_access(principal: Principal | None, id: UUID) -> None:
    if principal is not None and not principal.allows_function(id):
        raise NotFound("Function not found")


@asynccontextmanager
async def auth_transaction(database):
    try:
        async with database.sessions.begin() as session:
            # Serialize account/role mutations, including the last-admin check.
            if database.engine.dialect.name == "sqlite":
                await session.execute(text("BEGIN IMMEDIATE"))
            await session.scalar(
                select(RoleRow).where(RoleRow.protected.is_(True)).with_for_update()
            )
            yield session
    except IntegrityError as error:
        raise Conflict(
            "Username or role name is already in use, or the role is assigned"
        ) from error


class AuthService:
    def __init__(self, database):
        self.database = database

    async def authenticate(self, secret: str, *, api_key: bool) -> Principal:
        if not secret or len(secret) > 512:
            raise Unauthorized("Invalid or expired credentials")
        now = datetime.now(UTC)
        async with self.database.sessions() as session:
            if api_key:
                credential = await session.scalar(
                    select(APIKeyRow).where(
                        APIKeyRow.secret_hash == secret_hash(secret)
                    )
                )
                if (
                    credential is None
                    or credential.revoked_at is not None
                    or (
                        credential.expires_at is not None
                        and credential.expires_at <= now
                    )
                ):
                    raise Unauthorized("Invalid or expired credentials")
            else:
                credential = await session.get(SessionRow, secret_hash(secret))
                if credential is None or credential.expires_at <= now:
                    raise Unauthorized("Invalid or expired credentials")
            row = await UserRepository(session).get(credential.user_id)
            if row is None or not row.enabled:
                raise Unauthorized("Invalid or expired credentials")
            user = user_from_row(row)
            return Principal(
                user=user,
                permissions=user.permissions.intersection(
                    map(Permission, credential.permissions)
                )
                if api_key
                else user.permissions,
                key_id=credential.id if api_key else None,
                csrf_token=None if api_key else csrf_token(secret),
                function_ids=frozenset(map(UUID, credential.function_ids))
                if api_key
                else None,
            )

    async def login(
        self,
        username: str,
        password: str,
        *,
        lifetime: int,
        previous_secret: str | None = None,
    ):
        async with self.database.sessions() as session:
            row = await UserRepository(session).by_username(username)
            password_hash = row.password_hash if row is not None else DUMMY_HASH
            user_id = row.id if row is not None else None
        valid = await asyncio.to_thread(PASSWORDS.verify, password, password_hash)
        if not valid or user_id is None:
            raise Unauthorized("Invalid username or password")
        secret = secrets.token_urlsafe(48)
        now = datetime.now(UTC)
        async with auth_transaction(self.database) as session:
            row = await UserRepository(session).get(user_id)
            if row is None or not row.enabled or row.password_hash != password_hash:
                raise Unauthorized("Invalid username or password")
            await session.execute(
                delete(SessionRow).where(SessionRow.expires_at <= now)
            )
            if previous_secret:
                await session.execute(
                    delete(SessionRow).where(
                        SessionRow.secret_hash == secret_hash(previous_secret)
                    )
                )
            session.add(
                SessionRow(
                    secret_hash=secret_hash(secret),
                    user_id=row.id,
                    created_at=now,
                    expires_at=now + timedelta(seconds=lifetime),
                )
            )
            user = user_from_row(row)
        return secret, Principal(
            user=user, permissions=user.permissions, csrf_token=csrf_token(secret)
        )

    async def logout(self, secret: str) -> None:
        async with self.database.sessions.begin() as session:
            await session.execute(
                delete(SessionRow).where(SessionRow.secret_hash == secret_hash(secret))
            )

    async def list_roles(self, principal, **pagination):
        if not principal.permissions.intersection(
            {Permission.ROLES_MANAGE, Permission.USERS_MANAGE}
        ):
            raise Forbidden("Permission required: roles.manage or users.manage")
        async with self.database.sessions() as session:
            rows, total = await RoleRepository(session).list(**pagination)
            return [role_from_row(row) for row in rows], total

    async def create_role(self, principal, *, name, permissions):
        require(principal, Permission.ROLES_MANAGE)
        row = RoleRow(
            id=uuid7(),
            name=name,
            permissions=sorted(permissions),
            protected=False,
            created_at=datetime.now(UTC),
        )
        async with auth_transaction(self.database) as session:
            session.add(row)
            await session.flush()
            return role_from_row(row)

    async def update_role(self, principal, id, changes):
        require(principal, Permission.ROLES_MANAGE)
        async with auth_transaction(self.database) as session:
            row = await RoleRepository(session).get(id)
            if row is None:
                raise NotFound("Role not found")
            if row.protected:
                raise Conflict("The administrator role cannot be edited")
            for key, value in changes.items():
                setattr(row, key, sorted(value) if key == "permissions" else value)
            await session.flush()
            return role_from_row(row)

    async def delete_role(self, principal, id):
        require(principal, Permission.ROLES_MANAGE)
        async with auth_transaction(self.database) as session:
            row = await RoleRepository(session).get(id)
            if row is None:
                raise NotFound("Role not found")
            if row.protected:
                raise Conflict("The administrator role cannot be deleted")
            if await session.scalar(
                select(user_roles.c.user_id).where(user_roles.c.role_id == id).limit(1)
            ):
                raise Conflict("Remove the role from users before deleting it")
            await session.delete(row)

    @staticmethod
    async def _roles(session, ids):
        rows = list(
            (await session.scalars(select(RoleRow).where(RoleRow.id.in_(ids)))).all()
        )
        if len(rows) != len(set(ids)):
            raise NotFound("Role not found")
        return rows

    async def list_users(self, principal, **pagination):
        require(principal, Permission.USERS_MANAGE)
        async with self.database.sessions() as session:
            rows, total = await UserRepository(session).list(**pagination)
            return [user_from_row(row) for row in rows], total

    async def create_user(
        self, principal, *, username, password, role_ids, enabled=True
    ):
        require(principal, Permission.USERS_MANAGE)
        password_hash = await asyncio.to_thread(PASSWORDS.hash, password)
        now = datetime.now(UTC)
        async with auth_transaction(self.database) as session:
            row = UserRow(
                id=uuid7(),
                username=username,
                password_hash=password_hash,
                enabled=enabled,
                roles=await self._roles(session, role_ids),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            return user_from_row(row)

    async def update_user(self, principal, id, changes):
        require(principal, Permission.USERS_MANAGE)
        password = changes.pop("password", None)
        password_hash = (
            await asyncio.to_thread(PASSWORDS.hash, password)
            if password is not None
            else None
        )
        async with auth_transaction(self.database) as session:
            row = await UserRepository(session).get(id)
            if row is None:
                raise NotFound("User not found")
            roles = (
                await self._roles(session, changes["role_ids"])
                if "role_ids" in changes
                else row.roles
            )
            enabled = changes.get("enabled", row.enabled)
            if (
                row.enabled
                and any(role.protected for role in row.roles)
                and not (enabled and any(role.protected for role in roles))
            ):
                admins = await session.scalar(
                    select(func.count())
                    .select_from(UserRow)
                    .join(user_roles)
                    .join(RoleRow)
                    .where(
                        UserRow.enabled.is_(True),
                        RoleRow.protected.is_(True),
                        UserRow.id != id,
                    )
                )
                if not admins:
                    raise Conflict("At least one enabled administrator must remain")
            row.roles = roles
            row.enabled = enabled
            if "username" in changes:
                row.username = changes["username"]
            if password_hash is not None:
                row.password_hash = password_hash
            row.updated_at = datetime.now(UTC)
            if password_hash is not None or not enabled:
                await session.execute(
                    delete(SessionRow).where(SessionRow.user_id == id)
                )
            if not enabled:
                await session.execute(
                    update(APIKeyRow)
                    .where(APIKeyRow.user_id == id, APIKeyRow.revoked_at.is_(None))
                    .values(revoked_at=row.updated_at)
                )
            await session.flush()
            return user_from_row(row)

    async def change_password(self, principal, *, current_password, new_password):
        if principal.key_id is not None:
            raise Forbidden("Password changes require a browser session")
        async with self.database.sessions() as session:
            row = await UserRepository(session).get(principal.user.id)
            old_hash = row.password_hash
        if not await asyncio.to_thread(PASSWORDS.verify, current_password, old_hash):
            raise InvalidInput("Current password is incorrect")
        new_hash = await asyncio.to_thread(PASSWORDS.hash, new_password)
        async with auth_transaction(self.database) as session:
            row = await UserRepository(session).get(principal.user.id)
            if not row.enabled:
                raise Unauthorized("Invalid or expired credentials")
            if row.password_hash != old_hash:
                raise Conflict("Password was changed concurrently")
            row.password_hash = new_hash
            row.updated_at = datetime.now(UTC)
            await session.execute(
                delete(SessionRow).where(SessionRow.user_id == row.id)
            )

    async def list_keys(self, principal, **pagination):
        require(principal, Permission.KEYS_MANAGE)
        async with self.database.sessions() as session:
            rows, total = await APIKeyRepository(session).list(
                principal.user.id, **pagination
            )
            return [key_from_row(row) for row in rows], total

    async def create_key(
        self, principal, *, name, permissions, function_ids=(), expires_at=None
    ):
        require(principal, Permission.KEYS_MANAGE)
        secret = "fure_" + secrets.token_urlsafe(40)
        now = datetime.now(UTC)
        if expires_at is not None and expires_at <= now:
            raise InvalidInput("Key expiration must be in the future")
        async with auth_transaction(self.database) as session:
            owner = await UserRepository(session).get(principal.user.id)
            if owner is None or not owner.enabled:
                raise Unauthorized("Invalid or expired credentials")
            allowed = user_from_row(owner).permissions.intersection(
                principal.permissions
            )
            if not set(permissions).issubset(allowed):
                raise Forbidden(
                    "API key permissions cannot exceed the owner's current permissions"
                )
            await self._validate_key_functions(session, principal, function_ids)
            row = APIKeyRow(
                id=uuid7(),
                user_id=owner.id,
                name=name,
                prefix=secret[:13],
                secret_hash=secret_hash(secret),
                permissions=sorted(permissions),
                function_ids=sorted(map(str, function_ids)),
                created_at=now,
                expires_at=expires_at,
                revoked_at=None,
            )
            session.add(row)
            await session.flush()
            return key_from_row(row), secret

    async def _validate_key_functions(self, session, principal, function_ids):
        for id in function_ids:
            require_function_access(principal, id)
        found = set(
            await session.scalars(
                select(FunctionRow.id).where(FunctionRow.id.in_(function_ids))
            )
        )
        if found != set(function_ids):
            raise NotFound("Function not found")

    async def update_key(self, principal, id, *, function_ids):
        require(principal, Permission.KEYS_MANAGE)
        async with auth_transaction(self.database) as session:
            row = await APIKeyRepository(session).get(id, principal.user.id)
            if row is None:
                raise NotFound("API key not found")
            if row.revoked_at is not None or (
                row.expires_at is not None and row.expires_at <= datetime.now(UTC)
            ):
                raise Conflict("API key is revoked or expired")
            # A restricted key cannot expand another key beyond its own scope.
            await self._validate_key_functions(session, principal, function_ids)
            row.function_ids = sorted(map(str, function_ids))
            await session.flush()
            return key_from_row(row)

    async def revoke_key(self, principal, id):
        require(principal, Permission.KEYS_MANAGE)
        async with auth_transaction(self.database) as session:
            row = await APIKeyRepository(session).get(id, principal.user.id)
            if row is None:
                raise NotFound("API key not found")
            if row.revoked_at is None:
                row.revoked_at = datetime.now(UTC)

    async def create_first_admin(self, username: str, password: str):
        if not 12 <= len(password) <= 256:
            raise InvalidInput("Password must contain 12 to 256 characters")
        password_hash = await asyncio.to_thread(PASSWORDS.hash, password)
        now = datetime.now(UTC)
        async with auth_transaction(self.database) as session:
            if await session.scalar(select(func.count()).select_from(UserRow)):
                raise Conflict(
                    "Users already exist; create additional users through the administrator API"
                )
            role = await session.scalar(
                select(RoleRow).where(RoleRow.protected.is_(True))
            )
            if role is None:
                raise Conflict("Run database migrations first")
            row = UserRow(
                id=uuid7(),
                username=username,
                password_hash=password_hash,
                enabled=True,
                roles=[role],
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()
            return user_from_row(row)
