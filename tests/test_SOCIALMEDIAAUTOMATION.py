"""Unit tests for SOCIALMEDIAAUTOMATION backend."""

import os
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Import the app
from SOCIALMEDIAAUTOMATION import (
    app,
    classify_comment,
    action_for_category,
    tags_for_category,
    generate_reply,
    build_publish_payload,
    CommentPayload,
    PublishPayload,
    now_iso,
)


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def valid_comment_payload():
    """Valid comment payload for testing."""
    return {
        "platform": "instagram",
        "comment_id": "12345",
        "comment_text": "¿Cuál es el precio?",
        "user_name": "juan_perez",
        "timestamp": "2026-06-03T10:00:00Z",
        "post_id": "98765",
    }


@pytest.fixture
def valid_publish_payload():
    """Valid publish payload for testing."""
    return {
        "platform": "instagram",
        "caption": "Nuevo lanzamiento RoyalShield 🎉",
        "image_url": "https://example.com/image.jpg",
        "publish_at": "2026-06-03T15:00:00Z",
    }


class TestHealthEndpoint:
    """Test suite for /health endpoint."""

    def test_health_endpoint_returns_200(self, client):
        """Health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_ok_true(self, client):
        """Health endpoint should return ok: true."""
        response = client.get("/health")
        data = response.json()
        assert data["ok"] is True
        assert data["status"] == "healthy"

    def test_health_endpoint_has_timestamp(self, client):
        """Health endpoint should include received_at timestamp."""
        response = client.get("/health")
        data = response.json()
        assert "received_at" in data


class TestRootEndpoint:
    """Test suite for / endpoint."""

    def test_root_endpoint_returns_200(self, client):
        """Root endpoint should return 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_endpoint_returns_service_info(self, client):
        """Root endpoint should return service information."""
        response = client.get("/")
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "SOCIALMEDIAAUTOMATION"
        assert data["version"] == "2.0.0"


class TestCommentClassification:
    """Test suite for comment classification logic."""

    def test_classify_urgent_comment(self):
        """Should classify urgent comments correctly."""
        assert classify_comment("URGENTE! Tengo un problema") == "urgent"
        assert classify_comment("Necesito ayuda inmediata") == "urgent"

    def test_classify_lead_comment(self):
        """Should classify lead comments correctly."""
        assert classify_comment("¿Cuál es el precio?") == "lead"
        assert classify_comment("¿Tienen planes de suscripción?") == "lead"

    def test_classify_support_comment(self):
        """Should classify support comments correctly."""
        assert classify_comment("No funciona el sistema") == "soporte"
        assert classify_comment("Encontré un bug") == "soporte"

    def test_classify_public_comment(self):
        """Should classify public engagement comments correctly."""
        assert classify_comment("¡Excelente servicio!") == "comentario_publico"
        assert classify_comment("Me gusta mucho RoyalShield") == "comentario_publico"

    def test_classify_spam_comment(self):
        """Should classify spam comments correctly."""
        assert classify_comment("Visita https://spam.com haz clic aquí") == "spam"

    def test_classify_irrelevant_comment(self):
        """Should classify irrelevant comments correctly."""
        assert classify_comment("Hola a todos") == "irrelevante"


class TestActionForCategory:
    """Test suite for action determination logic."""

    def test_action_for_urgent(self):
        """Urgent comments should trigger auto_reply."""
        assert action_for_category("urgent") == "auto_reply"

    def test_action_for_lead(self):
        """Lead comments should trigger auto_reply."""
        assert action_for_category("lead") == "auto_reply"

    def test_action_for_support(self):
        """Support comments should trigger auto_reply."""
        assert action_for_category("soporte") == "auto_reply"

    def test_action_for_public(self):
        """Public comments should trigger auto_reply."""
        assert action_for_category("comentario_publico") == "auto_reply"

    def test_action_for_spam(self):
        """Spam comments should trigger manual_review."""
        assert action_for_category("spam") == "manual_review"

    def test_action_for_irrelevant(self):
        """Irrelevant comments should be ignored."""
        assert action_for_category("irrelevante") == "ignore"


class TestTagsForCategory:
    """Test suite for tag generation logic."""

    def test_tags_for_urgent(self):
        """Urgent comments should have priority tags."""
        tags = tags_for_category("urgent")
        assert "prioridad_alta" in tags
        assert "atencion_inmediata" in tags

    def test_tags_for_lead(self):
        """Lead comments should have sales tags."""
        tags = tags_for_category("lead")
        assert "posible_cliente" in tags
        assert "ventas" in tags

    def test_tags_for_support(self):
        """Support comments should have ticket tags."""
        tags = tags_for_category("soporte")
        assert "ticket_soporte" in tags

    def test_tags_for_engagement(self):
        """Public comments should have engagement tags."""
        tags = tags_for_category("comentario_publico")
        assert "engagement" in tags


