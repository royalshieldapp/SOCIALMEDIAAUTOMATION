"""Cobertura de la integración con Google Drive: listado de imágenes y proxy firmado."""
import asyncio
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import drive_integration
import SOCIALMEDIAAUTOMATION as mod

FILE_ID = "a" * 33  # >= 20 chars: coincide con el patrón del path del proxy


class FakeStreamResponse:
    """Respuesta mínima con la interfaz que usa el proxy (aiter_bytes/aclose)."""

    def __init__(self, status_code=200, headers=None, chunks=()):
        self.status_code = status_code
        self.headers = dict(headers or {})
        self._chunks = list(chunks)
        self.aclosed = False

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk

    async def aclose(self):
        self.aclosed = True


@pytest.fixture
def client():
    return TestClient(mod.app)


def signed_params(key, file_id=FILE_ID, ttl=3600):
    exp = int(time.time()) + ttl
    sig = hmac.new(key.encode(), f"{file_id}:{exp}".encode(), hashlib.sha256).hexdigest()
    return f"exp={exp}&sig={sig}"


def mock_drive_api(files):
    def respond(request):
        if "googleapis.com" in str(request.url):
            return httpx.Response(200, json={"files": files})
        return httpx.Response(404, text="not found")

    return respond


# --- fetch_folder_images: los tres caminos -----------------------------------

def test_fetch_folder_images_drive_api_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_DRIVE_API_KEY", "test-drive-key")
    files = [
        {"id": FILE_ID, "name": "foto.jpg", "mimeType": "image/jpeg",
         "thumbnailLink": None, "webViewLink": "https://drive.google.com/file/d/x/view"},
    ]
    original = httpx.AsyncClient
    with patch.object(
        drive_integration.httpx, "AsyncClient",
        side_effect=lambda **kwargs: original(transport=httpx.MockTransport(mock_drive_api(files)), **kwargs),
    ):
        result = asyncio.run(drive_integration.fetch_folder_images("folder123", "https://app.example"))
    assert result["ok"] is True
    assert result["source"] == "drive_api"
    assert result["count"] == 1
    image = result["images"][0]
    assert image["id"] == FILE_ID
    assert image["direct_url"] == f"https://app.example/drive/proxy/{FILE_ID}"


def test_fetch_folder_images_public_folder_fallback(monkeypatch):
    monkeypatch.delenv("GOOGLE_DRIVE_API_KEY", raising=False)
    html = f'<html><div id="entry-{FILE_ID}"></div></html>'

    def respond(request):
        return httpx.Response(200, text=html)

    original = httpx.AsyncClient
    with patch.object(
        drive_integration.httpx, "AsyncClient",
        side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    ):
        result = asyncio.run(drive_integration.fetch_folder_images("folder123", "https://app.example"))
    assert result["ok"] is True
    assert result["source"] == "public_folder_view"
    assert result["images"][0]["id"] == FILE_ID


def test_fetch_folder_images_total_failure_returns_not_ok(monkeypatch):
    monkeypatch.setenv("GOOGLE_DRIVE_API_KEY", "test-drive-key")

    def respond(request):
        return httpx.Response(500, text="boom")

    original = httpx.AsyncClient
    with patch.object(
        drive_integration.httpx, "AsyncClient",
        side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    ):
        result = asyncio.run(drive_integration.fetch_folder_images("folder123"))
    assert result["ok"] is False
    assert result["images"] == []
    assert result["error"]


# --- stream_drive_file: el par (response, aclose) ----------------------------

def test_stream_drive_file_returns_closable_pair():
    body = b"\xff\xd8fake-jpeg"

    def respond(request):
        return httpx.Response(200, headers={"content-type": "image/jpeg"}, content=body)

    original = httpx.AsyncClient
    with patch.object(
        drive_integration.httpx, "AsyncClient",
        side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    ):
        async def exercise():
            resp, aclose = await drive_integration.stream_drive_file(FILE_ID)
            data = b"".join([chunk async for chunk in resp.aiter_bytes()])
            await aclose()
            return data

        assert asyncio.run(exercise()) == body


