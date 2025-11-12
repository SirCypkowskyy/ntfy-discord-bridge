"""Main module for the ntfy-discord-bridge service."""

import asyncio
import json
from typing import Any

import backoff
import httpx
import uvloop

from app.core import database
from app.core.logging import log

# Dictionary storing active listening tasks (mapping ID -> asyncio task)
running_tasks: dict[int, asyncio.Task] = {}

# HTTP status code constants
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500


async def post_to_discord(
    session: httpx.AsyncClient,
    webhook_url: str,
    ntfy_message: dict[str, Any],
) -> None:
    """Send a formatted Ntfy message to a Discord webhook.

    Args:
        session: The HTTP client session.
        webhook_url: The Discord webhook URL.
        ntfy_message: The Ntfy message dictionary.

    Raises:
        httpx.RequestError: If the request error occurs.

    """
    title = ntfy_message.get("title", "New Ntfy message")
    message = ntfy_message.get("message", "*No content*")

    # Create a nice payload for Discord
    payload = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": 5814783,  # Blue color
                "footer": {
                    "text": f"Ntfy topic: {ntfy_message.get('topic')}",
                },
            },
        ],
    }

    try:
        response = await session.post(webhook_url, json=payload)
        response.raise_for_status()
        log.info(
            "Successfully sent message to Discord (topic: %(topic)s)",
            {"topic": ntfy_message.get("topic")},
        )
    except httpx.HTTPStatusError as e:
        log.error(
            "Error sending to Discord (%(status_code)s): %(text)s",
            {"status_code": e.response.status_code, "text": e.response.text},
        )
    except httpx.RequestError as e:
        log.error("Connection error sending to Discord: %(error)r", {"error": e})
        raise


@backoff.on_exception(
    backoff.expo,
    (httpx.RequestError, httpx.ConnectError),
    max_time=300,
)
async def listen_to_ntfy(mapping: dict[str, Any]) -> None:
    """Main function listening to Ntfy and forwarding messages to Discord.

    Uses backoff to automatically retry connections.

    Args:
        mapping: The mapping dictionary from the database.

    Raises:
        httpx.HTTPStatusError: If the HTTP status code is not 200.
        httpx.RequestError: If the request error occurs.

    """
    mapping_id = mapping["id"]
    server = mapping["ntfy_server"]
    topic = mapping["ntfy_topic"]
    webhook_url = mapping["discord_webhook"]
    auth_header = mapping.get("ntfy_auth_header")

    ntfy_url = f"{server.rstrip('/')}/{topic.lstrip('/')}/json"
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header

    log.info(
        (
            "[ID: %(mapping_id)s] Starting listening to Ntfy: "
            "%(ntfy_url)s with auth: %(auth_header)r"
        ),
        {"mapping_id": mapping_id, "ntfy_url": ntfy_url, "auth_header": auth_header},
    )

    # Use a separate Discord session to not block Ntfy connections
    async with (  # noqa: PLR1702
        httpx.AsyncClient() as discord_client,
        httpx.AsyncClient(headers=headers, timeout=30.0) as ntfy_client,
    ):
        try:
            async with ntfy_client.stream("GET", ntfy_url) as response:
                # Check for 4xx/5xx errors (e.g., bad authorization)
                response.raise_for_status()
                log.info(
                    "[ID: %(mapping_id)s] Connected to Ntfy stream: %(ntfy_url)s",
                    {"mapping_id": mapping_id, "ntfy_url": ntfy_url},
                )

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        if data.get("event") == "message":
                            log.info(
                                ("[ID: %(mapping_id)s] Received message: %(title)s"),
                                {
                                    "mapping_id": mapping_id,
                                    "title": data.get("title"),
                                },
                            )
                            await post_to_discord(discord_client, webhook_url, data)

                    except json.JSONDecodeError:
                        log.warning(
                            (
                                "[ID: %(mapping_id)s] Received invalid JSON "
                                "from Ntfy stream: %(line)s"
                            ),
                            {"mapping_id": mapping_id, "line": line},
                        )

        except httpx.HTTPStatusError as e:
            # 4xx errors (e.g., 401 Unauthorized, 404 Not Found)
            # usually should not be retried
            log.error(
                (
                    "[ID: %(mapping_id)s] HTTP status error: %(status_code)s "
                    "for %(ntfy_url)s. Check credentials/topic."
                ),
                {
                    "mapping_id": mapping_id,
                    "status_code": e.response.status_code,
                    "ntfy_url": ntfy_url,
                },
            )
            # Stop retrying for client errors
            if HTTP_BAD_REQUEST <= e.response.status_code < HTTP_INTERNAL_SERVER_ERROR:
                log.error(
                    (
                        "[ID: %(mapping_id)s] Stopping retries "
                        "due to client error %(status_code)s."
                    ),
                    {
                        "mapping_id": mapping_id,
                        "status_code": e.response.status_code,
                    },
                )
                return  # End task
            # Let backoff handle 5xx errors
            raise
        except httpx.RequestError as e:
            log.warning(
                ("[ID: %(mapping_id)s] Ntfy connection error: %(error)s. Retrying..."),
                {"mapping_id": mapping_id, "error": e},
            )
            raise  # Pass exception to backoff
        except Exception as e:
            log.error(
                "[ID: %(mapping_id)s] Unexpected error in listen_to_ntfy: %(error)s",
                {"mapping_id": mapping_id, "error": e},
                exc_info=True,
            )
            # Give a moment before retry
            await asyncio.sleep(5)
            raise  # Retry


async def manage_listeners() -> None:
    """Main management loop.

    Checks the database and dynamically starts/stops listening tasks.
    """
    while True:
        try:
            log.info("🔄 Checking for database updates...")
            mappings = await database.list_mappings()

            current_mapping_ids = {m["id"] for m in mappings}
            active_task_ids = set(running_tasks.keys())

            # 1. Start new listeners
            for mapping in mappings:
                mapping_id = mapping["id"]
                if mapping_id not in active_task_ids:
                    log.info(
                        (
                            "Found new mapping [ID: %(mapping_id)s], "
                            "starting listener..."
                        ),
                        {"mapping_id": mapping_id},
                    )
                    task = asyncio.create_task(listen_to_ntfy(mapping))
                    running_tasks[mapping_id] = task

            # 2. Stop deleted listeners
            stale_task_ids = active_task_ids - current_mapping_ids
            for mapping_id in stale_task_ids:
                log.info(
                    (
                        "Mapping [ID: %(mapping_id)s] has been deleted, "
                        "stopping listener..."
                    ),
                    {"mapping_id": mapping_id},
                )
                task = running_tasks.pop(mapping_id)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    log.debug(
                        "Task [ID: %(mapping_id)s] successfully cancelled.",
                        {"mapping_id": mapping_id},
                    )

        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            log.error(
                "Error in management loop: %(error)r",
                {"error": e},
                exc_info=True,
            )

        # Check database every 30 seconds
        await asyncio.sleep(30)


async def main() -> None:
    """Main function."""
    log.info("🚀 Starting Ntfy-Discord Bridge...")
    await database.init_db()
    await manage_listeners()


if __name__ == "__main__":
    # Use uvloop for higher performance
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(main())
