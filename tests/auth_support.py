from fure.services.auth import AuthService

PASSWORD = "correct horse battery staple"


def login(client, username="admin", password=PASSWORD):
    response = client.post(
        "/v1/auth/login",
        json={"username": username, "password": password},
        headers={"X-Fure-Client": "web"},
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()


def bootstrap(client):
    user = client.portal.call(
        AuthService(client.app.state.database).create_first_admin, "admin", PASSWORD
    )
    login(client)
    return user