# --- /drive/proxy: firma, tipo de contenido y límite --------------------------

def stream_pair(response):
    closed = []

    async def aclose():
        closed.append(True)
        await response.aclose()

    return response, aclose, closed


def test_drive_proxy_rejects_unsigned_request(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "test-key")
    response = client.get(f"/drive/proxy/{FILE_ID}")
    assert response.status_code == 401


def test_drive_proxy_rejects_expired_signature(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "test-key")
    response = client.get(f"/drive/proxy/{FILE_ID}?{signed_params('test-key', ttl=-10)}")
    assert response.status_code == 401


def test_drive_proxy_rejects_wrong_signature(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "test-key")
    exp = int(time.time()) + 3600
    response = client.get(f"/drive/proxy/{FILE_ID}?exp={exp}&sig={'0' * 64}")
    assert response.status_code == 401


def test_drive_proxy_rejects_non_image_content_type(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "test-key")
    resp = FakeStreamResponse(200, {"content-type": "text/html"}, [b"<html>"])
    fake, aclose, closed = stream_pair(resp)
    with patch.object(drive_integration, "stream_drive_file", new=AsyncMock(return_value=(fake, aclose))):
        response = client.get(f"/drive/proxy/{FILE_ID}?{signed_params('test-key')}")
    assert response.status_code == 502
    assert closed  # la conexión se libera aunque el contenido se rechace


def test_drive_proxy_rejects_oversized_content_length(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "test-key")
    too_big = str(25 * 1024 * 1024 + 1)
    resp = FakeStreamResponse(200, {"content-type": "image/jpeg", "content-length": too_big}, [b"x"])
    fake, aclose, closed = stream_pair(resp)
    with patch.object(drive_integration, "stream_drive_file", new=AsyncMock(return_value=(fake, aclose))):
        response = client.get(f"/drive/proxy/{FILE_ID}?{signed_params('test-key')}")
    assert response.status_code == 413
    assert closed


def test_drive_proxy_streams_image_and_caps_body_without_content_length(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "test-key")
    chunks = [b"y" * (6 * 1024 * 1024) for _ in range(5)]  # 30 MB sin Content-Length
    resp = FakeStreamResponse(200, {"content-type": "image/jpeg"}, chunks)
    fake, aclose, closed = stream_pair(resp)
    with patch.object(drive_integration, "stream_drive_file", new=AsyncMock(return_value=(fake, aclose))):
        response = client.get(f"/drive/proxy/{FILE_ID}?{signed_params('test-key')}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    # 5 x 6 MB = 30 MB, pero el proxy nunca sirve más de 25 MB: trunca en 24 MB.
    assert len(response.content) == 24 * 1024 * 1024
    assert closed  # el cliente de Drive se cierra tras el stream


def test_drive_sync_signs_proxy_urls(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_DRIVE_API_KEY", "test-drive-key")
    files = [{"id": FILE_ID, "name": "foto.jpg", "mimeType": "image/jpeg"}]
    original = httpx.AsyncClient
    with patch.object(
        drive_integration.httpx, "AsyncClient",
        side_effect=lambda **kwargs: original(transport=httpx.MockTransport(mock_drive_api(files)), **kwargs),
    ):
        response = client.post(
            "/drive/sync",
            headers={"x-automation-key": "test-key"},
            json={"folder_url": "folder123"},
        )
    assert response.status_code == 200
    direct_url = response.json()["images"][0]["direct_url"]
    assert f"/drive/proxy/{FILE_ID}?" in direct_url
    # La firma debe ser un HMAC válido de file_id:exp con la automation key.
    from urllib.parse import parse_qs, urlparse

    query = parse_qs(urlparse(direct_url).query)
    exp = int(query["exp"][0])
    expected = hmac.new(b"test-key", f"{FILE_ID}:{exp}".encode(), hashlib.sha256).hexdigest()
    assert hmac.compare_digest(query["sig"][0], expected)
