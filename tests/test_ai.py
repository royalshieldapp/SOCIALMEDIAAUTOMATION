import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
import SOCIALMEDIAAUTOMATION as mod
import ai_content


@pytest.fixture
def client():
    return TestClient(mod.app)


def test_ai_generate_post_fails_without_key(client):
    response = client.post(
        "/ai/generate-post",
        json={"topic": "seguridad", "platform": "instagram"}
    )
    assert response.status_code == 503


def test_ai_generate_post_with_mocked_nvidia(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "secret_key")
    monkeypatch.setenv("NVIDIA_API_KEY", "test_key")
    with patch.object(
        ai_content,
        "call_nvidia_chat",
        new=AsyncMock(return_value="🛡️ Publicación de prueba sobre Royal Shield")
    ):
        response = client.post(
            "/ai/generate-post",
            headers={"x-automation-key": "secret_key"},
            json={"topic": "Wi-Fi seguro", "platform": "instagram"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "Publicación de prueba sobre Royal Shield" in data["caption"]
    assert data["topic"] == "Wi-Fi seguro"


def test_ai_reply_comment_with_mocked_nvidia(client, monkeypatch):
    monkeypatch.setenv("AUTOMATION_API_KEY", "secret_key")
    monkeypatch.setenv("NVIDIA_API_KEY", "test_key")
    with patch.object(
        ai_content,
        "call_nvidia_chat",
        new=AsyncMock(return_value='{"category": "lead", "reply": "Hola Carlos, te enviamos los precios por DM"}')
    ):
        response = client.post(
            "/ai/reply-comment",
            headers={"x-automation-key": "secret_key"},
            json={"comment_text": "Cuánto cuesta?", "user_name": "Carlos", "platform": "facebook"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "lead"
    assert "precios por DM" in data["reply"]


def test_ai_fallback_without_nvidia_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    result = asyncio.run(ai_content.generate_post(topic="Alerta de phishing", platform="facebook"))
    assert "Royal Shield" in result["caption"]
    assert result["provider"] == "fallback_template"
