from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Permission(StrEnum):
    FUNCTIONS_READ = "functions.read"
    FUNCTIONS_CREATE = "functions.create"
    FUNCTIONS_UPDATE = "functions.update"
    FUNCTIONS_DELETE = "functions.delete"
    FUNCTIONS_PUBLISH = "functions.publish"
    FUNCTIONS_RUN = "functions.run"
    RUNS_READ = "runs.read"
    RUNS_READ_ALL = "runs.read_all"
    RUNS_CANCEL = "runs.cancel"
    RUNS_CANCEL_ALL = "runs.cancel_all"
    USERS_MANAGE = "users.manage"
    ROLES_MANAGE = "roles.manage"
    KEYS_MANAGE = "keys.manage"


@dataclass(frozen=True, slots=True, kw_only=True)
class Role:
    id: UUID
    name: str
    permissions: frozenset[Permission]
    protected: bool
    created_at: datetime

    @classmethod
    def restore(cls, **state):
        return cls(**state)


@dataclass(frozen=True, slots=True, kw_only=True)
class User:
    id: UUID
    username: str
    enabled: bool
    roles: tuple[Role, ...]
    created_at: datetime
    updated_at: datetime

    @property
    def permissions(self) -> frozenset[Permission]:
        return frozenset(
            permission for role in self.roles for permission in role.permissions
        )

    @classmethod
    def restore(cls, **state):
        return cls(**state)


@dataclass(frozen=True, slots=True, kw_only=True)
class APIKey:
    id: UUID
    user_id: UUID
    name: str
    prefix: str
    permissions: frozenset[Permission]
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def restore(cls, **state):
        return cls(**state)


@dataclass(frozen=True, slots=True, kw_only=True)
class Principal:
    user: User
    permissions: frozenset[Permission]
    key_id: UUID | None = None
    csrf_token: str | None = None

    def allows(self, permission: Permission) -> bool:
        return permission in self.permissions
