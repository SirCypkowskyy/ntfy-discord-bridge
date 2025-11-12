"""Discord webhook integration module."""

from typing import Any

import httpx

from app.core.logging import log


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
