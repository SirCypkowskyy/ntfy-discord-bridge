"""Main module for the ntfy-discord-bridge service."""

import asyncio

import uvloop

from app.core import database
from app.core.logging import log
from app.task_manager import manage_listeners


async def main() -> None:
    """Main function."""
    log.info("🚀 Starting Ntfy-Discord Bridge...")
    await database.init_db()
    await manage_listeners()


if __name__ == "__main__":
    # Use uvloop for higher performance
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(main())
