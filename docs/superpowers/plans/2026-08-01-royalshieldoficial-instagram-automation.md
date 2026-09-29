# @royalshieldsecure Instagram Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not dispatch subagents because this workspace does not authorize delegation.

**Goal:** Connect `@royalshieldsecure` to the existing Royal Shield Facebook/Meta assets and deliver verified Instagram publishing, safe comment automation, and an English organic-content system without paid ads or artificial engagement.

**Architecture:** Start from the current `origin/main` Facebook automation in an isolated worktree so the divergent local commit and dirty files remain untouched. Make and Google Sheets schedule approved content; the FastAPI backend validates requests and performs or normalizes official Meta Graph API operations; Meta webhooks drive comment classification and low-risk replies. External account changes are performed only through the user's authenticated browser session, and end-to-end success requires visible Meta results.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx, pytest/unittest, Meta Graph API, Instagram API with Facebook Login, Make.com, Railway, Google Sheets/XLSX.

## Global Constraints

- Keep `SOCIALMEDIAAUTOMATION` strictly separate from the Royal Shield Android/backend repositories.
- Content language is English; brand voice is premium, clear, useful, and non-alarmist.
- Growth is organic only: no paid ads, purchased followers, follow/unfollow, bulk likes, scraping, or unsolicited mass messaging.
- Only low-risk public engagement can auto-reply; support, prices, privacy, payments, compromised accounts, threats, minors, legal claims, and vulnerabilities require human review.
- Never log or commit credentials, full tokens, Meta App Secret, Make secret, or private user data.
- Do not modify or overwrite the existing dirty `main` checkout.
- Do not commit, push, deploy, spend money, or delete data without explicit user authorization.
- Local tests, `/health`, and `/config` are not end-to-end proof.
- Use official Meta endpoints for the Facebook Login model: `graph.facebook.com`, a Facebook Page access token, the linked Instagram Business Account ID, and the configured Graph API version.

---

### Task 1: Create a safe implementation worktree from current `origin/main`

**Files:**
- Preserve: `D:/APPS/SOCIALMEDIAAUTOMATION/railway.toml`
- Preserve: `D:/APPS/SOCIALMEDIAAUTOMATION/tests/test_backend.py`
- Preserve: `D:/APPS/SOCIALMEDIAAUTOMATION/.codex/`
- Preserve: `D:/APPS/SOCIALMEDIAAUTOMATION/docs/`
- Create worktree: `C:/Users/Anonymous/.codex/worktrees/instagram-automation/SOCIALMEDIAAUTOMATION`

**Interfaces:**
- Consumes: fetched `origin/main` at the current remote tip.
- Produces: branch `codex/instagram-automation` with a clean worktree; no merge into local `main`.

- [ ] **Step 1: Record current state without printing secrets**

```powershell
git status --short --branch
git log -1 --oneline HEAD
git log -1 --oneline origin/main
git diff --name-only
```

- [ ] **Step 2: Read `using-git-worktrees` and create the isolated worktree**

```powershell
git worktree add -b codex/instagram-automation "C:\Users\Anonymous\.codex\worktrees\instagram-automation\SOCIALMEDIAAUTOMATION" origin/main
```

- [ ] **Step 3: Verify isolation**

```powershell
git -C "C:\Users\Anonymous\.codex\worktrees\instagram-automation\SOCIALMEDIAAUTOMATION" status --short --branch
git status --short --branch
```

Expected: the new worktree is clean on `codex/instagram-automation`; the original checkout retains all prior modifications and untracked files.

- [ ] **Step 4: Run the remote baseline tests**

```powershell
python -m pytest -q
```

Expected: all baseline tests pass. If they fail, stop feature edits and use `systematic-debugging` to separate baseline failures from new work.

- [ ] **Step 5: Review checkpoint**

Record the branch, worktree, baseline test count, and any pre-existing failure. Do not commit.

---

### Task 2: Enforce the approved human-review policy and English replies

