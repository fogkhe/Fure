from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, JsonValue, model_validator

from fure.api.v1.schemas.common import (
    FunctionDescription,
    FunctionName,
    PaginationRequest,
    RequestSchema,
)


class FunctionCreateRequest(RequestSchema):
    name: FunctionName
    description: FunctionDescription | None = None
    enabled: bool = True


class FunctionUpdateRequest(RequestSchema):
    name: FunctionName | None = None
    description: FunctionDescription | None = None
    revision_id: UUID | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        for field in ("name", "revision_id", "enabled"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"'{field}' cannot be null")
        return self


class FunctionListRequest(PaginationRequest):
    name: FunctionName | None = None
    enabled: bool | None = None
    deleted: bool = False


class FunctionResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    revision_id: UUID | None
    enabled: bool
    deleted: bool
    runnable: bool
    input_schema: dict[str, JsonValue]
    output_schema: dict[str, JsonValue]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    deleted_at: AwareDatetime | None
