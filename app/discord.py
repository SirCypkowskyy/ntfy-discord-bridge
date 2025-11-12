"""Discord webhook integration module."""

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.logging import log

# Discord embed colors (decimal RGB values)
COLOR_INFO = 3447003  # Blue
COLOR_SUCCESS = 3066993  # Green
COLOR_WARNING = 16776960  # Yellow
COLOR_ERROR = 15158332  # Red

# Priority thresholds
PRIORITY_URGENT = 5
PRIORITY_HIGH = 4

# Emoji mappings
EMOJI_INFO = "ℹ️"  # noqa: RUF001
EMOJI_SUCCESS = "✅"
EMOJI_WARNING = "⚠️"
EMOJI_ERROR = "❌"

# Tag sets for notification type detection
ERROR_TAGS = {"error", "skull", "rotating_light", "fire", "boom"}
WARNING_TAGS = {"warning", "exclamation", "construction"}
SUCCESS_TAGS = {
    "white_check_mark",
    "heavy_check_mark",
    "partying_face",
    "tada",
    "check",
}


def _check_tags_for_type(tags_lower: list[str]) -> tuple[int, str] | None:
    """Check if tags indicate a specific notification type.

    Args:
        tags_lower: Lowercase list of tags.

    Returns:
        Tuple of (color, emoji) if tags match a type, None otherwise.

    """
    if any(tag in tags_lower for tag in ERROR_TAGS):
        return (COLOR_ERROR, EMOJI_ERROR)
    if any(tag in tags_lower for tag in WARNING_TAGS):
        return (COLOR_WARNING, EMOJI_WARNING)
    if any(tag in tags_lower for tag in SUCCESS_TAGS):
        return (COLOR_SUCCESS, EMOJI_SUCCESS)
    return None


def _priority_to_type(priority: int | str) -> tuple[int, str]:
    """Convert priority to notification type.

    Args:
        priority: The notification priority.

    Returns:
        Tuple of (color, emoji).

    """
    # Handle string priorities
    if isinstance(priority, str):
        priority_lower = priority.lower()
        priority_map: dict[str, tuple[int, str]] = {
            "urgent": (COLOR_ERROR, EMOJI_ERROR),
            "5": (COLOR_ERROR, EMOJI_ERROR),
            "high": (COLOR_WARNING, EMOJI_WARNING),
            "4": (COLOR_WARNING, EMOJI_WARNING),
        }
        return priority_map.get(priority_lower, (COLOR_INFO, EMOJI_INFO))

    # Handle numeric priorities
    if isinstance(priority, int):
        if priority >= PRIORITY_URGENT:
            return (COLOR_ERROR, EMOJI_ERROR)
        if priority >= PRIORITY_HIGH:
            return (COLOR_WARNING, EMOJI_WARNING)
        return (COLOR_INFO, EMOJI_INFO)

    return (COLOR_INFO, EMOJI_INFO)


def _determine_notification_type(
    priority: int | str | None,
    tags: list[str] | None,
) -> tuple[int, str]:
    """Determine notification type based on priority and tags.

    Args:
        priority: The notification priority (1-5 or string like "urgent", "high").
        tags: List of tags associated with the notification.

    Returns:
        Tuple of (color, emoji) where:
        - color: Discord embed color (decimal RGB)
        - emoji: Emoji string for the notification type

    """
    tags = tags or []
    tags_lower = [tag.lower() for tag in tags]

    # Check tags first (they can override priority)
    tag_result = _check_tags_for_type(tags_lower)
    if tag_result is not None:
        return tag_result

    # Determine by priority if no matching tags
    if priority is None:
        return (COLOR_INFO, EMOJI_INFO)

    return _priority_to_type(priority)


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
    priority = ntfy_message.get("priority")
    tags = ntfy_message.get("tags", [])

    # Determine notification type based on priority and tags
    color, emoji = _determine_notification_type(priority, tags)

    # Add emoji to title if not already present
    if not title.startswith(emoji):
        title = f"{emoji} {title}"

    # Get timestamp from ntfy message or use current time
    # Ntfy provides 'time' as Unix timestamp in seconds
    timestamp = ntfy_message.get("time")
    if timestamp:
        # Convert Unix timestamp to ISO 8601 format
        dt = datetime.fromtimestamp(timestamp, tz=UTC)
        timestamp_iso = dt.isoformat()
    else:
        # Use current time if not provided
        timestamp_iso = datetime.now(UTC).isoformat()

    # Create a nice payload for Discord
    payload = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": timestamp_iso,
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
