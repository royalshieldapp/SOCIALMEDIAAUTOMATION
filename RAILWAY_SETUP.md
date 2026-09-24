# Railway deployment - standalone Meta automation

This service runs directly on Railway and talks to Meta Graph API. There is no Make.com dependency.

## 1. Service

Deploy `royalshieldapp/SOCIALMEDIAAUTOMATION` from GitHub. The Docker/Railway start command launches:

```bash
exec uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port ${PORT:-8000}
```

Railway injects `PORT`; do not hardcode a public port.
FastAPI lifespan starts and stops the existing scheduler companion. Do not launch
an additional `scheduler_daemon.py` process. Keep one Uvicorn worker and one replica
for this SQLite deployment. Check any Railway dashboard start-command override.

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
SCHEDULER_ENABLED=false
SCHEDULER_POLL_SECONDS=30
ENVIRONMENT=production
```

Keep tokens and secrets only in Railway/Meta. Never commit them.

For Facebook Login with a linked Instagram Professional account, keep `INSTAGRAM_GRAPH_HOST=graph.facebook.com`. If the app later moves to Instagram Login with an Instagram user access token, set `INSTAGRAM_GRAPH_HOST=graph.instagram.com` and set `INSTAGRAM_ACCESS_TOKEN`.

## 3. Volume

Attach a Railway Volume mounted at `/data`. This makes SQLite state durable for webhook deduplication, scheduled posts, and retry status.

Production editorial operations fail with HTTP 503 unless `SCHEDULE_DB_PATH` is
inside `RAILWAY_VOLUME_MOUNT_PATH`. A directory created in the image is not a
volume. Confirm the mount in Railway and test persistence after a restart.
Do not create a paid service or volume without explicit spending authorization.

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

No external cron provider is required. The supervised `scheduler_daemon.py` task
calls `/scheduler/run` on localhost, waits for the whole cycle, then waits
`SCHEDULER_POLL_SECONDS`. It reports HTTP failures without logging response bodies
or credentials. `/health` fails if an enabled worker exits. Health does not verify
Meta permissions or publication. Use authenticated `GET /scheduler/status` to
see actual cycle timestamps, results, queue counts and worker state.

Use `/studio` or these authenticated routes with `x-automation-key`:

1. `POST /editorial/posts`: immutable draft, platform, caption, media, idempotency
   key and IANA timezone (default `America/New_York`). Destination is captured.
2. `POST /editorial/posts/{id}/approve`: only after editorial review.
3. `POST /editorial/posts/{id}/schedule`: approved future timestamp with the
   correct offset for that timezone. Facebook and Instagram use separate rows.
4. `GET /editorial/posts` and `GET /scheduler/status`: inspect the exact content,
   targets, schedules and overdue count before activation.
5. Set `SCHEDULER_ENABLED=true` in the existing service only after production
   checks, deploy, then keep the editorial pause until the queue is reviewed.
6. `POST /editorial/control` with `{"paused":false}` releases only approved
   scheduled rows. Confirm fresh cycle timestamps and provider IDs individually.

Rows more than 15 minutes late go to `needs_review`, not to publication. Review
and create/approve a new schedule only after reconciling the original result.
Interrupted writes, timeouts and incomplete responses are never blindly retried.
Instagram container IDs are saved before the publish call. Container readiness is
read with GET before publishing images or video. A stored container is not proof
of a published post. Confirm the media ID and permalink in Meta.

`POST /editorial/posts/{id}/refresh-link` retries only a GET for a known published
ID. Check `GET /{container_id}?fields=status_code,status` using the configured
Graph host/version when an Instagram result is ambiguous; do not call
`media_publish` again as a diagnostic. If the publication ID is unknown, reconcile
in Meta before any replacement draft is approved.

The legacy queue is preserved but is never released automatically. Legacy direct
publishing routes return 409 so they cannot bypass approval.

## 7. Safe rollout

Keep both auto-reply switches `false`. Signed comments are saved as review drafts,
even if a legacy switch is true. Validate real webhook delivery independently;
do not block publication on optional comments. No automatic replies are enabled.

Before activation validate token identity/permissions, Page identity, Instagram
identity and the Page linkage required by Facebook Login. Matching business
portfolio IDs is insufficient. Use the configured API version and never print
tokens. Public media must return 200 and the correct media type externally.

There is no approved production test schedule in the September 13 checkpoint.
Do not publish its demo merely because it is bundled in the image.

## 8. Pause and rollback

`POST /editorial/control` with `{"paused":true}` prevents new claims. Already
in-flight provider requests may finish: inspect IDs and `needs_review` before
restarting. Set `SCHEDULER_ENABLED=false` for the next deployment to stop cycles.
Retain and back up the actual volume. Schema changes are additive; no old queue
is deleted. Do not roll back to the pre-editorial build with automation enabled:
it has routes and reply behavior that bypass editorial approval. Leave both
auto-reply flags and scheduler disabled if an older image must be restored.
