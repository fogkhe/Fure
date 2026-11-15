from dataclasses import asdict

from fure.core.function import Function
from fure.core.implementations import JinjaImplementation, PythonImplementation
from fure.core.implementations.base import BaseImplementation
from fure.core.revision import Revision
from fure.core.run import (
    BaseRunMeta,
    CancelRunMeta,
    ErrorRunMeta,
    FailRunMeta,
    Run,
    RunStatus,
    SucceedRunMeta,
)
from fure.core.runners.base import BaseRunnerOptions
from fure.core.runners.jinja.openai import OpenAIJinjaRunMeta, OpenAIJinjaRunnerOptions
from fure.core.runners.python.base import BasePythonRunnerOptions
from fure.core.runners.python.inline import (
    InlinePythonRunMeta,
    InlinePythonRunnerOptions,
)
from fure.database.models import FunctionRow, RevisionRow, RunRow


def implementation_to_data(implementation: BaseImplementation) -> dict:
    schemas = {
        "input_schema": implementation.input_schema,
        "output_schema": implementation.output_schema,
    }
    if isinstance(implementation, PythonImplementation):
        return {"type": "python", "code": implementation.code, **schemas}
    if isinstance(implementation, JinjaImplementation):
        return {"type": "jinja", "template": implementation.template, **schemas}
    raise TypeError("Unsupported implementation type")


def implementation_from_data(data: dict) -> BaseImplementation:
    fields = {key: value for key, value in data.items() if key != "type"}
    if data["type"] == "python":
        return PythonImplementation.restore(**fields)
    if data["type"] == "jinja":
        return JinjaImplementation.restore(**fields)
    raise ValueError("Unknown stored implementation type")


def options_to_data(options: BaseRunnerOptions) -> dict:
    if isinstance(options, OpenAIJinjaRunnerOptions):
        return {"type": "openai_jinja", **asdict(options)}
    if isinstance(options, BasePythonRunnerOptions):
        return {"type": "inline_python", "timeout": options.timeout}
    raise TypeError("Unsupported runner options type")


def options_from_data(data: dict) -> BaseRunnerOptions:
    fields = {key: value for key, value in data.items() if key != "type"}
    if data["type"] == "openai_jinja":
        return OpenAIJinjaRunnerOptions(**fields)
    if data["type"] == "inline_python":
        return InlinePythonRunnerOptions(**fields)
    raise ValueError("Unknown stored runner type")


META_TYPES = {
    "openai_jinja": OpenAIJinjaRunMeta,
    "inline_python": InlinePythonRunMeta,
    "error": ErrorRunMeta,
    "fail": FailRunMeta,
    "cancel": CancelRunMeta,
    "succeed": SucceedRunMeta,
}


def meta_to_data(meta: BaseRunMeta | None) -> dict | None:
    if meta is None:
        return None
    for kind, cls in META_TYPES.items():
        if type(meta) is cls:
            return {"type": kind, **asdict(meta)}
    raise TypeError("Unsupported run metadata type")


def meta_from_data(data: dict | None) -> BaseRunMeta | None:
    if data is None:
        return None
    cls = META_TYPES[data["type"]]
    return cls(**{key: value for key, value in data.items() if key != "type"})


def function_from_row(row: FunctionRow, *, include_revision=True) -> Function:
    function = Function.restore(
        id=row.id,
        name=row.name,
        description=row.description,
        revision=None,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )
    if include_revision and row.revision is not None:
        # A trusted mapper wires the cyclic object graph without invoking the setter.
        function._revision = revision_from_row(row.revision, function)
    return function


def revision_from_row(row: RevisionRow, function: Function | None = None) -> Revision:
    owner = (
        function
        if function is not None
        else function_from_row(row.function, include_revision=False)
    )
    return Revision.restore(
        id=row.id,
        function=owner,
        implementation=implementation_from_data(row.implementation),
        runner_options=options_from_data(row.runner_options),
        created_at=row.created_at,
    )


def run_from_row(row: RunRow) -> Run:
    return Run.restore(
        id=row.id,
        revision=revision_from_row(row.revision),
        input=row.input,
        status=RunStatus(row.status),
        output=row.output,
        meta=meta_from_data(row.meta),
        duration=row.duration,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
