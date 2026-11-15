from abc import ABC, abstractmethod

from fure.core.types import JSONSchema


class BaseImplementation(ABC):
    __slots__ = ()

    @property
    @abstractmethod
    def input_schema(self) -> JSONSchema: ...

    @property
    @abstractmethod
    def output_schema(self) -> JSONSchema: ...
