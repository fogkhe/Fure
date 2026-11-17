from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
)

from fure.api.v1.schemas.common import RequestSchema
from fure.core.auth import Permission

type Username = Annotated[
    str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$", min_length=1, max_length=64)
]
type Password = Annotated[SecretStr, Field(min_length=12, max_length=256)]
type RoleName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]


class LoginRequest(RequestSchema):
    username: Username
    password: SecretStr = Field(min_length=1, max_length=256)


class PasswordChangeRequest(RequestSchema):
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: Password


class ChangesRequest(RequestSchema):
    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Fields cannot be null")
        return self


class RoleCreateRequest(RequestSchema):
    name: RoleName
    permissions: set[Permission] = Field(default_factory=set)


class RoleUpdateRequest(ChangesRequest):
    name: RoleName | None = None
    permissions: set[Permission] | None = None


class RoleResponse(BaseModel):
    id: UUID
    name: str
    permissions: list[Permission]
    protected: bool
    created_at: AwareDatetime


class UserCreateRequest(RequestSchema):
    username: Username
    password: Password
    role_ids: set[UUID] = Field(default_factory=set)
    enabled: bool = True


class UserUpdateRequest(ChangesRequest):
    username: Username | None = None
    password: Password | None = None
    role_ids: set[UUID] | None = None
    enabled: bool | None = None


class UserResponse(BaseModel):
    id: UUID
    username: str
    enabled: bool
    role_ids: list[UUID]
    roles: list[RoleResponse]
    permissions: list[Permission]
    created_at: AwareDatetime
    updated_at: AwareDatetime


class SessionResponse(BaseModel):
    user: UserResponse
    permissions: list[Permission]
    csrf_token: str | None


class APIKeyCreateRequest(RequestSchema):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    permissions: set[Permission] = Field(default_factory=set)
    function_ids: set[UUID] = Field(default_factory=set, max_length=1000)
    expires_at: AwareDatetime | None = None


class APIKeyUpdateRequest(ChangesRequest):
    function_ids: set[UUID] | None = Field(default=None, max_length=1000)


class APIKeyResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    prefix: str
    permissions: list[Permission]
    function_ids: list[UUID]
    created_at: AwareDatetime
    expires_at: AwareDatetime | None
    revoked_at: AwareDatetime | None


class APIKeyCreatedResponse(APIKeyResponse):
    secret: str


def role_response(role):
    return RoleResponse(
        id=role.id,
        name=role.name,
        permissions=sorted(role.permissions),
        protected=role.protected,
        created_at=role.created_at,
    )


def user_response(user):
    return UserResponse(
        id=user.id,
        username=user.username,
        enabled=user.enabled,
        role_ids=[role.id for role in user.roles],
        roles=[role_response(role) for role in user.roles],
        permissions=sorted(user.permissions),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def session_response(principal):
    return SessionResponse(
        user=user_response(principal.user),
        permissions=sorted(principal.permissions),
        csrf_token=principal.csrf_token,
    )


def key_response(key):
    return APIKeyResponse(
        **{
            name: getattr(key, name)
            for name in APIKeyResponse.model_fields
            if name not in {"permissions", "function_ids"}
        },
        permissions=sorted(key.permissions),
        function_ids=sorted(key.function_ids),
    )
