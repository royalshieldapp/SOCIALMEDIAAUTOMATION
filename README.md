# SOCIALMEDIAAUTOMATION

## Railway

Start command:

```bash
uvicorn SOCIALMEDIAAUTOMATION:app --host 0.0.0.0 --port ${PORT:-8000}
```

## Endpoints

- `GET /health`
- `POST /webhook`

## Make.com HTTP module

Use:

```text
POST https://YOUR-APP.up.railway.app/webhook
Content-Type: application/json
Timeout: 30 seconds
```

For comment classification:

```json
{
  "platform": "instagram",
  "comment_id": "123",
  "comment_text": "quiero precio",
  "user_name": "Carlos",
  "timestamp": "2026-05-14T12:00:00Z"
}
```

For image/caption:

```json
{
  "image_url": "https://example.com/image.png",
  "caption": "Royal Shield App..."
}
```

Optional security:

Set `MAKE_SECRET` in Railway Variables, then send the same value from Make either as:

```json
{
  "secret": "YOUR_SECRET",
  "image_url": "https://example.com/image.png",
  "caption": "Royal Shield App..."
}
```

or as a header:

```text
x-make-secret: YOUR_SECRET
```
