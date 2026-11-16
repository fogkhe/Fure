import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self
from uuid import UUID, uuid7

from fure.core.types import JSONSchema
from fure.utils.datetime import normalize_datetime

FUNCTION_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
FUNCTION_DESCRIPTION_MAX_LENGTH = 1000

if TYPE_CHECKING:
    from fure.core.revision import Revision


class Function:
    __slots__ = (
        "_created_at",
        "_deleted_at",
        "_description",
        "_enabled",
        "_id",
        "_name",
        "_public",
        "_revision",
        "_updated_at",
    )

    def __init__(
        self,
        name: str,
        description: str | None = None,
        revision: Revision | None = None,
        *,
        id: UUID | None = None,
        enabled: bool | None = None,
        public: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        deleted_at: datetime | None = None,
    ) -> None:
        self._validate_name(name)
        self._validate_description(description)

        self._id = id if id is not None else uuid7()
        self._name = name
        self._description = description
        self._revision = revision
        self._enabled = enabled if enabled is not None else True
        self._public = public
        self._created_at = normalize_datetime(
            created_at if created_at is not None else datetime.now(UTC)
        )
        self._updated_at = (
            normalize_datetime(updated_at)
            if updated_at is not None
            else self._created_at
        )
        self._deleted_at = (
            normalize_datetime(deleted_at) if deleted_at is not None else None
        )

    @classmethod
    def restore(
        cls,
        *,
        id: UUID,
        name: str,
        description: str | None,
        revision: Revision | None,
        enabled: bool,
        created_at: datetime,
        updated_at: datetime,
        deleted_at: datetime | None,
        public: bool = False,
    ) -> Self:
        function = cls.__new__(cls)
        function._id = id
        function._name = name
        function._description = description
        function._revision = revision
        function._enabled = enabled
        function._public = public
        function._created_at = created_at
        function._updated_at = updated_at
        function._deleted_at = deleted_at
        return function

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if self._name == value:
            return

        self._validate_name(value)
        self._name = value
        self._update()

    @property
    def description(self) -> str | None:
        return self._description

    @description.setter
    def description(self, value: str | None) -> None:
        if self._description == value:
            return

        self._validate_description(value)
        self._description = value
        self._update()

    @property
    def revision(self) -> Revision | None:
        return self._revision

    @property
    def input_schema(self) -> JSONSchema:
        return deepcopy(
            self._revision.implementation.input_schema
            if self._revision is not None
            else {}
        )

    @property
    def output_schema(self) -> JSONSchema:
        return deepcopy(
            self._revision.implementation.output_schema
            if self._revision is not None
            else {}
        )

    @revision.setter
    def revision(self, value: Revision) -> None:
        if self._revision == value:
            return

        self._revision = value
        self._update()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def public(self) -> bool:
        return self._public

    @public.setter
    def public(self, value: bool) -> None:
        if self._public != value:
            self._public = value
            self._update()

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def deleted_at(self) -> datetime | None:
        return self._deleted_at

    @property
    def deleted(self) -> bool:
        return self._deleted_at is not None

    @property
    def runnable(self) -> bool:
        return self._enabled and not self.deleted and self.revision is not None

    def enable(self) -> None:
        if self._enabled:
            return

        self._enabled = True
        self._update()

    def disable(self) -> None:
        if not self._enabled:
            return

        self._enabled = False
        self._update()

    def delete(self) -> None:
        if self.deleted:
            return

        self._deleted_at = normalize_datetime(datetime.now(UTC))
        self._update()

    def undelete(self) -> None:
        if not self.deleted:
            return

        self._deleted_at = None
        self._update()

    def _update(self) -> None:
        self._updated_at = normalize_datetime(datetime.now(UTC))

    @staticmethod
    def _validate_name(value: str) -> None:
        if not FUNCTION_NAME_PATTERN.fullmatch(value):
            raise ValueError(
                f"function name must match the pattern "
                f"{FUNCTION_NAME_PATTERN.pattern!r}",
            )

    @staticmethod
    def _validate_description(value: str | None) -> None:
        if value is None:
            return

        if len(value) > FUNCTION_DESCRIPTION_MAX_LENGTH:
            raise ValueError(
                f"function description must have a maximum length of "
                f"{FUNCTION_DESCRIPTION_MAX_LENGTH}",
            )
