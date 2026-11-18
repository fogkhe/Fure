import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import httpx2
from fastapi.testclient import TestClient
from openai import APIConnectionError

from fure.api.app import create_app
from fure.core.implementations import PythonImplementation
from fure.core.runners import OpenAIJinjaRunMeta, RunResult
from fure.settings import Settings
from tests.auth_support import bootstrap, login
from tests.database_support import isolated_database

MISSING_ID = "01900000-0000-7000-8000-000000000099"


class APITests(unittest.TestCase):
    def setUp(self):
        url = self.enterContext(isolated_database())
        self.settings = Settings(
            database_url=url,
            execution_heartbeat_interval=0.05,
        )
        self.app = create_app(self.settings)
        self.client = self.enterContext(TestClient(self.app))
        bootstrap(self.client)

    def function(self, name="greet", **fields):
        response = self.client.post("/v1/functions", json={"name": name, **fields})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def revision(
        self,
        function_id,
        code="async def function(input: None) -> str: return 'hello'",
        *,
        timeout=5,
        activate=True,
    ):
        response = self.client.post(
            "/v1/revisions",
            json={
                "function_id": function_id,
                "implementation": {"type": "python", "code": code},
                "runner_options": {"type": "inline_python", "timeout": timeout},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        revision = response.json()
        if activate:
            selected = self.client.patch(
                f"/v1/functions/{function_id}", json={"revision_id": revision["id"]}
            )
            self.assertEqual(selected.status_code, 200, selected.text)
        return revision

    def test_schema_docs_and_health(self):
        schema = self.client.get("/openapi.json").json()
        expected = {
            "/v1/functions",
            "/v1/functions/{function_id}",
            "/v1/functions/{function_id}/undelete",
            "/v1/functions/{function_id}/run",
            "/v1/revisions",
            "/v1/revisions/{revision_id}",
            "/v1/runs",
            "/v1/runs/{run_id}",
            "/v1/runs/{run_id}/cancel",
            "/v1/run/{function_name}",
        }
        self.assertTrue(expected.issubset(schema["paths"]))
        for path in expected:
            for operation in schema["paths"][path].values():
                self.assertNotIn("501", operation["responses"])
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_uuid_execution_and_name_alias_share_current_revision_and_access_rules(
        self,
    ):
        function = self.function()
        self.revision(function["id"])
        endpoint = f"/v1/functions/{function['id']}/run"
        for path in (endpoint, "/v1/run/greet"):
            response = self.client.post(path, json={})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["output"], "hello")
            self.assertIn("X-Run-Id", response.headers)
        self.client.patch(f"/v1/functions/{function['id']}", json={"name": "renamed"})
        self.assertEqual(self.client.post(endpoint, json={}).json()["output"], "hello")
        self.assertEqual(self.client.post("/v1/run/greet", json={}).status_code, 404)
        self.assertEqual(self.client.post("/v1/run/renamed", json={}).status_code, 200)
        self.client.patch(f"/v1/functions/{function['id']}", json={"enabled": False})
        self.assertEqual(self.client.post(endpoint, json={}).status_code, 409)
        self.client.delete(f"/v1/functions/{function['id']}")
        self.assertEqual(self.client.post(endpoint, json={}).status_code, 404)

    def _wait_terminal(self, id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = self.client.get(f"/v1/runs/{id}")
            self.assertEqual(response.status_code, 200, response.text)
            record = response.json()
            if record["status"] not in {"pending", "running"}:
                return record
            time.sleep(0.01)
        self.fail("Run did not finish")

    def test_async_execution_returns_an_id_before_completion_and_uses_existing_cancel(
        self,
    ):
        function = self.function()
        self.revision(
            function["id"],
            "import asyncio\nasync def function(input: None) -> str:\n    await asyncio.sleep(60)\n    return 'late'",
            timeout=None,
        )
        endpoint = f"/v1/functions/{function['id']}/run?wait=false"
        response = self.client.post(endpoint, json={})
        self.assertEqual(response.status_code, 202, response.text)
        record = response.json()
        self.assertIn(record["status"], {"pending", "running"})
        self.assertEqual(record["id"], response.headers["X-Run-Id"])
        self.assertEqual(self._wait_running(self.client), record["id"])
        cancelled = self.client.post(f"/v1/runs/{record['id']}/cancel")
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertEqual(self._wait_terminal(record["id"])["status"], "cancelled")
        self.assertEqual(
            self.client.post(f"/v1/runs/{record['id']}/cancel").status_code, 409
        )

    def test_async_completion_and_failure_are_persisted_for_both_routes(self):
        function = self.function()
        for path in (f"/v1/functions/{function['id']}/run", "/v1/run/greet"):
            for code, expected_status in (
                ("async def function(input: None) -> int: return 42", "succeeded"),
                (
                    "async def function(input: None) -> int: raise ValueError('failed')",
                    "failed",
                ),
            ):
                self.revision(function["id"], code)
                response = self.client.post(path, params={"wait": "false"}, json={})
                self.assertEqual(response.status_code, 202, response.text)
                record = self._wait_terminal(response.json()["id"])
                self.assertEqual(record["status"], expected_status)
                self.assertEqual(record["function_id"], function["id"])
                if expected_status == "succeeded":
                    self.assertEqual(record["output"], 42)
                    self.assertEqual(record["meta"], {})
                else:
                    self.assertEqual(record["meta"]["code"], "execution_error")

    def test_async_execution_requires_readable_history_and_sync_public_execution_remains_available(
        self,
    ):
        function = self.function(public=True)
        self.revision(function["id"])
        endpoint = f"/v1/functions/{function['id']}/run"
        key = self.client.post(
            "/v1/keys",
            json={
                "name": "run-only",
                "permissions": ["functions.run"],
                "function_ids": [function["id"]],
            },
        ).json()["secret"]
        headers = {"Authorization": f"Bearer {key}"}
        for path in (endpoint, "/v1/run/greet"):
            self.assertEqual(
                self.client.post(
                    path, params={"wait": "false"}, json={}, headers=headers
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.post(path, json={}, headers=headers).status_code, 200
            )
        # The rejected submissions must not have created any runs.
        self.assertEqual(self.client.get("/v1/runs").json()["total"], 2)
        self.client.cookies.clear()
        for path in (endpoint, "/v1/run/greet"):
            self.assertEqual(
                self.client.post(path, params={"wait": "false"}, json={}).status_code,
                401,
            )
            self.assertEqual(self.client.post(path, json={}).status_code, 200)

    def test_function_name_search_is_case_insensitive_and_treats_underscores_literally(
        self,
    ):
        self.function("pre-GREET_alpha")
        self.function("pre_greet_beta", enabled=False)
        self.function("pre-greetXalpha")

        names = []
        for page in (0, 1):
            response = self.client.get(
                "/v1/functions", params={"name": "Greet_", "size": 1, "page": page}
            )
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["total"], 2)
            names.extend(item["name"] for item in result["items"])
        self.assertCountEqual(names, ["pre-GREET_alpha", "pre_greet_beta"])

        enabled = self.client.get(
            "/v1/functions", params={"name": "Greet_", "enabled": True}
        ).json()
        self.assertEqual(enabled["total"], 1)
        self.assertEqual(enabled["items"][0]["name"], "pre-GREET_alpha")

    def test_function_crud_filters_pagination_and_name_reuse(self):
        first = self.function(description="old")
        self.assertFalse(first["runnable"])
        self.function("other", enabled=False)
        self.assertEqual(
            self.client.post("/v1/functions", json={"name": "greet"}).status_code, 409
        )
        page = self.client.get("/v1/functions?size=1&page=0").json()
        self.assertEqual(page["total"], 2)
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(
            self.client.get("/v1/functions?enabled=false").json()["total"], 1
        )
        self.assertEqual(self.client.get("/v1/functions?name=greet").json()["total"], 1)
        updated = self.client.patch(
            f"/v1/functions/{first['id']}",
            json={"name": "renamed", "description": None, "enabled": False},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertIsNone(updated.json()["description"])
        self.assertFalse(updated.json()["enabled"])
        self.assertEqual(
            self.client.delete(f"/v1/functions/{first['id']}").status_code, 204
        )
        self.assertEqual(self.client.get("/v1/functions").json()["total"], 1)
        self.assertEqual(
            self.client.get("/v1/functions?deleted=true").json()["total"], 1
        )
        replacement = self.function("renamed")
        self.assertEqual(
            self.client.post(f"/v1/functions/{first['id']}/undelete").status_code, 409
        )
        self.client.delete(f"/v1/functions/{replacement['id']}")
        restored = self.client.post(f"/v1/functions/{first['id']}/undelete")
        self.assertEqual(restored.status_code, 200)
        self.assertFalse(restored.json()["deleted"])
        self.assertFalse(restored.json()["enabled"])

    def test_revision_selection_history_and_ownership(self):
        function = self.function()
        first = self.revision(function["id"], activate=False)
        self.assertIsNone(
            self.client.get(f"/v1/functions/{function['id']}").json()["revision_id"]
        )
        self.client.patch(
            f"/v1/functions/{function['id']}", json={"revision_id": first["id"]}
        )
        run = self.client.post("/v1/run/greet", json={})
        self.assertEqual(run.status_code, 200)
        run_id = run.headers["X-Run-Id"]
        second = self.revision(
            function["id"], "async def function(input: None) -> int: return 42"
        )
        self.assertEqual(
            self.client.post("/v1/run/greet", json={}).json()["output"], 42
        )
        self.assertEqual(
            self.client.get(f"/v1/runs/{run_id}").json()["revision_id"], first["id"]
        )
        versions = self.client.get(f"/v1/revisions?function_id={function['id']}").json()
        self.assertEqual(
            [item["id"] for item in versions["items"]], [second["id"], first["id"]]
        )
        other = self.function("other")
        self.assertEqual(
            self.client.patch(
                f"/v1/functions/{other['id']}", json={"revision_id": first["id"]}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.get(f"/v1/revisions/{first['id']}").status_code, 200
        )
        self.assertEqual(
            self.client.patch(f"/v1/revisions/{first['id']}", json={}).status_code, 405
        )

    def test_python_execution_validation_failures_and_timeouts_are_recorded(self):
        function = self.function()
        code = "from pydantic import BaseModel\nclass Input(BaseModel):\n    value: int\nasync def function(input: Input) -> int: return input.value + 1"
        revision = self.revision(function["id"], code)
        response = self.client.post("/v1/run/greet", json={"input": {"value": 4}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["output"], 5)
        self.assertEqual(response.json()["meta"], {})
        self.assertGreaterEqual(response.json()["duration"], 0)
        detail = self.client.get("/v1/runs/" + response.headers["X-Run-Id"]).json()
        self.assertEqual(detail["status"], "succeeded")
        self.assertEqual(detail["revision_id"], revision["id"])
        self.assertIsNotNone(detail["finished_at"])
        invalid = self.client.post("/v1/run/greet", json={"input": {}})
        self.assertEqual(invalid.status_code, 422)
        failure = self.client.get("/v1/runs/" + invalid.headers["X-Run-Id"]).json()
        self.assertEqual(failure["status"], "failed")
        self.assertEqual(failure["meta"]["code"], "invalid_input")
        self.revision(
            function["id"], "async def function(input: None) -> int: return 'bad'"
        )
        failed = self.client.post("/v1/run/greet", json={})
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(
            self.client.get("/v1/runs/" + failed.headers["X-Run-Id"]).json()["meta"][
                "code"
            ],
            "execution_error",
        )
        self.revision(
            function["id"],
            "import asyncio\nasync def function(input: None) -> str:\n    await asyncio.sleep(10)\n    return 'late'",
            timeout=0.02,
        )
        timed_out = self.client.post("/v1/run/greet", json={})
        self.assertEqual(timed_out.status_code, 504)
        timed_record = self.client.get(
            "/v1/runs/" + timed_out.headers["X-Run-Id"]
        ).json()
        self.assertEqual(timed_record["meta"]["code"], "timeout")
        self.assertIsNotNone(timed_record["finished_at"])
        history = self.client.get(
            f"/v1/runs?function_id={function['id']}&status=failed"
        ).json()
        self.assertEqual(history["total"], 3)
        self.assertEqual(
            self.client.get(f"/v1/runs?revision_id={revision['id']}").json()["total"], 2
        )

    def test_missing_disabled_deleted_and_unversioned_functions(self):
        self.assertEqual(self.client.post("/v1/run/missing", json={}).status_code, 404)
        function = self.function()
        self.assertEqual(self.client.post("/v1/run/greet", json={}).status_code, 409)
        self.revision(function["id"])
        self.client.patch(f"/v1/functions/{function['id']}", json={"enabled": False})
        self.assertEqual(self.client.post("/v1/run/greet", json={}).status_code, 409)
        self.client.delete(f"/v1/functions/{function['id']}")
        self.assertEqual(self.client.post("/v1/run/greet", json={}).status_code, 404)
        self.assertEqual(
            self.client.patch(
                f"/v1/functions/{function['id']}", json={"enabled": True}
            ).status_code,
            409,
        )
        for path in (
            f"/v1/functions/{MISSING_ID}",
            f"/v1/revisions/{MISSING_ID}",
            f"/v1/runs/{MISSING_ID}",
        ):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(
            self.client.post(f"/v1/runs/{MISSING_ID}/cancel").status_code, 404
        )

    def test_concurrent_function_creation_has_one_winner(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self.client.post, "/v1/functions", json={"name": "same"})
                for _ in range(2)
            ]
            codes = sorted(future.result(timeout=5).status_code for future in futures)
        self.assertEqual(codes, [201, 409])
        self.assertEqual(self.client.get("/v1/functions?name=same").json()["total"], 1)

    def test_nonfinite_outputs_are_failed_before_success_is_saved(self):
        function = self.function()
        self.revision(
            function["id"],
            "async def function(input: None) -> float: return float('nan')",
        )
        response = self.client.post("/v1/run/greet", json={})
        self.assertEqual(response.status_code, 500)
        record = self.client.get("/v1/runs/" + response.headers["X-Run-Id"]).json()
        self.assertEqual(record["status"], "failed")
        self.assertIsNone(record["output"])

    def test_invalid_definitions_and_payloads_do_not_create_revisions(self):
        function = self.function()
        for implementation, options in (
            ({"type": "python", "code": "bad syntax!"}, {"type": "inline_python"}),
            (
                {"type": "jinja", "template": "{{ broken"},
                {
                    "type": "openai_jinja",
                    "base_url": "http://localhost:11434/v1",
                    "model": "test",
                },
            ),
            ({"type": "jinja", "template": "hello"}, {"type": "inline_python"}),
        ):
            response = self.client.post(
                "/v1/revisions",
                json={
                    "function_id": function["id"],
                    "implementation": implementation,
                    "runner_options": options,
                },
            )
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get("/v1/revisions").json()["total"], 0)
        for payload in ({}, {"enabled": None}, {"revision_id": None}):
            self.assertEqual(
                self.client.patch(
                    f"/v1/functions/{function['id']}", json=payload
                ).status_code,
                422,
            )
        self.assertEqual(
            self.client.post("/v1/functions", json={"name": "bad name"}).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/v1/functions", json={"name": "x", "input_schema": {}}
            ).status_code,
            422,
        )
        self.assertEqual(self.client.get("/v1/runs?size=1001").status_code, 422)
        self.assertEqual(self.client.get("/v1/runs?status=unknown").status_code, 422)

    def test_openai_metadata_credentials_and_provider_failures(self):
        function = self.function()
        revision = self.client.post(
            "/v1/revisions",
            json={
                "function_id": function["id"],
                "implementation": {"type": "jinja", "template": "Hello, {{ name }}!"},
                "runner_options": {
                    "type": "openai_jinja",
                    "base_url": "http://localhost:11434/v1",
                    "model": "test",
                    "api_key": "private-key",
                    "timeout": 5,
                },
            },
        )
        self.assertEqual(revision.status_code, 201, revision.text)
        self.assertNotIn("api_key", revision.json()["runner_options"])
        self.assertNotIn("private-key", revision.text)
        self.client.patch(
            f"/v1/functions/{function['id']}",
            json={"revision_id": revision.json()["id"]},
        )
        result = RunResult(
            output="Hello!", meta=OpenAIJinjaRunMeta(10, 261, 271), duration=0.223
        )
        with patch(
            "fure.services.execution.OpenAIJinjaRunner.run",
            new=AsyncMock(return_value=result),
        ) as execute:
            response = self.client.post(
                "/v1/run/greet", json={"input": {"name": "world"}}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(
                response.json()["meta"],
                {"input_tokens": 10, "output_tokens": 261, "total_tokens": 271},
            )
            self.assertEqual(execute.await_count, 1)
        detail = self.client.get("/v1/runs/" + response.headers["X-Run-Id"]).json()
        self.assertEqual(detail["meta"], response.json()["meta"])
        with patch(
            "fure.services.execution.OpenAIJinjaRunner.run",
            new=AsyncMock(
                side_effect=APIConnectionError(
                    request=httpx2.Request("POST", "http://provider.test")
                )
            ),
        ):
            failure = self.client.post(
                "/v1/run/greet", json={"input": {"name": "world"}}
            )
            self.assertEqual(failure.status_code, 502)
            self.assertNotIn("private-key", failure.text)
        self.assertEqual(self.client.get("/v1/runs?status=failed").json()["total"], 1)

    def test_saved_state_survives_restart_and_reads_do_not_execute_code(self):
        function = self.function()
        revision = self.revision(function["id"])
        response = self.client.post("/v1/run/greet", json={})
        run_id = response.headers["X-Run-Id"]
        with (
            TestClient(create_app(self.settings)) as other,
            patch.object(
                PythonImplementation,
                "_inspect",
                side_effect=AssertionError("read executed code"),
            ),
        ):
            login(other)
            for path in (
                "/v1/functions",
                f"/v1/functions/{function['id']}",
                "/v1/revisions",
                f"/v1/revisions/{revision['id']}",
                "/v1/runs",
                f"/v1/runs/{run_id}",
            ):
                self.assertEqual(other.get(path).status_code, 200)

    def _wait_running(self, client):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            items = client.get("/v1/runs?status=running").json()["items"]
            if items:
                return items[0]["id"]
            time.sleep(0.01)
        self.fail("Run did not start")

    def test_cancellation_between_workers_and_terminal_state_protection(self):
        function = self.function()
        self.revision(
            function["id"],
            "import asyncio\nasync def function(input: None) -> str:\n    await asyncio.sleep(10)\n    return 'late'",
            timeout=3,
        )
        with (
            TestClient(create_app(self.settings)) as other,
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            login(other)
            future = pool.submit(self.client.post, "/v1/run/greet", json={})
            id = self._wait_running(other)
            cancelled = other.post(f"/v1/runs/{id}/cancel")
            self.assertEqual(cancelled.status_code, 200, cancelled.text)
            self.assertEqual(cancelled.json()["status"], "cancelled")
            self.assertEqual(future.result(timeout=5).status_code, 409)
            self.assertEqual(other.post(f"/v1/runs/{id}/cancel").status_code, 409)
            self.assertEqual(other.get(f"/v1/runs/{id}").json()["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
