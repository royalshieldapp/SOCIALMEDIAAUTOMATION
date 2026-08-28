"""In-process companion scheduler for the Royal Shield automation service.

Runs in the same Railway container and periodically invokes the protected
scheduler endpoint on localhost. It never logs the automation key.
"""

import asyncio
import os

import httpx


def enabled() -> bool:
    return os.getenv("SCHEDULER_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def poll_seconds() -> int:
    try:
        return max(int(os.getenv("SCHEDULER_POLL_SECONDS", "30")), 5)
    except ValueError:
        return 30


async def main() -> None:
    while True:
        if enabled():
            key = (os.getenv("AUTOMATION_API_KEY") or "").strip()
            port = (os.getenv("PORT") or "8000").strip()
            if key:
                try:
                    async with httpx.AsyncClient(timeout=20.0) as client:
                        await client.post(
                            f"http://127.0.0.1:{port}/scheduler/run",
                            headers={"x-automation-key": key},
                        )
                except httpx.RequestError:
                    # Uvicorn may still be starting or restarting. Retry next cycle.
                    pass
        await asyncio.sleep(poll_seconds())


if __name__ == "__main__":
    asyncio.run(main())
