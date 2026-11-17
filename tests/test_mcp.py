import unittest
from uuid import uuid7

import httpx2
from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from fure.api.app import create_app
from fure.settings import Settings
from tests.auth_support import bootstrap, login
from tests.database_support import isolated_database


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            Settings(database_url=self.enterContext(isolated_database()))
        )
        self.client = self.enterContext(TestClient(self.app))
        self.admin = bootstrap(self.client)

    def key(
        self, ids=(), permissions=("mcp.access", "functions.read", "functions.run")
    ):
        response = self.client.post(
            "/v1/keys",
            json={
                "name": "mcp",
                "permissions": list(permissions),
                "function_ids": list(ids),
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def function(self, name="hello", code=None, **fields):
        function = self.client.post(
            "/v1/functions", json={"name": name, "description": "Say hello", **fields}
        ).json()
        revision = self.client.post(
            "/v1/revisions",
            json={
                "function_id": function["id"],
                "implementation": {
                    "type": "python",
                    "code": code
                    or "from pydantic import BaseModel\nclass Input(BaseModel):\n    name: str\nasync def function(input: Input) -> str: return 'Hello ' + input.name",
                },
                "runner_options": {"type": "inline_python", "timeout": 2},
            },
        )
        self.assertEqual(revision.status_code, 201, revision.text)
        response = self.client.patch(
            f"/v1/functions/{function['id']}",
            json={"revision_id": revision.json()["id"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), revision.json()

    def rpc(self, key, method, params=None):
        return self.client.post(
            "/mcp/",
            headers={
                "Authorization": "Bearer " + key["secret"],
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )

    def tools(self, key):
        response = self.rpc(key, "tools/list")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["result"]["tools"]

    def call(self, key, name="hello", arguments=None):
        response = self.rpc(
            key,
            "tools/call",
            {
                "name": name,
                "arguments": arguments if arguments is not None else {"name": "world"},
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_discovery_execution_and_history(self):
        function, _ = self.function()
        self.function("hidden")
        key = self.key([function["id"]])
        initialized = self.rpc(
            key,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        self.assertEqual(initialized.status_code, 200, initialized.text)
        tools = self.tools(key)
        self.assertEqual([tool["name"] for tool in tools], ["hello"])
        self.assertEqual(tools[0]["description"], "Say hello")
        self.assertEqual(tools[0]["inputSchema"], function["input_schema"])
        result = self.call(key)["result"]
        self.assertFalse(result.get("isError", False), result)
        data = result["structuredContent"]
        self.assertEqual(data["output"], "Hello world")
        self.assertEqual(data["meta"], {})
        self.assertGreaterEqual(data["duration"], 0)
        run = self.client.get(f"/v1/runs/{data['run_id']}").json()
        self.assertEqual(run["user_id"], str(self.admin.id))
        self.assertEqual(run["api_key_id"], key["id"])
        self.assertEqual(run["input"], {"name": "world"})

    def test_fastmcp_client_over_http_isolates_keys(self):
        first, _ = self.function()
        second, _ = self.function("second")
        keys = [self.key([function["id"]]) for function in (first, second)]

        async def verify():
            import asyncio

            def transport(key):
                return StreamableHttpTransport(
                    "http://testserver/mcp/",
                    headers={"Authorization": "Bearer " + key["secret"]},
                    httpx_client_factory=lambda **kwargs: httpx2.AsyncClient(
                        transport=httpx2.ASGITransport(app=self.app), **kwargs
                    ),
                )

            async with (
                Client(transport(keys[0])) as first_client,
                Client(transport(keys[1])) as second_client,
            ):
                tools = await asyncio.gather(
                    first_client.list_tools(), second_client.list_tools()
                )
                self.assertEqual(
                    [[tool.name for tool in group] for group in tools],
                    [["hello"], ["second"]],
                )
                results = await asyncio.gather(
                    first_client.call_tool("hello", {"name": "first"}),
                    second_client.call_tool("second", {"name": "second"}),
                )
                self.assertEqual(
                    [result.structured_content["output"] for result in results],
                    ["Hello first", "Hello second"],
                )

        self.client.portal.call(verify)

    def test_http_authentication_and_permissions(self):
        function, _ = self.function()
        key = self.key([function["id"]], ["functions.read", "functions.run"])
        self.assertEqual(self.rpc(key, "tools/list").status_code, 403)
        # A browser session, including an administrator's, is not an MCP credential.
        self.assertEqual(self.client.post("/mcp/", json={}).status_code, 401)
        self.assertEqual(self.rpc({"secret": "invalid"}, "tools/list").status_code, 401)
        key = self.key([function["id"]], ["mcp.access", "functions.read"])
        self.assertEqual(len(self.tools(key)), 1)
        self.assertTrue(self.call(key)["result"]["isError"])
        key = self.key([function["id"]], ["mcp.access", "functions.run"])
        self.assertEqual(self.tools(key), [])
        self.assertEqual(
            self.call(key)["result"]["structuredContent"]["output"], "Hello world"
        )

    def test_scope_changes_rename_revocation_and_public_bypass(self):
        first, _ = self.function()
        second, _ = self.function("second", public=True)
        key = self.key([first["id"]])
        self.assertTrue(self.call(key, "second")["result"]["isError"])
        headers = {"Authorization": "Bearer " + key["secret"]}
        for endpoint in (f"/v1/functions/{second['id']}/run", "/v1/run/second"):
            self.assertEqual(
                self.client.post(
                    endpoint, json={"input": {"name": "world"}}, headers=headers
                ).status_code,
                404,
            )
        self.client.patch(f"/v1/functions/{first['id']}", json={"name": "renamed"})
        self.assertEqual([tool["name"] for tool in self.tools(key)], ["renamed"])
        self.assertEqual(
            self.call(key, "renamed")["result"]["structuredContent"]["output"],
            "Hello world",
        )
        changed = self.client.patch(
            f"/v1/keys/{key['id']}", json={"function_ids": [second["id"]]}
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertNotIn("secret", changed.json())
        self.assertEqual([tool["name"] for tool in self.tools(key)], ["second"])
        self.assertTrue(self.call(key, "renamed")["result"]["isError"])
        self.client.patch(f"/v1/keys/{key['id']}", json={"function_ids": []})
        self.assertEqual(self.tools(key), [])
        self.assertTrue(self.call(key, "second")["result"]["isError"])
        self.client.delete(f"/v1/keys/{key['id']}")
        self.assertEqual(self.rpc(key, "tools/list").status_code, 401)

    def test_disabled_deleted_and_draft_tools_are_not_exposed(self):
        active, _ = self.function()
        disabled, _ = self.function("disabled", enabled=False)
        deleted, _ = self.function("deleted")
        self.client.delete(f"/v1/functions/{deleted['id']}")
        draft = self.client.post("/v1/functions", json={"name": "draft"}).json()
        key = self.key([f["id"] for f in (active, disabled, deleted, draft)])
        self.assertEqual([tool["name"] for tool in self.tools(key)], ["hello"])
        for name in ("disabled", "deleted", "draft"):
            self.assertTrue(self.call(key, name)["result"]["isError"])

    def test_null_input_validation_and_execution_errors(self):
        function, _ = self.function(
            code="async def function(input: None) -> int: return 42"
        )
        key = self.key([function["id"]])
        self.assertEqual(self.tools(key)[0]["inputSchema"]["type"], "object")
        self.assertEqual(
            self.call(key, arguments={})["result"]["structuredContent"]["output"], 42
        )
        self.assertTrue(
            self.call(key, arguments={"unexpected": 1})["result"]["isError"]
        )
        failed, _ = self.function(
            "failed",
            code="async def function(input: None) -> str: raise ValueError('private source failure')",
        )
        self.client.patch(
            f"/v1/keys/{key['id']}", json={"function_ids": [failed["id"]]}
        )
        result = self.call(key, "failed", {})["result"]
        self.assertTrue(result["isError"])
        self.assertIn("run_id", result["structuredContent"])
        self.assertNotIn("private source failure", str(result))

    def test_rest_scope_includes_revisions_history_mutation_and_child_keys(self):
        allowed, revision = self.function()
        hidden, hidden_revision = self.function("hidden")
        own = self.client.post(
            f"/v1/functions/{allowed['id']}/run", json={"input": {"name": "world"}}
        )
        hidden_run = self.client.post(
            f"/v1/functions/{hidden['id']}/run", json={"input": {"name": "world"}}
        )
        key = self.key(
            [allowed["id"]],
            [
                "functions.read",
                "functions.run",
                "functions.update",
                "functions.delete",
                "runs.read",
                "runs.read_all",
                "runs.cancel_all",
                "keys.manage",
            ],
        )
        headers = {"Authorization": "Bearer " + key["secret"]}
        self.assertEqual(
            self.client.get("/v1/functions", headers=headers).json()["total"], 1
        )
        self.assertEqual(
            self.client.get("/v1/revisions", headers=headers).json()["total"], 1
        )
        self.assertEqual(
            self.client.get("/v1/runs", headers=headers).json()["total"], 1
        )
        for path in (
            f"/v1/functions/{hidden['id']}",
            f"/v1/revisions/{hidden_revision['id']}",
            f"/v1/runs/{hidden_run.headers['X-Run-Id']}",
        ):
            self.assertEqual(self.client.get(path, headers=headers).status_code, 404)
        self.assertEqual(
            self.client.get(
                f"/v1/revisions/{revision['id']}", headers=headers
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                f"/v1/runs/{own.headers['X-Run-Id']}", headers=headers
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                f"/v1/functions/{hidden['id']}",
                headers=headers,
                json={"description": "blocked"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(
                f"/v1/functions/{hidden['id']}", headers=headers
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/v1/functions/{hidden['id']}/undelete", headers=headers
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/v1/runs/{hidden_run.headers['X-Run-Id']}/cancel", headers=headers
            ).status_code,
            404,
        )
        child = self.client.post(
            "/v1/keys",
            headers=headers,
            json={"name": "child", "function_ids": [hidden["id"]]},
        )
        self.assertEqual(child.status_code, 404)
        child = self.client.post(
            "/v1/keys",
            headers=headers,
            json={
                "name": "child",
                "permissions": ["functions.read"],
                "function_ids": [allowed["id"]],
            },
        )
        self.assertEqual(child.status_code, 201, child.text)
        self.assertEqual(
            self.client.patch(
                f"/v1/keys/{child.json()['id']}",
                headers=headers,
                json={"function_ids": [hidden["id"]]},
            ).status_code,
            404,
        )

    def test_key_scope_validation(self):
        key = self.key()
        self.assertEqual(self.tools(key), [])
        self.assertEqual(
            self.client.patch(f"/v1/keys/{key['id']}", json={}).status_code, 422
        )
        self.assertEqual(
            self.client.patch(
                f"/v1/keys/{key['id']}", json={"function_ids": None}
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.patch(
                f"/v1/keys/{key['id']}", json={"function_ids": [str(uuid7())]}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/v1/keys", json={"name": "bad", "function_ids": [str(uuid7())]}
            ).status_code,
            404,
        )
        self.client.delete(f"/v1/keys/{key['id']}")
        self.assertEqual(
            self.client.patch(
                f"/v1/keys/{key['id']}", json={"function_ids": []}
            ).status_code,
            409,
        )

    def test_role_changes_affect_existing_mcp_key(self):
        function, _ = self.function()
        permissions = ["mcp.access", "functions.read", "functions.run", "keys.manage"]
        role = self.client.post(
            "/v1/roles", json={"name": "mcp-user", "permissions": permissions}
        ).json()
        self.client.post(
            "/v1/users",
            json={
                "username": "consumer",
                "password": "correct horse battery staple",
                "role_ids": [role["id"]],
            },
        )
        owner = TestClient(self.app)
        owner.portal = self.client.portal
        self.addCleanup(owner.close)
        login(owner, "consumer")
        key = owner.post(
            "/v1/keys",
            json={
                "name": "client",
                "permissions": permissions,
                "function_ids": [function["id"]],
            },
        ).json()
        self.assertEqual(len(self.tools(key)), 1)
        self.client.patch(
            f"/v1/roles/{role['id']}",
            json={"permissions": ["mcp.access", "functions.read", "keys.manage"]},
        )
        self.assertTrue(self.call(key)["result"]["isError"])
        self.client.patch(
            f"/v1/roles/{role['id']}",
            json={"permissions": ["functions.read", "keys.manage"]},
        )
        self.assertEqual(self.rpc(key, "tools/list").status_code, 403)
