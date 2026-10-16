"""Authenticated backup API and OAuth regression coverage."""

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.api.v1.endpoints import oauth
from app.core.security import create_access_token
from app.models.category import Category
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.services.backup_crypto import decrypt_backup


async def account(db, name="backup-user"):
    user = User(username=name, email=f"{name}@example.com", password_hash="unused")
    db.add(user)
    await db.commit()
    token = create_access_token({"sub": str(user.id), "token_version": user.token_version})
    return user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_export_encrypts_and_import_restores(client, db_session):
    user, headers = await account(db_session)
    db_session.add(Category(user_id=user.id, name="Restored category"))
    await db_session.commit()
    response = await client.post("/api/v1/backup/export", headers=headers,
                                 json={"passphrase": "backup-password-123"})
    assert response.status_code == 200, response.text
    assert b"Restored category" not in response.content
    assert decrypt_backup(response.content, "backup-password-123")["categories"][0]["name"] == "Restored category"
    await db_session.delete((await db_session.execute(select(Category))).scalar_one())
    await db_session.commit()
    response = await client.post("/api/v1/backup/import", headers=headers,
                                 files={"file": ("backup.json", response.content, "application/json")},
                                 data={"passphrase": "backup-password-123"})
    assert response.status_code == 200, response.text
    assert response.json()["categories_imported"] == 1
    assert (await db_session.execute(select(Category.name))).scalar_one() == "Restored category"


@pytest.mark.asyncio
async def test_backup_cannot_create_admin_announcements(client, db_session):
    _, headers = await account(db_session)
    data = {"version": "2.0", "exported_at": "2026-10-13", "categories": [], "feeds": [],
            "ai_providers": [], "ai_models": [], "custom_rules": [],
            "notifications": [{"title": "fake admin", "content": "malicious"}]}
    response = await client.post("/api/v1/backup/import", headers=headers,
                                 files={"file": ("backup.json", json.dumps(data), "application/json")})
    assert response.status_code == 403


class ProviderClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, url, **_):
        return httpx.Response(200, json={"access_token": "provider-token"},
                              request=httpx.Request("POST", url))

    async def get(self, url, **_):
        return httpx.Response(200, json={"id": 1234, "username": "oauth-user", "email": "oauth@example.com"},
                              request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_oauth_callback_uses_cookie_and_never_exposes_tokens(client, db_session, monkeypatch):
    db_session.add(SystemSettings(key="oauth_linuxdo", value=json.dumps({
        "enabled": True, "client_id": "test-client", "client_secret": "test-secret",
        "authorize_url": "https://provider.example/authorize", "token_url": "https://provider.example/token",
        "userinfo_url": "https://provider.example/user",
    })))
    await db_session.commit()
    login = await client.get("/api/v1/auth/linuxdo/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    assert "HttpOnly" in login.headers["set-cookie"]
    monkeypatch.setattr(oauth.httpx, "AsyncClient", ProviderClient)
    response = await client.get(f"/api/v1/auth/callback/linuxdo?code=sample&state={state}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login?oauth_success=true"
    assert "access_token" not in response.headers["location"]
    assert "HttpOnly" in response.headers["set-cookie"]
    user = (await db_session.execute(select(User))).scalar_one()
    assert user.is_admin


@pytest.mark.asyncio
async def test_oauth_rejects_state_from_another_browser(client):
    response = await client.get("/api/v1/auth/callback/linuxdo?code=sample&state=not-bound",
                                follow_redirects=False)
    assert "invalid_state" in response.headers["location"]