**Files:**
- Modify: `SOCIALMEDIAAUTOMATION.py`
- Modify: `tests/test_SOCIALMEDIAAUTOMATION.py`
- Modify: `tests/test_backend.py`

**Interfaces:**
- Consumes: existing `Category`, `Action`, `CommentPayload`, `classify_comment()`.
- Produces: `action_for_category(category: Category) -> Action`, `classify_comment(text: str) -> Category`, and `generate_reply(category: Category, payload: CommentPayload) -> str` matching the approved safety policy.

- [ ] **Step 1: Write failing policy tests**

```python
def test_only_low_risk_public_engagement_auto_replies():
    assert action_for_category("comentario_publico") == "auto_reply"
    assert action_for_category("urgent") == "manual_review"
    assert action_for_category("lead") == "manual_review"
    assert action_for_category("soporte") == "manual_review"
    assert action_for_category("spam") == "manual_review"
    assert action_for_category("irrelevante") == "ignore"


def test_public_reply_is_english_and_does_not_claim_total_protection():
    payload = CommentPayload(
        platform="instagram",
        comment_id="comment_1",
        comment_text="Great tip",
        user_name="Alex Morgan",
    )
    reply = generate_reply("comentario_publico", payload)
    assert reply == "Thanks, Alex! We appreciate you being part of the Royal Shield community."
    assert "100%" not in reply
    assert "guarantee" not in reply.lower()


@pytest.mark.parametrize(
    "text",
    [
        "My account was hacked",
        "I found a security vulnerability",
        "A child shared private information",
        "I was charged twice",
        "My personal data was exposed",
    ],
)
def test_sensitive_english_comments_require_human_review(text):
    category = classify_comment(text)
    assert action_for_category(category) == "manual_review"
```

- [ ] **Step 2: Run the focused tests and confirm RED**

```powershell
python -m pytest tests/test_SOCIALMEDIAAUTOMATION.py -k "only_low_risk or public_reply_is_english or sensitive_english" -q
```

Expected: failures because urgent/lead/support currently auto-reply, replies are Spanish, and English sensitive terms are not classified consistently.

- [ ] **Step 3: Implement the minimal policy**

```python
def action_for_category(category: Category) -> Action:
    if category == "comentario_publico":
        return "auto_reply"
    if category in {"urgent", "lead", "soporte", "spam"}:
        return "manual_review"
    return "ignore"


SENSITIVE_URGENT_TERMS = {
    "hacked",
    "compromised",
    "vulnerability",
    "child",
    "minor",
    "charged",
    "payment",
    "private information",
    "personal data",
    "exposed",
}


def generate_reply(category: Category, payload: CommentPayload) -> str:
    name = payload.user_name.split()[0] if payload.user_name else "there"
    if category == "comentario_publico":
        return (
            f"Thanks, {name}! We appreciate you being part of the "
            "Royal Shield community."
        )
    return (
        f"Thanks, {name}. Our team will review your comment and follow up "
        "through an appropriate official channel."
    )
```

Check `SENSITIVE_URGENT_TERMS` before low-risk engagement keywords in `classify_comment()` and return `urgent`, which is always routed to `manual_review`.

- [ ] **Step 4: Update older assertions that encoded unsafe auto-replies**

Change only expectations for `urgent`, `lead`, and `soporte`; preserve unrelated test coverage.

- [ ] **Step 5: Run policy and full tests**

```powershell
python -m pytest tests/test_SOCIALMEDIAAUTOMATION.py tests/test_backend.py -q
```

Expected: PASS.

- [ ] **Step 6: Review checkpoint**

Confirm that no sensitive category can enter the auto-reply path. Do not commit.

---

### Task 3: Add secure Instagram configuration and Graph API request boundaries

**Files:**
- Modify: `SOCIALMEDIAAUTOMATION.py`
- Modify: `.env.example`
- Modify: `tests/test_backend.py`

