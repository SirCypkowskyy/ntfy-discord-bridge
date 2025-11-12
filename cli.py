#!/usr/bin/env python3
"""CLI for the ntfy-discord-bridge service."""

import argparse
import asyncio
import base64
import sys

from rich.console import Console
from rich.table import Table

from app.core import database
from app.core.logging import log

console = Console()


def build_auth_header(
    basic_creds: tuple[str, str] | None = None,
    token: str | None = None,
) -> str | None:
    """Build the authentication header for Ntfy.

    Args:
        basic_creds: The basic credentials (username, password).
        token: The token.

    Returns:
        The authentication header.

    """
    if basic_creds:
        user, password = basic_creds
        creds_str = f"{user}:{password}"
        encoded_creds = base64.b64encode(creds_str.encode()).decode()
        return f"Basic {encoded_creds}"
    if token:
        return f"Bearer {token}"
    return None


async def cli_add(args: argparse.Namespace) -> None:
    """Handle the 'add' command.

    Args:
        args: The arguments.

    """
    auth_header = build_auth_header(args.basic, args.token)
    success = await database.add_mapping(
        args.server,
        args.topic,
        args.webhook,
        auth_header,
    )
    if not success:
        sys.exit(1)  # Exit with error code if mapping already exists


async def cli_remove(args: argparse.Namespace) -> None:
    """Handle the 'remove' command.

    Args:
        args: The arguments.

    """
    success = await database.remove_mapping(args.id)
    if not success:
        sys.exit(1)


async def cli_list(args: argparse.Namespace) -> None:
    """Handle the 'list' command.

    Args:
        args: The arguments.

    """
    mappings = await database.list_mappings()

    if not mappings:
        console.print("No active mappings.", style="yellow")
        return

    table = Table(title="Active Ntfy -> Discord Mappings")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Ntfy Server")
    table.add_column("Ntfy Topic")
    table.add_column("Discord Webhook")
    table.add_column("Auth", style="dim")

    for m in mappings:
        # Hide credentials in logs
        auth_display = "None"
        if m["ntfy_auth_header"]:
            if m["ntfy_auth_header"].startswith("Basic"):
                auth_display = "Basic (User/Pass)"
            elif m["ntfy_auth_header"].startswith("Bearer"):
                auth_display = "Bearer Token"

        table.add_row(
            str(m["id"]),
            m["ntfy_server"],
            m["ntfy_topic"],
            m["discord_webhook"][:30] + "...",  # Shorten webhook for readability
            auth_display,
        )

    console.print(table)


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="CLI for managing the Ntfy-Discord bridge",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Available commands",
    )

    # Polecenie 'add'
    parser_add = subparsers.add_parser("add", help="Add a new mapping")
    parser_add.add_argument(
        "--server",
        required=True,
        help="Ntfy server URL (e.g. https://ntfy.sh)",
    )
    parser_add.add_argument("--topic", required=True, help="Nazwa tematu Ntfy")
    parser_add.add_argument(
        "--webhook",
        required=True,
        help="Pełny URL webhooka Discord",
    )

    auth_group = parser_add.add_mutually_exclusive_group()
    auth_group.add_argument(
        "--basic",
        nargs=2,
        metavar=("USER", "PASS"),
        help="Authentication Basic (username/password)",
    )
    auth_group.add_argument(
        "--token",
        metavar="TOKEN",
        help="Authentication Bearer Token",
    )
    parser_add.set_defaults(func=cli_add)

    # Polecenie 'remove'
    parser_remove = subparsers.add_parser("remove", help="Remove a mapping")
    parser_remove.add_argument(
        "--id",
        required=True,
        type=int,
        help="ID of the mapping to remove (use 'list' to see IDs)",
    )
    parser_remove.set_defaults(func=cli_remove)

    # Polecenie 'list'
    parser_list = subparsers.add_parser(
        "list",
        help="List all active mappings",
    )
    parser_list.set_defaults(func=cli_list)

    args = parser.parse_args()

    # Use asyncio.run() to call the asynchronous CLI function
    try:
        asyncio.run(args.func(args))
    except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        log.error(f"CLI error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
