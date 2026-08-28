# Royal Shield Social Media Automation

Standalone FastAPI backend for Royal Shield social-media automation on Railway.
It connects directly to Meta Graph API for Facebook and Instagram. **Make.com is not required.**

## What it does

- Verifies Meta webhooks with `META_VERIFY_TOKEN` and `X-Hub-Signature-256`.
- Publishes Facebook text, image, and video posts directly.
- Publishes Instagram images and Reels using media container -> `media_publish`.
- Replies directly to Facebook and Instagram comments.
- Auto-classifies incoming comments and can auto-reply.
- Deduplicates webhook comment retries with SQLite.
- Stores future posts in SQLite and runs the scheduler companion inside the same Railway container.
- Protects mutating internal endpoints with `AUTOMATION_API_KEY` and fails closed if the key is missing.

## Main endpoints

- `GET /health`
- `GET /config`
- `GET /webhook` - Meta verification challenge
- `POST /webhook` - signed Meta events only
- `POST /posts` - publish or schedule Facebook/Instagram
- `POST /facebook/posts`
- `POST /instagram/posts`
- `POST /facebook/comments/{comment_id}/reply`
- `POST /instagram/comments/{comment_id}/reply`
- `POST /scheduler/run`

Internal POST endpoints require:

```http
x-automation-key: <AUTOMATION_API_KEY>
```

## Local run

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port 8000 --reload --env-file .env
```

## Railway variables

Configure at minimum:

```env
META_VERIFY_TOKEN=<random-token-used-also-in-meta>
META_APP_SECRET=<meta-app-secret>
META_GRAPH_API_VERSION=v25.0
AUTOMATION_API_KEY=<long-random-secret>
FACEBOOK_PAGE_ID=<page-id>
FACEBOOK_PAGE_ACCESS_TOKEN=<page-token>
FACEBOOK_AUTO_REPLY_ENABLED=false
INSTAGRAM_BUSINESS_ACCOUNT_ID=<instagram-professional-account-id>
INSTAGRAM_GRAPH_HOST=graph.facebook.com
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_AUTO_REPLY_ENABLED=false
SCHEDULE_DB_PATH=/data/socialmediaautomation.db
SCHEDULER_ENABLED=true
SCHEDULER_POLL_SECONDS=30
ENVIRONMENT=production
```

Do not put real tokens or secrets in GitHub.

## Instagram login mode

This backend supports both current Meta host patterns:

- Facebook Login for Business: `INSTAGRAM_GRAPH_HOST=graph.facebook.com`
- Instagram Login: `INSTAGRAM_GRAPH_HOST=graph.instagram.com`

Royal Shield currently defaults to Facebook Login because the Instagram Professional account is expected to be linked to a Facebook Page. If a separate Instagram Login token is used, set `INSTAGRAM_ACCESS_TOKEN` and switch the host accordingly.

## Railway Volume

Scheduling and webhook deduplication use SQLite. Attach a Railway Volume mounted at `/data` and keep:

```env
SCHEDULE_DB_PATH=/data/socialmediaautomation.db
```

Without a Volume the app can still run, but scheduled/deduplication state can disappear when the container is replaced.

## Scheduler

`scheduler_daemon.py` runs beside Uvicorn in the same container and calls the protected scheduler endpoint on localhost. No external automation provider is required.

To disable it temporarily:

```env
SCHEDULER_ENABLED=false
```

## Safe rollout

1. Merge the tested branch to `main`.
2. Let Railway deploy `main`.
3. Add the new environment variables.
4. Attach the `/data` Volume before relying on scheduling/deduplication.
5. Keep Facebook and Instagram auto-replies `false` initially.
6. Verify `/health` and `/config`.
7. Verify the Meta callback URL: `https://<railway-domain>/webhook`.
8. Test one Facebook post, one Instagram post, and one manual comment reply on each platform.
9. Enable auto-replies one platform at a time.

## Tests

```bash
python -m py_compile SOCIALMEDIAAUTOMATION.py scheduler_daemon.py
python -m pytest
```
