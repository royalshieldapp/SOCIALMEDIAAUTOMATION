import os
import unittest

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


if __name__ == "__main__":
    unittest.main()
