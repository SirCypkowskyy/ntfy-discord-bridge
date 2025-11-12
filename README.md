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

### 2. Run with Docker Compose

```bash
docker compose up -d
```

### 3. Add a mapping using CLI

Once the container is running, use the CLI to manage mappings:

```bash
docker exec -it ntfy-discord-bridge cli add \
    --server https://ntfy.sh \
    --topic your-ntfy-topic \
    --webhook <YOUR_DISCORD_WEBHOOK_URL>
```

The container will automatically detect new mappings and start forwarding notifications.

## CLI Usage

The CLI tool (`cli`) is available inside the Docker container and can be used to manage your ntfy-to-Discord mappings.

### List all mappings

View all active mappings:

```bash
docker exec -it ntfy-discord-bridge cli list
```

This will display a table with:
- **ID**: Unique identifier for each mapping
- **Ntfy Server**: The ntfy server URL
- **Ntfy Topic**: The topic name
- **Discord Webhook**: The Discord webhook URL (truncated for security)
- **Auth**: Authentication method used (None, Basic, or Bearer Token)

### Add a new mapping

#### Basic mapping (no authentication)

```bash
docker exec -it ntfy-discord-bridge cli add \
    --server https://ntfy.sh \
    --topic my-topic \
    --webhook https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

#### With Basic authentication

```bash
docker exec -it ntfy-discord-bridge cli add \
    --server https://ntfy.sh \
    --topic my-secure-topic \
    --webhook https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
    --basic username password
```

#### With Bearer token authentication

```bash
docker exec -it ntfy-discord-bridge cli add \
    --server https://ntfy.sh \
    --topic my-secure-topic \
    --webhook https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN \
    --token YOUR_BEARER_TOKEN
```

### Remove a mapping

Remove a mapping by its ID (use `cli list` to find the ID):

```bash
docker exec -it ntfy-discord-bridge cli remove --id 1
```

### Local CLI usage (without Docker)

If you're running the service locally, you can use the CLI directly:

```bash
# Make sure dependencies are installed
uv sync

# Use the CLI
python cli.py list
python cli.py add --server https://ntfy.sh --topic test --webhook <WEBHOOK_URL>
python cli.py remove --id 1
```

Or if the file is executable:

```bash
./cli.py list
./cli.py add --server https://ntfy.sh --topic test --webhook <WEBHOOK_URL>
./cli.py remove --id 1
```

---

See the [CLI documentation](cli.py) and [main.py](main.py) for advanced usage and configuration details.