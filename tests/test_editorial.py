import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
import SOCIALMEDIAAUTOMATION as mod

HEADERS = {"x-automation-key": "test-editorial-key"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    for key, value in {
        "SCHEDULE_DB_PATH": str(tmp_path / "editorial.db"),
        "AUTOMATION_API_KEY": "test-editorial-key",
        "FACEBOOK_PAGE_ID": "123",
        "INSTAGRAM_BUSINESS_ACCOUNT_ID": "456",
        "META_APP_SECRET": "test-secret",
        "ENVIRONMENT": "test",
        "SCHEDULER_ENABLED": "true",
    }.items():
        monkeypatch.setenv(key, value)
    return TestClient(mod.app)


def draft(client, platform="facebook", key="draft-1"):
    response = client.post("/editorial/posts", headers=HEADERS, json={
        "idempotency_key": key, "platform": platform, "caption": "Revisa tus permisos.",
        "image_url": "https://example.com/privacy.jpg", "timezone": "America/New_York",
    })
    assert response.status_code == 200, response.text
    return response.json()


def approved(client, platform="facebook", key="draft-1"):
    item = draft(client, platform, key)
    response = client.post(f"/editorial/posts/{item['id']}/approve", headers=HEADERS)
    assert response.status_code == 200, response.text
    return item


def make_due(item):
    with mod.editorial.connect() as conn:
        conn.execute("UPDATE editorial_posts SET publish_at=?, status='scheduled' WHERE id=?", ((datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat(), item["id"]))


def unpause(client):
    assert client.post("/editorial/control", headers=HEADERS, json={"paused": False}).status_code == 200


def test_draft_never_publishes_and_requires_approval(client):
    item = draft(client)
    assert item["status"] == "draft"
    assert item["target_id"] == "123"
    response = client.post(f"/editorial/posts/{item['id']}/schedule", headers=HEADERS,
                           json={"publish_at": "2099-01-01T12:00:00-05:00"})
    assert response.status_code == 409
    assert client.get("/editorial/posts", headers=HEADERS).json()[0]["status"] == "draft"


def test_idempotency_survives_new_store_instance_and_rejects_changed_content(client):
    first = draft(client)
    assert draft(client)["id"] == first["id"]
    assert type(mod.editorial)().get(first["id"])["caption"] == "Revisa tus permisos."
    response = client.post("/editorial/posts", headers=HEADERS, json={
        "idempotency_key": "draft-1", "platform": "facebook", "caption": "Different",
        "timezone": "America/New_York"})
    assert response.status_code == 409


def test_scheduling_validates_zone_and_offset(client):
    item = approved(client)
    for value in ["2099-01-01T12:00:00", "2020-01-01T12:00:00-05:00", "2099-01-01T12:00:00+09:00"]:
        assert client.post(f"/editorial/posts/{item['id']}/schedule", headers=HEADERS,
                           json={"publish_at": value}).status_code == 422
    response = client.post(f"/editorial/posts/{item['id']}/schedule", headers=HEADERS,
                           json={"publish_at": "2099-01-01T12:00:00-05:00"})
    assert response.json()["publish_at"] == "2099-01-01T17:00:00+00:00"


def test_pause_and_atomic_claim_prevent_duplicate_dispatch(client):
    item = approved(client)
    make_due(item)
    assert mod.editorial.claim_due() is None
    unpause(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: type(mod.editorial)().claim_due(), range(4)))
    assert sum(row is not None for row in rows) == 1
    assert mod.editorial.get(item["id"])["status"] == "publishing"


def test_resume_quarantines_expired_schedule_instead_of_releasing_backlog(client):
    old = approved(client)
    fresh = approved(client, key="fresh")
    make_due(fresh)
    with mod.editorial.connect() as conn:
        conn.execute("UPDATE editorial_posts SET status='scheduled',publish_at='2020-01-01T00:00:00+00:00' WHERE id=?", (old["id"],))
    unpause(client)
    claimed = mod.editorial.claim_due()
    assert claimed["id"] == fresh["id"]
    assert mod.editorial.get(old["id"])["status"] == "needs_review"
    assert mod.editorial.claim_due() is None


def test_default_timezone_is_new_york(client):
    response = client.post("/editorial/posts", headers=HEADERS, json={
        "idempotency_key": "default-zone", "platform": "facebook", "caption": "Approved later"})
    assert response.status_code == 200
    assert response.json()["timezone"] == "America/New_York"


def test_instagram_container_survives_publish_timeout_without_retry(client, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    item = approved(client, "instagram")
    make_due(item)
    unpause(client)
    with patch.object(mod, "graph_request", new=AsyncMock(side_effect=[
        {"id": "container_123"}, {"status_code": "FINISHED"}, TimeoutError("private")
    ])) as graph:
        asyncio.run(mod.run_due_posts())
        saved = mod.editorial.get(item["id"])
        assert saved["container_id"] == "container_123"
        assert saved["status"] == "needs_review"
        assert saved["external_id"] is None
        assert asyncio.run(mod.run_due_posts())["checked"] == 0
    assert graph.await_count == 3


def test_scheduler_status_requires_auth_and_reports_actual_cycle(client):
    assert client.get("/scheduler/status").status_code == 401
    before = client.get("/scheduler/status", headers=HEADERS).json()
    assert before["last_finished_at"] is None
    assert before["paused"] is True
    assert client.post("/scheduler/run", headers=HEADERS).status_code == 200
    after = client.get("/scheduler/status", headers=HEADERS).json()
    assert after["last_started_at"] is not None
    assert after["last_finished_at"] is not None
    assert after["last_result"]["checked"] == 0


def test_scheduler_failure_is_visible_without_leaking_secrets(client):
    with patch.object(mod, "run_due_posts", new=AsyncMock(side_effect=RuntimeError("private-token"))):
        with TestClient(mod.app, raise_server_exceptions=False) as api:
            response = api.post("/scheduler/run", headers=HEADERS)
    assert response.status_code == 503
    state = client.get("/scheduler/status", headers=HEADERS).json()
    assert state["last_result"]["ok"] is False
    assert "private-token" not in json.dumps(state)


def test_application_supervises_scheduler_lifecycle(client):
    import scheduler_daemon
    events = []
    async def companion():
        events.append("started")
        try:
            await asyncio.Event().wait()
        finally:
            events.append("stopped")
    with patch.object(scheduler_daemon, "main", new=companion):
        with TestClient(mod.app) as api:
            assert api.get("/health").status_code == 200
            assert events == ["started"]
    assert events == ["started", "stopped"]


def test_health_fails_when_enabled_worker_exits(client):
    import scheduler_daemon
    async def stopped():
        return
    with patch.object(scheduler_daemon, "main", new=stopped):
        with TestClient(mod.app) as api:
            assert api.get("/health").status_code == 503


@pytest.mark.parametrize("code", [4, 190])
def test_rate_limit_and_expired_token_do_not_retry_publication(client, code):
    from fastapi import HTTPException
    item = approved(client)
    make_due(item)
    unpause(client)
    with patch.object(mod, "publish", new=AsyncMock(side_effect=HTTPException(502, {"code": code, "message": "private"}))) as publish:
        asyncio.run(mod.run_due_posts())
        asyncio.run(mod.run_due_posts())
    assert publish.await_count == 1
    saved = mod.editorial.get(item["id"])
    assert saved["status"] == "failed"
    assert "private" not in saved["last_error"]


def test_existing_queue_migration_preserves_content_and_approval(client):
    import os
    import sqlite3
    item = approved(client)
    # Represent the pre-P0 database without the new provider-container column.
    with sqlite3.connect(os.environ["SCHEDULE_DB_PATH"]) as conn:
        conn.execute("ALTER TABLE editorial_posts DROP COLUMN container_id")
    restored = type(mod.editorial)().get(item["id"])
    assert restored["status"] == "approved"
    assert restored["approved_at"] is not None
    assert restored["caption"] == item["caption"]
    assert restored["container_id"] is None


def test_instagram_unready_image_is_not_published(client, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    item = approved(client, "instagram")
    make_due(item)
    unpause(client)
    with patch.object(mod, "graph_request", new=AsyncMock(side_effect=[
        {"id": "container_123"}, {"status_code": "ERROR"}
    ])) as graph:
        asyncio.run(mod.run_due_posts())
    assert graph.await_count == 2
    assert mod.editorial.get(item["id"])["status"] == "needs_review"
    assert mod.editorial.get(item["id"])["container_id"] == "container_123"


def test_scheduler_records_real_ids_links_and_does_not_repeat(client):
    item = approved(client)
    make_due(item)
    unpause(client)
    with patch.object(mod, "publish", new=AsyncMock(return_value={"id": "123_789"})), \
         patch.object(mod, "publication_link", new=AsyncMock(return_value="https://www.facebook.com/123/posts/789")):
        result = asyncio.run(mod.run_due_posts())
        second = asyncio.run(mod.run_due_posts())
    saved = mod.editorial.get(item["id"])
    assert result["published"] == 1 and second["checked"] == 0
    assert saved["external_id"] == "123_789"
    assert saved["permalink"] == "https://www.facebook.com/123/posts/789"
    assert saved["status"] == "published"


@pytest.mark.parametrize("result", [{}, {"success": True}, {"media": {}}])
def test_missing_meta_id_never_looks_published_or_retries(client, result):
    item = approved(client)
    make_due(item)
    unpause(client)
    with patch.object(mod, "publish", new=AsyncMock(return_value=result)):
        asyncio.run(mod.run_due_posts())
    assert mod.editorial.get(item["id"])["status"] == "needs_review"
    assert mod.editorial.claim_due() is None


def test_timeout_preserves_other_platform_and_never_blindly_retries(client):
    fb = approved(client)
    ig = approved(client, "instagram", "draft-ig")
    make_due(fb)
    make_due(ig)
    unpause(client)
    with patch.object(mod, "publish", new=AsyncMock(side_effect=[{"id": "123_789"}, TimeoutError("secret-value")])), \
         patch.object(mod, "publication_link", new=AsyncMock(return_value="https://www.facebook.com/123/posts/789")):
        asyncio.run(mod.run_due_posts())
    assert mod.editorial.get(fb["id"])["status"] == "published"
    failed = mod.editorial.get(ig["id"])
    assert failed["status"] == "needs_review"
    assert "secret-value" not in json.dumps(failed)


def test_target_change_blocks_approved_post(client, monkeypatch):
    item = approved(client)
    make_due(item)
    unpause(client)
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "999")
    asyncio.run(mod.run_due_posts())
    assert mod.editorial.get(item["id"])["status"] == "failed"


def test_comments_persist_as_review_drafts_even_when_auto_reply_flag_enabled(client, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_AUTO_REPLY_ENABLED", "true")
    body = {"object": "instagram", "entry": [{"id": "456", "changes": [{"field": "comments", "value": {
        "id": "789", "text": "Royal Shield password leaked", "from": {"username": "person"}, "media": {"id": "555"}}}]}]}
    raw = json.dumps(body).encode()
    headers = {"x-hub-signature-256": "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()}
    with patch.object(mod, "reply_comment", new=AsyncMock(side_effect=AssertionError("must not send"))):
        first = client.post("/webhook", content=raw, headers=headers)
        second = client.post("/webhook", content=raw, headers=headers)
    assert first.status_code == 200
    assert first.json()["auto_reply_queued"] == 0
    assert second.json()["duplicates_ignored"] == 1
    inbox = client.get("/editorial/comments", headers=HEADERS).json()
    assert len(inbox) == 1
    assert inbox[0]["status"] == "pending_review"
    assert inbox[0]["category"] == "urgent"


def test_legacy_post_cannot_bypass_editorial_approval(client):
    response = client.post("/posts", headers=HEADERS, json={"platform": "facebook", "caption": "No approval"})
    assert response.status_code == 409


def test_editorial_data_requires_authentication(client):
    assert client.get("/editorial/posts").status_code == 401
    assert client.get("/editorial/comments").status_code == 401


def test_legacy_queue_is_not_silently_published(client):
    mod.state.schedule(mod.PublishPayload(platform="facebook", caption="legacy", publish_at="2020-01-01T00:00:00Z"))
    unpause(client)
    assert asyncio.run(mod.run_due_posts())["checked"] == 0


def test_stale_dispatch_becomes_manual_review_without_resending(client):
    item = approved(client)
    make_due(item)
    unpause(client)
    mod.editorial.claim_due()
    with mod.editorial.connect() as conn:
        conn.execute("UPDATE editorial_posts SET started_at='2020-01-01T00:00:00+00:00' WHERE id=?", (item["id"],))
    assert mod.editorial.claim_due() is None
    assert mod.editorial.get(item["id"])["status"] == "needs_review"


def test_permalink_failure_can_be_recovered_with_read_only_retry(client):
    item = approved(client)
    make_due(item)
    unpause(client)
    with patch.object(mod, "publish", new=AsyncMock(return_value={"id": "123_789"})), \
         patch.object(mod, "publication_link", new=AsyncMock(side_effect=TimeoutError)):
        asyncio.run(mod.run_due_posts())
    assert mod.editorial.get(item["id"])["external_id"] == "123_789"
    with patch.object(mod, "publication_link", new=AsyncMock(return_value="https://www.facebook.com/123/posts/789")):
        response = client.post(f"/editorial/posts/{item['id']}/refresh-link", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["permalink"] == "https://www.facebook.com/123/posts/789"


def test_production_rejects_ephemeral_database(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    assert client.get("/editorial/posts", headers=HEADERS).status_code == 503


def test_unrelated_signed_page_event_is_not_stored(client):
    raw = json.dumps({"object": "instagram", "entry": [{"id": "999", "changes": [{"field": "comments", "value": {"id": "77", "text": "hello"}}]}]}).encode()
    signature = "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
    assert client.post("/webhook", content=raw, headers={"x-hub-signature-256": signature}).status_code == 200
    assert client.get("/editorial/comments", headers=HEADERS).json() == []


def test_private_media_urls_rejected(client):
    for url in ["https://127.0.0.1/a.jpg", "https://localhost/a.jpg", "https://user:pass@example.com/a.jpg", "https://[::1]/a.jpg"]:
        response = client.post("/editorial/posts", headers=HEADERS, json={"idempotency_key": "private", "platform": "instagram", "caption": "test", "image_url": url, "timezone": "UTC"})
        assert response.status_code == 422


def test_studio_available_without_exposing_keys(client):
    response = client.get("/studio")
    assert response.status_code == 200
    assert "test-editorial-key" not in response.text


def test_graph_read_keeps_credentials_out_of_urls(client):
    import httpx
    original = httpx.AsyncClient
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "123"})
    with patch.object(mod.httpx, "AsyncClient", side_effect=lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs)):
        result = asyncio.run(mod.graph_request("123", "private-test-token", {"fields": "id"}, method="GET"))
    assert result["id"] == "123"
    assert "private-test-token" not in str(requests[0].url)
    assert requests[0].headers["Authorization"] == "Bearer private-test-token"


@pytest.mark.parametrize("platform", ["page", "instagram"])
def test_malformed_signed_webhook_returns_validation_error(client, platform):
    for body in [{"object": platform, "entry": None}, {"object": platform, "entry": [{"id": "123", "changes": None}]}, {"object": platform, "entry": [None]}, {"object": platform, "entry": [{"changes": [None]}]}]:
        raw = json.dumps(body).encode()
        signature = "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
        assert client.post("/webhook", content=raw, headers={"x-hub-signature-256": signature}).status_code == 422


def test_administration_rate_limit_bounds_repeated_requests(client):
    mod.admin_requests.clear()
    try:
        for _ in range(120):
            assert client.get("/editorial/control", headers=HEADERS).status_code == 200
        assert client.get("/editorial/control", headers=HEADERS).status_code == 429
    finally:
        mod.admin_requests.clear()


def test_admin_limit_recovers_and_invalid_keys_do_not_block_valid_key(client):
    mod.admin_requests.clear()
    mod.admin_denied_requests.clear()
    try:
        with patch.object(mod.time, "monotonic", return_value=100):
            for _ in range(120):
                assert client.get("/editorial/control").status_code == 401
            assert client.get("/editorial/control").status_code == 429
            assert client.get("/editorial/control", headers=HEADERS).status_code == 200
            for _ in range(119):
                assert client.get("/editorial/control", headers=HEADERS).status_code == 200
            assert client.get("/editorial/control", headers=HEADERS).status_code == 429
        with patch.object(mod.time, "monotonic", return_value=160):
            assert client.get("/editorial/control", headers=HEADERS).status_code == 200
            assert client.get("/editorial/control").status_code == 401
    finally:
        mod.admin_requests.clear()
        mod.admin_denied_requests.clear()


def test_graph_error_preserves_diagnostics_without_credentials(client):
    import httpx
    original = httpx.AsyncClient
    def respond(request):
        return httpx.Response(400, json={"error": {
            "message": "Rejected private-test-token and test-secret",
            "type": "OAuthException", "code": 190, "error_subcode": 463,
            "fbtrace_id": "trace-test-123"}})
    with patch.object(mod.httpx, "AsyncClient", side_effect=lambda **kw: original(transport=httpx.MockTransport(respond), **kw)):
        with pytest.raises(mod.HTTPException) as error:
            asyncio.run(mod.graph_request("123", "private-test-token"))
    detail = error.value.detail
    assert detail["type"] == "OAuthException"
    assert detail["fbtrace_id"] == "trace-test-123"
    assert detail["code"] == 190 and detail["error_subcode"] == 463
    assert "Rejected" in detail["message"]
    assert "private-test-token" not in json.dumps(detail)
    assert "test-secret" not in json.dumps(detail)
