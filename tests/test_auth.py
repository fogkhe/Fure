import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

from fastapi.testclient import TestClient
from sqlalchemy import select

from fure.api.app import create_app
from fure.core.run import Run
from fure.database.models import APIKeyRow, SessionRow, UserRow
from fure.database.repositories import FunctionRepository, RunRepository
from fure.services.auth import AuthService
from fure.services.errors import Conflict
from fure.settings import Settings
from tests.auth_support import PASSWORD, bootstrap, login
from tests.database_support import isolated_database


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            Settings(database_url=self.enterContext(isolated_database()))
        )
        self.client = self.enterContext(TestClient(self.app))
        self.admin = bootstrap(self.client)

    def anonymous(self):
        # Share the running app's portal; no second lifespan on the same object.
        client = TestClient(self.app)
        client.portal = self.client.portal
        self.addCleanup(client.close)
        return client

    def role(self, permissions, name="custom"):
        response = self.client.post(
            "/v1/roles", json={"name": name, "permissions": permissions}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def user(self, username="consumer", roles=()):
        response = self.client.post(
            "/v1/users",
            json={"username": username, "password": PASSWORD, "role_ids": list(roles)},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def key(self, client=None, permissions=(), **fields):
        response = (client or self.client).post(
            "/v1/keys",
            json={"name": "integration", "permissions": list(permissions), **fields},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def function(self, public=False, name="hello"):
        function = self.client.post(
            "/v1/functions", json={"name": name, "public": public}
        ).json()
        revision = self.client.post(
            "/v1/revisions",
            json={
                "function_id": function["id"],
                "implementation": {
                    "type": "python",
                    "code": "async def function(input: None) -> str: return 'hello'",
                },
                "runner_options": {"type": "inline_python", "timeout": 10},
            },
        )
        self.assertEqual(revision.status_code, 201, revision.text)
        self.client.patch(
            f"/v1/functions/{function['id']}",
            json={"revision_id": revision.json()["id"]},
        )
        return function

    def test_authentication_csrf_and_logout(self):
        guest = self.anonymous()
        self.assertEqual(guest.get("/v1/functions").status_code, 401)
        self.assertEqual(guest.get("/health").status_code, 200)
        self.assertEqual(
            guest.post(
                "/v1/auth/login", json={"username": "admin", "password": PASSWORD}
            ).status_code,
            403,
        )
        failed = guest.post(
            "/v1/auth/login",
            json={"username": "missing", "password": "bad"},
            headers={"X-Fure-Client": "web"},
        )
        self.assertEqual(failed.status_code, 401)
        login(guest)
        self.assertTrue(guest.cookies.get("fure_session"))
        cookie = next(
            cookie for cookie in guest.cookies.jar if cookie.name == "fure_session"
        )
        self.assertIn("HttpOnly", cookie._rest)
        self.assertEqual(cookie._rest["SameSite"], "lax")
        csrf = guest.headers.pop("X-CSRF-Token")
        self.assertEqual(
            guest.post("/v1/functions", json={"name": "csrf"}).status_code, 403
        )
        guest.headers["X-CSRF-Token"] = csrf
        self.assertEqual(guest.post("/v1/auth/logout").status_code, 204)
        self.assertEqual(guest.get("/v1/auth/me").status_code, 401)

    def test_roles_are_combined_and_request_permissions_are_enforced(self):
        read = self.role(["functions.read"], "read")
        run = self.role(["functions.run", "runs.read", "keys.manage"], "run")
        user = self.user(roles=[read["id"], run["id"]])
        client = self.anonymous()
        me = login(client, user["username"])
        self.assertEqual(
            set(me["permissions"]),
            {"functions.read", "functions.run", "runs.read", "keys.manage"},
        )
        self.assertEqual(client.get("/v1/functions").status_code, 200)
        for path in ("/v1/users", "/v1/roles"):
            self.assertEqual(client.get(path).status_code, 403)
        self.assertEqual(
            client.post("/v1/functions", json={"name": "blocked"}).status_code, 403
        )
        self.assertEqual(
            self.client.patch(
                f"/v1/roles/{read['id']}", json={"permissions": []}
            ).status_code,
            200,
        )
        self.assertEqual(client.get("/v1/functions").status_code, 403)
        self.assertEqual(self.client.delete(f"/v1/roles/{run['id']}").status_code, 409)

    def test_api_key_permissions_intersection_revocation_and_no_secret_disclosure(self):
        role = self.role(["functions.read", "keys.manage"])
        user = self.user(roles=[role["id"]])
        owner = self.anonymous()
        login(owner, user["username"])
        self.assertEqual(
            owner.post(
                "/v1/keys", json={"name": "too much", "permissions": ["users.manage"]}
            ).status_code,
            403,
        )
        key = self.key(owner, ["functions.read"])
        bearer = self.anonymous()
        bearer.headers["Authorization"] = "Bearer " + key["secret"]
        self.assertEqual(bearer.get("/v1/functions").status_code, 200)
        self.assertEqual(
            bearer.post("/v1/functions", json={"name": "blocked"}).status_code, 403
        )
        self.assertEqual(
            bearer.post("/v1/keys", json={"name": "child"}).status_code, 403
        )
        listing = owner.get("/v1/keys")
        self.assertNotIn(key["secret"], listing.text)
        self.assertNotIn("secret_hash", listing.text)
        self.client.patch(
            f"/v1/roles/{role['id']}",
            json={"permissions": ["keys.manage", "functions.create"]},
        )
        self.assertEqual(bearer.get("/v1/functions").status_code, 403)
        self.assertEqual(
            bearer.post("/v1/functions", json={"name": "still_blocked"}).status_code,
            403,
        )
        self.assertEqual(self.client.delete(f"/v1/keys/{key['id']}").status_code, 404)
        self.assertEqual(owner.delete(f"/v1/keys/{key['id']}").status_code, 204)
        self.assertEqual(bearer.get("/v1/functions").status_code, 401)

    def test_run_ownership_public_execution_and_invalid_credentials(self):
        self.function()
        role = self.role(["functions.run", "runs.read", "runs.cancel", "keys.manage"])
        user = self.user(roles=[role["id"]])
        owner = self.anonymous()
        login(owner, user["username"])
        key = self.key(owner, ["functions.run", "runs.read"])
        owner.cookies.clear()
        owner.headers["Authorization"] = "Bearer " + key["secret"]
        own = owner.post("/v1/run/hello", json={})
        self.assertEqual(own.status_code, 200, own.text)
        own_id = own.headers["X-Run-Id"]
        own_record = owner.get(f"/v1/runs/{own_id}").json()
        self.assertEqual(own_record["user_id"], user["id"])
        self.assertEqual(own_record["api_key_id"], key["id"])
        admin_run = self.client.post("/v1/run/hello", json={})
        admin_id = admin_run.headers["X-Run-Id"]
        self.assertEqual(owner.get("/v1/runs").json()["total"], 1)
        self.assertEqual(owner.get(f"/v1/runs/{admin_id}").status_code, 404)
        self.assertEqual(owner.post(f"/v1/runs/{admin_id}/cancel").status_code, 404)
        self.assertEqual(self.client.get("/v1/runs").json()["total"], 2)
        guest = self.anonymous()
        self.assertEqual(guest.post("/v1/run/hello", json={}).status_code, 401)
        public = self.function(public=True, name="public")
        run = guest.post("/v1/run/public", json={})
        self.assertEqual(run.status_code, 200, run.text)
        self.assertEqual(
            guest.get(f"/v1/runs/{run.headers['X-Run-Id']}").status_code, 401
        )
        self.assertEqual(guest.get(f"/v1/functions/{public['id']}").status_code, 401)
        guest.headers["Authorization"] = "Bearer invalid"
        self.assertEqual(guest.post("/v1/run/public", json={}).status_code, 401)
        self.client.patch(f"/v1/functions/{public['id']}", json={"public": False})
        guest.headers.pop("Authorization")
        self.assertEqual(guest.post("/v1/run/public", json={}).status_code, 401)

    def test_publishing_requires_separate_permission(self):
        role = self.role(["functions.create", "functions.update"])
        user = self.user(roles=[role["id"]])
        owner = self.anonymous()
        login(owner, user["username"])
        self.assertEqual(
            owner.post(
                "/v1/functions", json={"name": "public", "public": True}
            ).status_code,
            403,
        )
        function = owner.post("/v1/functions", json={"name": "private"}).json()
        self.assertEqual(
            owner.patch(
                f"/v1/functions/{function['id']}", json={"public": True}
            ).status_code,
            403,
        )

    def test_cancel_all_cannot_reveal_an_unreadable_run(self):
        function = self.function()
        role = self.role(["runs.read", "runs.cancel_all"])
        user = self.user(roles=[role["id"]])
        owner = self.anonymous()
        login(owner, user["username"])

        async def pending_run():
            async with self.app.state.database.sessions.begin() as session:
                stored = await FunctionRepository(session).get(UUID(function["id"]))
                run = Run(stored.revision, None, user_id=self.admin.id)
                await RunRepository(session).add(run, uuid7())
                return run.id

        run_id = self.client.portal.call(pending_run)
        self.assertEqual(owner.post(f"/v1/runs/{run_id}/cancel").status_code, 404)
        self.assertEqual(
            self.client.get(f"/v1/runs/{run_id}").json()["status"], "pending"
        )
        self.client.patch(
            f"/v1/roles/{role['id']}",
            json={"permissions": ["runs.read", "runs.read_all", "runs.cancel_all"]},
        )
        self.assertEqual(owner.post(f"/v1/runs/{run_id}/cancel").status_code, 200)

    def test_last_admin_protected_role_and_bootstrap(self):
        admin_role = next(
            role
            for role in self.client.get("/v1/roles").json()["items"]
            if role["protected"]
        )
        self.assertEqual(
            self.client.patch(
                f"/v1/roles/{admin_role['id']}", json={"permissions": []}
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.delete(f"/v1/roles/{admin_role['id']}").status_code, 409
        )
        for changes in ({"role_ids": []}, {"enabled": False}):
            self.assertEqual(
                self.client.patch(
                    f"/v1/users/{self.admin.id}", json=changes
                ).status_code,
                409,
            )
        with self.assertRaises(Conflict):
            self.client.portal.call(
                AuthService(self.app.state.database).create_first_admin,
                "second",
                PASSWORD,
            )
        second = self.user("second", roles=[admin_role["id"]])
        self.assertEqual(
            self.client.patch(
                f"/v1/users/{second['id']}", json={"enabled": False}
            ).status_code,
            200,
        )

    def test_disabled_user_credentials_do_not_revive_on_enable(self):
        role = self.role(["functions.read", "keys.manage"])
        user = self.user(roles=[role["id"]])
        owner = self.anonymous()
        login(owner, user["username"])
        key = self.key(owner, ["functions.read"])
        bearer = self.anonymous()
        bearer.headers["Authorization"] = "Bearer " + key["secret"]
        self.client.patch(f"/v1/users/{user['id']}", json={"enabled": False})
        self.assertEqual(owner.get("/v1/auth/me").status_code, 401)
        self.assertEqual(bearer.get("/v1/functions").status_code, 401)
        self.client.patch(f"/v1/users/{user['id']}", json={"enabled": True})
        self.assertEqual(owner.get("/v1/auth/me").status_code, 401)
        self.assertEqual(bearer.get("/v1/functions").status_code, 401)
        login(owner, user["username"])

    def test_password_change_revokes_all_sessions_and_stores_only_hashes(self):
        other = self.anonymous()
        login(other)
        failed = self.client.post(
            "/v1/auth/password",
            json={"current_password": "wrong", "new_password": PASSWORD + "2"},
        )
        self.assertEqual(failed.status_code, 422)
        response = self.client.post(
            "/v1/auth/password",
            json={"current_password": PASSWORD, "new_password": PASSWORD + "2"},
        )
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(other.get("/v1/auth/me").status_code, 401)
        login(other, password=PASSWORD + "2")
        key = self.key(other, ["functions.read"])

        async def inspect():
            async with self.app.state.database.sessions() as session:
                user = await session.get(UserRow, self.admin.id)
                self.assertTrue(user.password_hash.startswith("$argon2id$"))
                stored = await session.get(APIKeyRow, UUID(key["id"]))
                self.assertNotEqual(stored.secret_hash, key["secret"])
                credential = await session.scalar(select(SessionRow))
                self.assertNotEqual(
                    credential.secret_hash, other.cookies.get("fure_session")
                )

        self.client.portal.call(inspect)

    def test_expired_key_and_validation(self):
        self.assertEqual(
            self.client.post(
                "/v1/keys",
                json={
                    "name": "expired",
                    "expires_at": (
                        datetime.now(UTC) - timedelta(seconds=1)
                    ).isoformat(),
                },
            ).status_code,
            422,
        )
        for body in ({"name": ""}, {"name": "unknown", "permissions": ["unknown"]}):
            self.assertEqual(self.client.post("/v1/roles", json=body).status_code, 422)
        self.assertEqual(
            self.client.post(
                "/v1/users", json={"username": "short", "password": "short"}
            ).status_code,
            422,
        )

    def test_last_admin_check_serializes_concurrent_changes(self):
        admin_role = next(
            role
            for role in self.client.get("/v1/roles").json()["items"]
            if role["protected"]
        )
        second = self.user("second", roles=[admin_role["id"]])
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self.client.patch, f"/v1/users/{id}", json={"role_ids": []})
                for id in (str(self.admin.id), second["id"])
            ]
            codes = sorted(future.result().status_code for future in futures)
        self.assertEqual(codes, [200, 409])