**Interfaces:**
- Consumes: `get_meta_graph_api_version()`, `app_secret_proof()`, `META_REQUEST_TIMEOUT_SECONDS`.
- Produces:
  - `require_instagram_config() -> tuple[str, str]`
  - `instagram_graph_request(method: Literal["GET", "POST"], edge: str, data: Dict[str, Any]) -> Dict[str, Any]`

- [ ] **Step 1: Write failing configuration tests**

```python
def test_instagram_config_requires_business_account_id_and_page_token(self):
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(HTTPException) as exc:
            require_instagram_config()
    assert exc.value.status_code == 503
    assert exc.value.detail == "Instagram publishing is not configured"


def test_config_reports_instagram_flags_without_values(client):
    with patch.dict(
        os.environ,
        {
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "ig-1",
            "FACEBOOK_PAGE_ACCESS_TOKEN": "page-token",
            "INSTAGRAM_AUTO_REPLY_ENABLED": "false",
        },
        clear=False,
    ):
        body = client.get("/config").json()["configured"]
    assert body["INSTAGRAM_BUSINESS_ACCOUNT_ID"] is True
    assert body["INSTAGRAM_PAGE_ACCESS_TOKEN"] is True
    assert "page-token" not in str(body)
```

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_backend.py -k "instagram_config or instagram_flags" -q
```

- [ ] **Step 3: Implement fail-closed configuration**

```python
def require_instagram_config() -> tuple[str, str]:
    ig_user_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    access_token = (
        os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN")
        or os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
        or ""
    ).strip()
    if not ig_user_id or not access_token:
        raise HTTPException(
            status_code=503,
            detail="Instagram publishing is not configured",
        )
    if not re.fullmatch(META_ID_PATTERN, ig_user_id):
        raise HTTPException(status_code=503, detail="Instagram account ID is invalid")
    return ig_user_id, access_token
