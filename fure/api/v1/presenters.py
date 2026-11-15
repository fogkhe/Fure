from fure.api.v1.schemas import FunctionResponse, RevisionResponse, RunDetailResponse
from fure.database.mappers import implementation_to_data, options_to_data


def function_response(function):
    return FunctionResponse(
        id=function.id,
        name=function.name,
        description=function.description,
        revision_id=function.revision.id if function.revision else None,
        enabled=function.enabled,
        deleted=function.deleted,
        runnable=function.runnable,
        input_schema=function.input_schema,
        output_schema=function.output_schema,
        created_at=function.created_at,
        updated_at=function.updated_at,
        deleted_at=function.deleted_at,
    )


def revision_response(revision):
    options = options_to_data(revision.runner_options)
    options.pop("api_key", None)
    return RevisionResponse(
        id=revision.id,
        function_id=revision.function.id,
        implementation=implementation_to_data(revision.implementation),
        runner_options=options,
        created_at=revision.created_at,
    )


def run_response(run):
    return RunDetailResponse(
        id=run.id,
        function_id=run.revision.function.id,
        revision_id=run.revision.id,
        input=run.input,
        status=run.status,
        output=run.output,
        meta=run.meta,
        duration=run.duration,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
