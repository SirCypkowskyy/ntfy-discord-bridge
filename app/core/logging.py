"""Logging configuration for the ntfy-discord-bridge service."""

import logging

from rich.logging import RichHandler

# Konfigurujemy logger, aby używał RichHandler dla ładnego formatowania
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, tracebacks_suppress=[])],
)

# Pobieramy główny logger
log = logging.getLogger("rich")
