"""Ntfy integration module."""

import asyncio
import json
from typing import Any

import backoff
import httpx

from app.core.logging import log
from app.discord import post_to_discord

# HTTP status code constants
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500


async def _process_ntfy_stream(
    response: httpx.Response,
    mapping_id: int,
    discord_client: httpx.AsyncClient,
    webhook_url: str,
) -> None:
    """Process lines from Ntfy stream and forward messages to Discord.

    Args:
        response: The HTTP response stream.
        mapping_id: The mapping ID.
        discord_client: The Discord HTTP client.
        webhook_url: The Discord webhook URL.

    """
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
    # Configure headers for optimal streaming connection
    # - User-Agent: Identifies the client (good practice)
    # - Accept: Specifies we want NDJSON (newline-delimited JSON) stream format
    # - Connection: keep-alive: Maintains persistent connection for streaming
    headers = {
        "User-Agent": "ntfy-discord-bridge/0.1.0",
        "Accept": "application/x-ndjson, application/json",
        "Connection": "keep-alive",
    }
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
    # Configure timeout for streaming: no read timeout (None) for long-lived streams,
    # but keep reasonable connect/write timeouts
    stream_timeout = httpx.Timeout(
        connect=10.0,  # 10 seconds to establish connection
        read=None,  # No read timeout for streaming connections
        write=10.0,  # 10 seconds to write data
        pool=5.0,  # 5 seconds to get connection from pool
    )
    async with (
        httpx.AsyncClient() as discord_client,
        httpx.AsyncClient(
            headers=headers,
            timeout=stream_timeout,
        ) as ntfy_client,
    ):
        try:
            async with ntfy_client.stream("GET", ntfy_url) as response:
                # Check for 4xx/5xx errors (e.g., bad authorization)
                response.raise_for_status()
                log.info(
                    "[ID: %(mapping_id)s] Connected to Ntfy stream: %(ntfy_url)s",
                    {"mapping_id": mapping_id, "ntfy_url": ntfy_url},
                )

                await _process_ntfy_stream(
                    response,
                    mapping_id,
                    discord_client,
                    webhook_url,
                )

        except httpx.HTTPStatusError as e:
            is_client_error = (
                HTTP_BAD_REQUEST <= e.response.status_code < HTTP_INTERNAL_SERVER_ERROR
            )
            _handle_http_status_error(
                e,
                mapping_id,
                ntfy_url,
                is_client_error=is_client_error,
            )
            # Stop retrying for client errors
            if is_client_error:
                return  # End task
            # Let backoff handle 5xx errors
            raise
        except httpx.RequestError as e:
            error_msg = str(e) or type(e).__name__
            log.warning(
                ("[ID: %(mapping_id)s] Ntfy connection error: %(error)s. Retrying..."),
                {"mapping_id": mapping_id, "error": error_msg},
            )
            raise  # Pass exception to backoff
        except Exception as e:
            error_msg = str(e) or type(e).__name__
            log.error(
                "[ID: %(mapping_id)s] Unexpected error in listen_to_ntfy: %(error)s",
                {"mapping_id": mapping_id, "error": error_msg},
                exc_info=True,
            )
            # Give a moment before retry
            await asyncio.sleep(5)
            raise  # Retry


def _handle_http_status_error(
    error: httpx.HTTPStatusError,
    mapping_id: int,
    ntfy_url: str,
    *,
    is_client_error: bool,
) -> None:
    """Handle HTTP status errors from Ntfy.

    Args:
        error: The HTTP status error.
        mapping_id: The mapping ID.
        ntfy_url: The Ntfy URL.
        is_client_error: Whether this is a client error (4xx).

    """
    log.error(
        (
            "[ID: %(mapping_id)s] HTTP status error: %(status_code)s "
            "for %(ntfy_url)s. Check credentials/topic."
        ),
        {
            "mapping_id": mapping_id,
            "status_code": error.response.status_code,
            "ntfy_url": ntfy_url,
        },
    )
    # Stop retrying for client errors
    if is_client_error:
        log.error(
            (
                "[ID: %(mapping_id)s] Stopping retries "
                "due to client error %(status_code)s."
            ),
            {
                "mapping_id": mapping_id,
                "status_code": error.response.status_code,
            },
        )
