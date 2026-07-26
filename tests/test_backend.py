import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from SOCIALMEDIAAUTOMATION import app


class BackendSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def make_headers(self):
        secret = os.getenv("MAKE_SECRET")
        return {"x-make-secret": secret} if secret else {}

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["status"], "healthy")

    def test_meta_webhook_verification_uses_meta_verify_token(self):
        previous_token = os.environ.get("META_VERIFY_TOKEN")
        os.environ["META_VERIFY_TOKEN"] = "test-token"

        try:
            response = self.client.get(
                "/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "test-token",
                    "hub.challenge": "challenge-123",
                },
            )
        finally:
            if previous_token is None:
                os.environ.pop("META_VERIFY_TOKEN", None)
            else:
                os.environ["META_VERIFY_TOKEN"] = previous_token

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "challenge-123")

    def test_comment_payload_returns_classification(self):
        response = self.client.post(
            "/webhook",
            headers=self.make_headers(),
            json={
                "platform": "instagram",
                "comment_id": "comment-1",
                "comment_text": "Quiero precio",
                "user_name": "Carlos",
                "timestamp": "2026-06-20T10:00:00Z",
                "post_id": "post-1",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["category"], "lead")
        self.assertEqual(data["action"], "auto_reply")
        self.assertIn("posible_cliente", data["tags"])

    def test_make_alias_accepts_publish_payload(self):
        response = self.client.post(
            "/webhook/make",
            headers=self.make_headers(),
            json={
                "event_type": "publish_post",
                "platform": "instagram",
                "caption": "Post test",
                "image_url": "https://example.com/image.jpg",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["category"], "media_post")
        self.assertEqual(data["action"], "publish_now")
        self.assertEqual(data["publish_payload"]["media_type"], "image")

    def test_facebook_text_post_calls_page_feed(self):
        graph_result = {"id": "page-1_post-1"}
        with (
            patch.dict(
                os.environ,
                {
                    "MAKE_SECRET": "make-secret",
                    "FACEBOOK_PAGE_ID": "page-1",
                    "FACEBOOK_PAGE_ACCESS_TOKEN": "page-token",
                },
                clear=False,
            ),
            patch(
                "SOCIALMEDIAAUTOMATION.facebook_graph_request",
                new=AsyncMock(return_value=graph_result),
            ) as graph_request,
        ):
            response = self.client.post(
                "/facebook/posts",
                headers={"x-make-secret": "make-secret"},
                json={
                    "platform": "facebook",
                    "caption": "Facebook post",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["meta_result"]["id"], "page-1_post-1")
        graph_request.assert_awaited_once_with(
            edge="page-1/feed",
            data={"message": "Facebook post"},
        )

    def test_facebook_comment_reply_calls_graph_api(self):
        graph_result = {"id": "reply-1"}
        with (
            patch.dict(
                os.environ,
                {
                    "MAKE_SECRET": "make-secret",
                    "FACEBOOK_PAGE_ID": "page-1",
                    "FACEBOOK_PAGE_ACCESS_TOKEN": "page-token",
                },
                clear=False,
            ),
            patch(
                "SOCIALMEDIAAUTOMATION.facebook_graph_request",
                new=AsyncMock(return_value=graph_result),
            ) as graph_request,
        ):
            response = self.client.post(
                "/facebook/comments/comment_1/reply",
                headers={"x-make-secret": "make-secret"},
                json={"message": "Gracias por escribirnos"},
            )

        self.assertEqual(response.status_code, 200)
        graph_request.assert_awaited_once_with(
            edge="comment_1/comments",
            data={"message": "Gracias por escribirnos"},
        )

    def test_native_meta_webhook_requires_valid_signature(self):
        body = {
            "object": "page",
            "entry": [
                {
                    "id": "page-1",
                    "changes": [
                        {
                            "field": "feed",
                            "value": {
                                "item": "comment",
                                "verb": "add",
                                "comment_id": "comment_1",
                                "message": "Quiero precio",
                                "from": {"id": "user-1", "name": "Carlos"},
                                "post_id": "page-1_post-1",
                            },
                        }
                    ],
                }
            ],
        }
        raw_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
        signature = (
            "sha256="
            + hmac.new(
                b"app-secret",
                raw_body,
                hashlib.sha256,
            ).hexdigest()
        )

        with patch.dict(
            os.environ,
            {
                "META_APP_SECRET": "app-secret",
                "FACEBOOK_AUTO_REPLY_ENABLED": "false",
            },
            clear=False,
        ):
            response = self.client.post(
                "/webhook",
                content=raw_body,
                headers={
                    "content-type": "application/json",
                    "x-hub-signature-256": signature,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["facebook_comment_events"], 1)
        self.assertFalse(response.json()["auto_reply_queued"])

    def test_native_meta_webhook_rejects_invalid_signature(self):
        raw_body = b'{"object":"page","entry":[]}'
        with patch.dict(
            os.environ,
            {"META_APP_SECRET": "app-secret"},
            clear=False,
        ):
            response = self.client.post(
                "/webhook",
                content=raw_body,
                headers={
                    "content-type": "application/json",
                    "x-hub-signature-256": "sha256=invalid",
                },
            )

        self.assertEqual(response.status_code, 401)

    def test_production_make_endpoint_fails_closed_without_secret(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production"},
            clear=False,
        ):
            previous_secret = os.environ.pop("MAKE_SECRET", None)
            try:
                response = self.client.post(
                    "/facebook/posts",
                    json={
                        "platform": "facebook",
                        "caption": "Should not publish",
                    },
                )
            finally:
                if previous_secret is not None:
                    os.environ["MAKE_SECRET"] = previous_secret

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