class TestReplyGeneration:
    """Test suite for reply generation logic."""

    def test_generate_reply_for_urgent(self):
        """Should generate appropriate urgent reply."""
        payload = CommentPayload(
            platform="instagram",
            comment_id="123",
            comment_text="URGENTE",
            user_name="Juan",
            timestamp="2026-06-03T10:00:00Z",
        )
        reply = generate_reply("urgent", payload)
        assert "Juan" in reply
        assert "mensaje privado" in reply

    def test_generate_reply_for_lead(self):
        """Should generate appropriate lead reply."""
        payload = CommentPayload(
            platform="instagram",
            comment_id="123",
            comment_text="Precio",
            user_name="Maria",
            timestamp="2026-06-03T10:00:00Z",
        )
        reply = generate_reply("lead", payload)
        assert "Maria" in reply
        assert "interés" in reply

    def test_reply_includes_first_name_only(self):
        """Reply should use only first name."""
        payload = CommentPayload(
            platform="instagram",
            comment_id="123",
            comment_text="Test",
            user_name="Juan Carlos Perez",
            timestamp="2026-06-03T10:00:00Z",
        )
        reply = generate_reply("comentario_publico", payload)
        assert "Juan" in reply
        assert "Carlos" not in reply


class TestPublishPayload:
    """Test suite for publish payload validation."""

    def test_valid_publish_payload_with_image(self, valid_publish_payload):
        """Should accept valid publish payload with image."""
        payload = PublishPayload(**valid_publish_payload)
        assert payload.platform == "instagram"
        assert payload.caption == "Nuevo lanzamiento RoyalShield 🎉"
        assert payload.image_url == "https://example.com/image.jpg"

    def test_publish_payload_caption_required(self):
        """Caption should be required."""
        with pytest.raises(ValueError):
            PublishPayload(
                platform="instagram",
                caption="",
                image_url="https://example.com/image.jpg",
            )

    def test_publish_payload_invalid_image_url(self):
        """Image URL must be valid HTTP/HTTPS."""
        with pytest.raises(ValueError):
            PublishPayload(
                platform="instagram",
                caption="Test",
                image_url="not-a-url",
            )

    def test_publish_payload_video_not_for_instagram(self):
        """Video URLs should only be for Facebook."""
        with pytest.raises(ValueError):
            PublishPayload(
                platform="instagram",
                caption="Test",
                video_url="https://example.com/video.mp4",
            )

    def test_publish_payload_valid_iso_datetime(self):
        """Should accept valid ISO datetime."""
        payload = PublishPayload(
            platform="facebook",
            caption="Test",
            publish_at="2026-06-03T15:00:00Z",
        )
        assert payload.publish_at == "2026-06-03T15:00:00Z"

    def test_publish_payload_invalid_datetime(self):
        """Should reject invalid datetime."""
        with pytest.raises(ValueError):
            PublishPayload(
                platform="instagram",
                caption="Test",
                publish_at="not-a-date",
            )


class TestBuildPublishPayload:
    """Test suite for publish payload building."""

    def test_build_payload_with_image(self, valid_publish_payload):
        """Should build payload correctly with image."""
        payload = PublishPayload(**valid_publish_payload)
        built = build_publish_payload(payload)
        assert built["media_type"] == "image"
        assert built["platform"] == "instagram"

    def test_build_payload_with_video(self):
        """Should build payload correctly with video."""
        valid_video_payload = {
            "platform": "facebook",
            "caption": "Test video",
            "video_url": "https://example.com/video.mp4",
        }
        payload = PublishPayload(**valid_video_payload)
        built = build_publish_payload(payload)
        assert built["media_type"] == "video"

    def test_build_payload_text_only(self):
        """Should build text-only payload correctly."""
        text_payload = {
            "platform": "instagram",
            "caption": "Text post",
        }
        payload = PublishPayload(**text_payload)
        built = build_publish_payload(payload)
        assert built["media_type"] == "text"


class TestWebhookEndpoints:
    """Test suite for webhook endpoints."""

    def test_webhook_get_missing_token(self, client):
        """GET /webhook without token should return 403."""
        response = client.get("/webhook")
        assert response.status_code == 403

    def test_webhook_post_comment(self, client, valid_comment_payload):
        """POST /webhook should handle comment payload."""
        response = client.post("/webhook", json=valid_comment_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "category" in data
        assert "action" in data
        assert "reply" in data

    def test_webhook_post_publish(self, client, valid_publish_payload):
        """POST /webhook should handle publish payload."""
        response = client.post("/webhook", json=valid_publish_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["category"] == "media_post"

    def test_webhook_post_invalid_json(self, client):
        """POST /webhook with invalid JSON should return 400."""
        response = client.post("/webhook", data="invalid")
        assert response.status_code == 400

    def test_webhook_post_non_dict_json(self, client):
        """POST /webhook with non-dict JSON should return 400."""
        response = client.post("/webhook", json=[1, 2, 3])
        assert response.status_code == 400


class TestUtilityFunctions:
    """Test suite for utility functions."""

    def test_now_iso_returns_valid_iso(self):
        """now_iso() should return valid ISO format string."""
        iso_str = now_iso()
        assert "T" in iso_str
        assert iso_str.endswith("+00:00")
        # Should be parseable
        datetime.fromisoformat(iso_str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
