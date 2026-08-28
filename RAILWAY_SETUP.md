# Railway deployment - standalone Meta automation

This service runs directly on Railway and talks to Meta Graph API. There is no Make.com dependency.

## 1. Service

Deploy `royalshieldapp/SOCIALMEDIAAUTOMATION` from GitHub. The Docker/Railway start command launches:

```bash
python scheduler_daemon.py & exec uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port ${PORT:-8000}
```

Railway injects `PORT`; do not hardcode a public port.

## 2. Variables

Add:

```env
META_VERIFY_TOKEN=<random-token>
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

Keep tokens and secrets only in Railway/Meta. Never commit them.

For Facebook Login with a linked Instagram Professional account, keep `INSTAGRAM_GRAPH_HOST=graph.facebook.com`. If the app later moves to Instagram Login with an Instagram user access token, set `INSTAGRAM_GRAPH_HOST=graph.instagram.com` and set `INSTAGRAM_ACCESS_TOKEN`.

## 3. Volume

Attach a Railway Volume mounted at `/data`. This makes SQLite state durable for webhook deduplication, scheduled posts, and retry status.

Without a Volume the app still starts, but state can disappear when the container is replaced.

## 4. Health check

The repository health check is:

```text
/health
```

After deploy verify:

```text
https://<your-domain>/health
https://<your-domain>/config
```

`/config` reports configuration status without returning token values.

## 5. Meta webhook

Use:

```text
https://<your-domain>/webhook
```

Use the same `META_VERIFY_TOKEN` in Meta and Railway. POST webhook events must include a valid `X-Hub-Signature-256` generated with `META_APP_SECRET`.

## 6. Scheduler

No external cron provider is required. `scheduler_daemon.py` runs in the same Railway container and calls `/scheduler/run` on localhost every `SCHEDULER_POLL_SECONDS` seconds.

Future posts submitted to `POST /posts` are stored in SQLite until due. Failed scheduled jobs are retried and marked failed after five attempts.

## 7. Safe rollout

Keep both auto-reply switches `false` for the first deployment. Verify manual publishing and comment replies first, then enable Facebook and Instagram auto-replies one at a time.
