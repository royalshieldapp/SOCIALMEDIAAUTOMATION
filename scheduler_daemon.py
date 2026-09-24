"""In-process companion scheduler for the Royal Shield automation service.

Runs in the same Railway container and periodically invokes the protected
scheduler endpoint on localhost. It never logs the automation key.
"""

import asyncio
import os
import logging

import httpx

logger = logging.getLogger("socialmediaautomation.scheduler")


def enabled() -> bool:
    return os.getenv("SCHEDULER_ENABLED", "false").strip().lower() in {
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
                    # Wait for the complete cycle, including media processing.
                    # A read timeout would abandon the request while it still publishes.
                    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None), trust_env=False) as client:
                        response = await client.post(
                            f"http://127.0.0.1:{port}/scheduler/run",
                            headers={"x-automation-key": key},
                        )
                        if response.is_error:
                            logger.warning("Scheduler endpoint returned HTTP %s", response.status_code)
                except httpx.RequestError:
                    # Uvicorn may still be starting or restarting. Retry next cycle.
                    logger.warning("Scheduler endpoint unavailable; next cycle will retry queue inspection")
            else:
                logger.warning("Scheduler enabled but AUTOMATION_API_KEY is not configured")
        await asyncio.sleep(poll_seconds())


if __name__ == "__main__":
    asyncio.run(main())