```

- [ ] **Step 4: Implement the request wrapper**

Use `Authorization: Bearer <token>` rather than placing the token in a logged URL. Accept only `GET` and `POST`; sanitize Meta errors to `Meta Graph API rejected the Instagram request`; log only status code and Meta error type.

```python
async def instagram_graph_request(
    method: Literal["GET", "POST"],
    edge: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    _, access_token = require_instagram_config()
    version = get_meta_graph_api_version()
    url = f"https://graph.facebook.com/{version}/{edge.lstrip('/')}"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient(
            timeout=META_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = await client.request(method, url, data=data, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Meta Graph API is temporarily unavailable",
        ) from exc
    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Meta Graph API returned an invalid response",
        ) from exc
    if response.is_error or not isinstance(result, dict) or result.get("error"):
        raise HTTPException(
            status_code=502,
            detail="Meta Graph API rejected the Instagram request",
        )
    return result
```

- [ ] **Step 5: Ensure `.env.example` contains the names once, without real values**

```dotenv
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_business_account_id_here
INSTAGRAM_PAGE_ACCESS_TOKEN=your_instagram_page_access_token_here
INSTAGRAM_AUTO_REPLY_ENABLED=false
```

- [ ] **Step 6: Test success, timeout, malformed JSON, and redaction paths**

Run:

```powershell
python -m pytest tests/test_backend.py -k "instagram" -q
```

Expected: PASS; no token appears in captured logs or `/config`.

- [ ] **Step 7: Review checkpoint**

Confirm the host and token model match Instagram API with Facebook Login. Do not commit.

---

### Task 4: Add Instagram image, carousel, and Reel container endpoints for Make

**Files:**
- Modify: `SOCIALMEDIAAUTOMATION.py`
- Modify: `tests/test_backend.py`

**Interfaces:**
- Consumes: `instagram_graph_request()`, `verify_make_secret()`, `require_instagram_config()`.
- Produces:
  - `InstagramContainerPayload(format: Literal["image", "carousel", "reel"], caption: str, media_url: Optional[str], carousel_urls: List[str], share_to_feed: bool = True)`
  - `POST /instagram/media/containers`
  - `GET /instagram/media/containers/{container_id}`
  - `POST /instagram/media/publish/{container_id}`

- [ ] **Step 1: Write failing image-container test**

```python
def test_instagram_image_container_calls_official_media_edge(client):
    with patch(
        "SOCIALMEDIAAUTOMATION.instagram_graph_request",
        new=AsyncMock(return_value={"id": "container_1"}),
    ) as graph_request:
        response = client.post(
            "/instagram/media/containers",
            headers={"x-make-secret": "make-secret"},
            json={
                "format": "image",
                "caption": "Protect your digital life with practical habits.",
                "media_url": "https://cdn.example.com/post.jpg",
            },
        )
    assert response.status_code == 200
    graph_request.assert_awaited_once_with(
        method="POST",
        edge="ig-1/media",
        data={
            "image_url": "https://cdn.example.com/post.jpg",
            "caption": "Protect your digital life with practical habits.",
        },
    )
```

- [ ] **Step 2: Write failing Reel-container test**

```python
def test_instagram_reel_container_sets_reels_and_share_to_feed(client):
    with patch(
        "SOCIALMEDIAAUTOMATION.instagram_graph_request",
        new=AsyncMock(return_value={"id": "container_2"}),
    ) as graph_request:
        response = client.post(
            "/instagram/media/containers",
            headers={"x-make-secret": "make-secret"},
            json={
                "format": "reel",
                "caption": "Three signs a message may be a scam.",
                "media_url": "https://cdn.example.com/reel.mp4",
                "share_to_feed": True,
            },
        )
    assert response.status_code == 200
    assert graph_request.await_args.kwargs["data"]["media_type"] == "REELS"
    assert graph_request.await_args.kwargs["data"]["share_to_feed"] == "true"
```

- [ ] **Step 3: Write failing image-carousel test**

```python
def test_instagram_carousel_creates_children_then_parent(client):
    graph_results = [
        {"id": "child_1"},
        {"id": "child_2"},
        {"id": "carousel_1"},
    ]
    with patch(
        "SOCIALMEDIAAUTOMATION.instagram_graph_request",
        new=AsyncMock(side_effect=graph_results),
    ) as graph_request:
        response = client.post(
            "/instagram/media/containers",
            headers={"x-make-secret": "make-secret"},
            json={
                "format": "carousel",
                "caption": "Three privacy checks to make today.",
                "carousel_urls": [
                    "https://cdn.example.com/check-1.jpg",
                    "https://cdn.example.com/check-2.jpg",
                ],
            },
        )
    assert response.status_code == 200
    assert graph_request.await_count == 3
    assert graph_request.await_args_list[-1].kwargs["data"] == {
        "media_type": "CAROUSEL",
        "children": "child_1,child_2",
        "caption": "Three privacy checks to make today.",
    }
```

- [ ] **Step 4: Run the container tests and confirm RED**

```powershell
python -m pytest tests/test_backend.py -k "instagram_image_container or instagram_reel_container or instagram_carousel" -q
```

- [ ] **Step 5: Implement strict payload validation**

```python
class InstagramContainerPayload(BaseModel):
    format: Literal["image", "carousel", "reel"]
    caption: str = Field(..., min_length=1, max_length=2200)
    media_url: Optional[str] = None
    carousel_urls: List[str] = Field(default_factory=list, max_length=10)
    share_to_feed: bool = True

    @field_validator("media_url")
    @classmethod
    def validate_media_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not re.fullmatch(r"https://[^\s]+", value.strip()):
            raise ValueError("media_url must be a public HTTPS URL")
        return value.strip()
```

Add a model-level validator: image/Reel require exactly one `media_url` and no `carousel_urls`; carousel requires 2–10 public HTTPS image URLs and no `media_url`.

- [ ] **Step 6: Implement container, status, and publish endpoints**

For image containers send `image_url` and `caption`. For Reels send `media_type=REELS`, `video_url`, `caption`, and lowercase `share_to_feed`. For carousels, create 2–10 image children with `is_carousel_item=true`, collect only real returned child IDs, then create the parent with `media_type=CAROUSEL`, comma-separated `children`, and `caption`. Status calls `GET /{container_id}` with `fields=status_code,status`. Publish calls `POST /{ig_user_id}/media_publish` with `creation_id`.

- [ ] **Step 7: Add failure tests**

Test: missing/incorrect `x-make-secret`, HTTP media URL, one-item/eleven-item carousel, mixed `media_url` and `carousel_urls`, invalid container ID, Meta `ERROR` status, Meta rejection, and absence of a returned real `id`.

- [ ] **Step 8: Run focused and full tests**

```powershell
python -m pytest tests/test_backend.py -k "instagram" -q
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 9: Review checkpoint**

Verify endpoints return `created`, `processing`, `finished`, or `published` according to actual Meta output and never fabricate success. Do not commit.

---

### Task 5: Normalize Instagram comment webhooks and auto-reply only to low-risk comments

**Files:**
- Modify: `SOCIALMEDIAAUTOMATION.py`
- Modify: `tests/test_backend.py`

**Interfaces:**
- Consumes: `verify_meta_signature()`, `CommentPayload`, `classify_comment()`, `action_for_category()`, `generate_reply()`, `instagram_graph_request()`.
- Produces:
  - `extract_instagram_comment_events(body: Dict[str, Any]) -> List[CommentPayload]`
  - `reply_to_instagram_comment(comment_id: str, message: str) -> Dict[str, Any]`
  - native webhook response fields `instagram_comment_events` and `instagram_auto_replies_queued`.

- [ ] **Step 1: Write failing webhook-normalization test using Meta's current payload shape**

```python
def test_extracts_current_instagram_comment_webhook_shape():
    body = {
        "object": "instagram",
        "entry": [{
            "id": "ig-1",
            "time": 1785636000,
            "field": "comments",
            "value": {
                "id": "comment_1",
                "from": {"username": "alex"},
                "text": "Great privacy tip!",
                "media": {"id": "media_1", "media_product_type": "FEED"},
            },
        }],
    }
    events = extract_instagram_comment_events(body)
    assert len(events) == 1
    assert events[0].platform == "instagram"
    assert events[0].comment_id == "comment_1"
    assert events[0].post_id == "media_1"
```

- [ ] **Step 2: Write failing safety-routing test**

```python
async def test_instagram_support_comment_is_never_auto_replied():
    payload = CommentPayload(
        platform="instagram",
        comment_id="comment_2",
        comment_text="My account was hacked",
        user_name="sam",
    )
    await process_instagram_comment_events([payload])
    instagram_graph_request.assert_not_awaited()
```

- [ ] **Step 3: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_backend.py -k "instagram_comment or support_comment" -q
```

- [ ] **Step 4: Implement extraction with strict object, field, ID, and text checks**

Accept the current `entry[].field/value` shape and the older `entry[].changes[]` shape only when all required fields are present. Ignore self-generated events and malformed items.

- [ ] **Step 5: Implement public reply through the official comment edge**

```python
async def reply_to_instagram_comment(comment_id: str, message: str) -> Dict[str, Any]:
    if not re.fullmatch(META_ID_PATTERN, comment_id):
        raise HTTPException(status_code=422, detail="Invalid Instagram comment ID")
    return await instagram_graph_request(
        method="POST",
        edge=f"{comment_id}/replies",
        data={"message": message},
    )
```

- [ ] **Step 6: Gate background replies**

Queue a reply only when all conditions are true: signature valid, `INSTAGRAM_AUTO_REPLY_ENABLED=true`, category action equals `auto_reply`, comment ID is valid, and the event is not a duplicate within the process-level idempotency cache. Sensitive categories return `pending_review` metrics without calling Meta. Document that this cache prevents immediate duplicate deliveries only; it is not durable across Railway restarts or multiple instances. Production activation must additionally use a Make Data Store or another approved durable store keyed by comment/event ID.

- [ ] **Step 7: Test valid signature, invalid signature, disabled flag, duplicate event, Meta error, and low-risk success**

```powershell
python -m pytest tests/test_backend.py -k "instagram" -q
python -m pytest -q
```

Expected: PASS; only public low-risk engagement reaches `/{comment_id}/replies`.

- [ ] **Step 8: Review checkpoint**

Confirm no private-reply or unsolicited-DM endpoint was added. Do not commit.

---

### Task 6: Create the English organic content calendar and approval artifact

**Files:**
- Create: `outputs/019fc061-7c4b-7af0-8a07-f7ff18fad375/royalshieldoficial_30_day_calendar.xlsx`
- Create: `content/royalshieldoficial_copy_pack.md`
- Create: `content/README.md`

**Interfaces:**
- Consumes: approved audience segments, content pillars, English voice, and status model.
- Produces: a Make/Google Sheets-ready editorial queue with unique `Content ID` values and an approval gate.

- [ ] **Step 1: Read the `spreadsheets` skill and load the bundled workspace dependencies**

Use the provided spreadsheet runtime; do not handcraft an invalid XLSX archive.

- [ ] **Step 2: Create workbook columns**

Use these operational columns (the source register may add `Source URL`):

```text
Content ID | Audience Segment | Content Pillar | Format | Hook | Caption | Media Brief | Media URL | Publish At | Approval Status | Publish Status | Meta Media ID | Published At | Error Summary | Source URL
```

- [ ] **Step 3: Populate a 30-day launch queue**

Create 18 feed entries: 8 images, 6 carousels, and 4 Reels. Every caption is English, factual, includes one natural CTA, names one primary segment, and avoids total-protection claims. Set `Approval Status=draft`, `Publish Status=draft`, and leave all IDs/results empty.

- [ ] **Step 4: Add validation and conditional formatting**

- `Approval Status`: `draft,pending_review,approved,cancelled`
- `Publish Status`: `draft,publishing,published,failed,cancelled`
- Highlight `approved` green, `failed` red, and missing media on approved rows amber.
- Freeze headers and enable filters.

- [ ] **Step 5: Create the copy pack**

Include the proposed English bio, five content pillars, response templates for low-risk public comments, escalation language, and prohibited claims.

- [ ] **Step 6: Verify workbook structure and render representative sheets**

Confirm 18 unique content IDs, no approved rows, no populated Meta IDs, valid dropdowns, readable widths, and no formula errors.

- [ ] **Step 7: Review checkpoint**

Do not upload the workbook or publish any content. Do not commit.

---

### Task 7: Update configuration and operator documentation

**Files:**
- Modify: `README.md`
- Modify: `MAKE_SETUP.md`
- Modify: `RAILWAY_SETUP.md`
- Modify: `.env.example`
- Create: `docs/INSTAGRAM_ROYALSHIELDOFICIAL_RUNBOOK.md`

**Interfaces:**
- Consumes: Tasks 2–6 endpoint and field names.
- Produces: exact setup steps for Meta, Make, Railway, and the first real test.

- [ ] **Step 1: Document the Make scenario**

Flow:

```text
Google Sheets approved row
  -> POST /instagram/media/containers
  -> poll GET /instagram/media/containers/{container_id}
  -> POST /instagram/media/publish/{container_id}
  -> update Meta Media ID, Published At, Publish Status, Error Summary
```

Require `x-make-secret`; retry only processing/timeouts; query status before retrying publish.

- [ ] **Step 2: Document the comment flow**

Meta `comments` webhook -> signed `/webhook` -> classification -> low-risk public reply or `pending_review`. State explicitly that support, pricing, security incidents, privacy, payments, minors, and legal issues do not auto-reply.

- [ ] **Step 3: Document Meta permissions and assets without hardcoding IDs**

List the required linked Page, Instagram Business Account ID, Page access token, webhook `comments`, and necessary Instagram/Page permissions. Tell the operator to read the actual IDs from Meta and store values only in Railway/Make.

- [ ] **Step 4: Document rollout and rollback toggles**

Start with `INSTAGRAM_AUTO_REPLY_ENABLED=false`. Rollback disables Make scheduling and the flag, then verifies no new activity; revoking the token is the emergency stop.

- [ ] **Step 5: Run documentation consistency checks**

```powershell
rg -n "INSTAGRAM_|/instagram/|pending_review|x-make-secret" README.md MAKE_SETUP.md RAILWAY_SETUP.md docs/INSTAGRAM_ROYALSHIELDOFICIAL_RUNBOOK.md .env.example
rg -n "your_.*_here|example.com" .env.example docs/INSTAGRAM_ROYALSHIELDOFICIAL_RUNBOOK.md
```

Expected: names match code; only explicit placeholder examples appear; no real secret is present.

- [ ] **Step 6: Run the complete local verification suite**

```powershell
python -m pytest -q
python -m compileall -q SOCIALMEDIAAUTOMATION.py
```

Expected: PASS.

- [ ] **Step 7: Review checkpoint**

Summarize changed files and test evidence. Do not commit.

---

### Task 8: Configure authenticated services and prove the real end-to-end flow

**Files:**
- Read only: local runbook and test artifacts.
- External state: Instagram, Facebook Page, Meta Business, Meta App, Make scenario, Railway variables.

**Interfaces:**
- Consumes: authenticated user sessions, verified account IDs, tested endpoints, approved content row.
- Produces: a linked Business account and real evidence for one post and two comment paths.

- [ ] **Step 1: Read the `chrome` control skill before using the user's session**

Never type, reveal, or copy passwords, MFA codes, App Secret, or full tokens into chat/tool output. Pause if Meta requests authentication or a security decision only the user can complete.

- [ ] **Step 2: Convert and secure Instagram**

Convert `@royalshieldsecure` to Business, confirm it is public, enable 2FA, review active sessions, and complete the approved English profile fields. Record only non-secret evidence.

- [ ] **Step 3: Link the existing Facebook Page**

From Page settings or Instagram professional settings, link the exact existing Royal Shield Page and verify the same relationship in Meta Business. Do not create a duplicate Page.

- [ ] **Step 4: Connect the Meta App**

Verify Page and Instagram IDs from Meta; configure the signed callback; subscribe to Instagram `comments`; confirm permissions and token ownership. Enter secrets directly in protected dashboards.

- [ ] **Step 5: Configure Railway without deploying code**

Prepare the required variable list. Only change Railway values when the implementation is deployed from an authorized commit; do not point production to uncommitted local code.

- [ ] **Step 6: Configure Make without activating production scheduling**

Connect `@royalshieldsecure`, map the workbook/Google Sheet fields, add the `x-make-secret` header, and keep the scenario inactive until a controlled test row is approved.

- [ ] **Step 7: Run controlled E2E tests after explicit deploy authorization**

1. Publish one approved image and verify it is visible in Instagram.
2. Record the real Meta Media ID and timestamp.
3. Add a benign comment from a separate real account and verify one public reply.
4. Add a support/security test comment and verify it remains `pending_review` with no public reply.
5. Replay the webhook and verify no duplicate response.

- [ ] **Step 8: Activate gradual rollout**

Enable only approved scheduled rows. Keep `INSTAGRAM_AUTO_REPLY_ENABLED=false` during the first supervised comment cycle; enable it only after the safety test passes. Monitor daily at launch.

- [ ] **Step 9: Final evidence report**

Report facts separately: linked assets, deployed commit, Make scenario state, real post URL/ID, real reply ID, blocked sensitive comment, and unresolved permissions. Do not claim completion for any unverified layer.
