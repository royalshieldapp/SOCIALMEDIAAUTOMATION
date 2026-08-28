import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import SOCIALMEDIAAUTOMATION as mod


@pytest.fixture(autouse=True)
def clean_env(tmp_path):
    keys = [
        "AUTOMATION_API_KEY",
        "META_APP_SECRET",
        "META_VERIFY_TOKEN",
        "FACEBOOK_PAGE_ID",
        "FACEBOOK_PAGE_ACCESS_TOKEN",
        "INSTAGRAM_BUSINESS_ACCOUNT_ID",
        "INSTAGRAM_ACCESS_TOKEN",
        "FACEBOOK_AUTO_REPLY_ENABLED",
        "INSTAGRAM_AUTO_REPLY_ENABLED",
        "SCHEDULE_DB_PATH",
    ]
    old = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    os.environ["SCHEDULE_DB_PATH"] = str(tmp_path / "state.db")
    yield
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def client():
    return TestClient(mod.app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_has_no_make(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "make" not in json.dumps(response.json()).lower()
    assert response.json()["version"] == "3.0.0"


def test_mutating_endpoint_fails_closed_without_key(client):
    response = client.post(
        "/facebook/posts", json={"platform": "facebook", "caption": "test"}
    )
    assert response.status_code == 503


def test_mutating_endpoint_rejects_wrong_key(client):
    os.environ["AUTOMATION_API_KEY"] = "expected"
    response = client.post(
        "/facebook/posts",
        headers={"x-automation-key": "wrong"},
        json={"platform": "facebook", "caption": "test"},
    )
    assert response.status_code == 401


def test_facebook_publish_calls_graph_api(client):
    os.environ.update(
        {
            "AUTOMATION_API_KEY": "key",
            "FACEBOOK_PAGE_ID": "page_1",
            "FACEBOOK_PAGE_ACCESS_TOKEN": "token",
        }
    )
    with patch.object(
        mod, "meta_graph_request", new=AsyncMock(return_value={"id": "post_1"})
    ) as request:
        response = client.post(
            "/facebook/posts",
            headers={"x-automation-key": "key"},
            json={"platform": "facebook", "caption": "hello"},
        )
    assert response.status_code == 200
    assert response.json()["action"] == "published"
    request.assert_awaited_once_with(
        edge="page_1/feed", access_token="token", data={"message": "hello"}
    )


def test_instagram_image_publish_uses_container_then_publish(client):
    os.environ.update(
        {
            "AUTOMATION_API_KEY": "key",
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "ig_1",
            "INSTAGRAM_ACCESS_TOKEN": "ig-token",
        }
    )
    graph = AsyncMock(side_effect=[{"id": "container_1"}, {"id": "media_1"}])
    with patch.object(mod, "meta_graph_request", new=graph):
        response = client.post(
            "/instagram/posts",
            headers={"x-automation-key": "key"},
            json={
                "platform": "instagram",
                "caption": "hello ig",
                "image_url": "https://example.com/a.jpg",
            },
        )
    assert response.status_code == 200
    assert response.json()["meta_result"]["container_id"] == "container_1"
    assert graph.await_count == 2
    assert graph.await_args_list[0].kwargs["edge"] == "ig_1/media"
    assert graph.await_args_list[1].kwargs["edge"] == "ig_1/media_publish"


def test_instagram_public_comment_reply(client):
    os.environ.update(
        {
            "AUTOMATION_API_KEY": "key",
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "ig_1",
            "INSTAGRAM_ACCESS_TOKEN": "ig-token",
        }
    )
    with patch.object(
        mod, "meta_graph_request", new=AsyncMock(return_value={"id": "reply_1"})
    ) as request:
        response = client.post(
            "/instagram/comments/comment_1/reply",
            headers={"x-automation-key": "key"},
            json={"message": "Gracias"},
        )
    assert response.status_code == 200
    request.assert_awaited_once_with(
        edge="comment_1/replies",
        access_token="ig-token",
        data={"message": "Gracias"},
        host="graph.instagram.com",
    )


def test_meta_webhook_rejects_bad_signature(client):
    os.environ["META_APP_SECRET"] = "secret"
    response = client.post(
        "/webhook",
        content=b'{"object":"page","entry":[]}',
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256=bad",
        },
    )
    assert response.status_code == 401


def test_instagram_webhook_is_deduplicated(client):
    os.environ.update(
        {"META_APP_SECRET": "secret", "INSTAGRAM_AUTO_REPLY_ENABLED": "true"}
    )
    body = {
        "object": "instagram",
        "entry": [
            {
                "id": "ig_1",
                "time": 123,
                "field": "comments",
                "value": {
                    "id": "comment_1",
                    "from": {"username": "carlos"},
                    "text": "quiero precio",
                    "media": {"id": "media_1"},
                },
            }
        ],
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    headers = {
        "content-type": "application/json",
        "x-hub-signature-256": signature,
    }
    with patch.object(mod, "process_comment_event", new=AsyncMock()):
        first = client.post("/webhook", content=raw, headers=headers)
        second = client.post("/webhook", content=raw, headers=headers)
    assert first.status_code == 200
    assert first.json()["auto_reply_queued"] == 1
    assert second.json()["auto_reply_queued"] == 0
    assert second.json()["duplicates_ignored"] == 1


def test_future_post_is_scheduled_without_calling_meta(client):
    os.environ["AUTOMATION_API_KEY"] = "key"
    publish_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    with patch.object(mod, "publish_to_platform", new=AsyncMock()) as publish:
        response = client.post(
            "/posts",
            headers={"x-automation-key": "key"},
            json={
                "platform": "facebook",
                "caption": "later",
                "publish_at": publish_at,
            },
        )
    assert response.status_code == 200
    assert response.json()["action"] == "scheduled"
    assert isinstance(response.json()["schedule_id"], int)
    publish.assert_not_awaited()


def test_scheduler_publishes_due_post(client):
    os.environ["AUTOMATION_API_KEY"] = "key"
    payload = mod.PublishPayload(
        platform="facebook",
        caption="due",
        publish_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    )
    mod.state_store.ensure_schema()
    with mod.state_store._lock, mod.state_store._connect() as conn:
        conn.execute(
            "INSERT INTO scheduled_posts(payload_json, publish_at, created_at) VALUES (?, ?, ?)",
            (json.dumps(payload.model_dump()), payload.publish_at, mod.now_iso()),
        )
        conn.commit()
    with patch.object(
        mod, "publish_to_platform", new=AsyncMock(return_value={"id": "ok"})
    ) as publish:
        response = client.post(
            "/scheduler/run", headers={"x-automation-key": "key"}
        )
    assert response.status_code == 200
    assert response.json()["published"] == 1
    publish.assert_awaited_once()
