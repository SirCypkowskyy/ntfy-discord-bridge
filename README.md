# ntfy-discord-bridge

A service that forwards notifications from [ntfy](https://ntfy.sh/) topics to Discord webhooks, deployable via Docker.

## Overview

**ntfy-discord-bridge** connects your [ntfy](https://ntfy.sh/) notifications directly to Discord channels via webhooks. It supports multiple mappings and secure connections, and can be managed easily using its CLI or run in Docker.

## Features

- Listens to one or more ntfy topics and streams messages to Discord webhooks.
- Supports authenticated ntfy servers (Basic and Bearer).
- Dynamic management: add or remove mappings at runtime without restart.
- Robust error handling and automatic reconnection/backoff.
- Simple management CLI (`cli.py`): add/list/remove topic-to-webhook mappings.
- Easy deployment with Docker/Docker Compose.
- Written in Python 3.11+.

## Highlights

- **Docker-ready:** Ships with a Dockerfile and docker-compose configuration for production deployments.
- **CLI management:** Use the CLI tool to add, list, or remove ntfy-to-Discord mappings (see below).
- **Persistent mappings:** All mappings are stored in a persistent volume, so container restarts retain your configuration.

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/SirCypkowskyy/ntfy-discord-bridge.git
cd ntfy-discord-bridge
```

### 2. Add a mapping

```bash
docker run --rm -v $(pwd)/data:/app/data ntfy-discord-bridge \
    python cli.py add \
    --server https://ntfy.sh \
    --topic your-ntfy-topic \
    --webhook <YOUR_DISCORD_WEBHOOK_URL>
```

#### Authenticated servers

Add `--basic username password` or `--token <TOKEN>` as needed.

### 3. Run with Docker Compose

Customize your mappings with the CLI as above, then simply run:

```bash
docker compose up -d
```

The container will watch your mappings and forward notifications as configured.

---

See the [CLI documentation](cli.py) and [main.py](main.py) for advanced usage and configuration details.