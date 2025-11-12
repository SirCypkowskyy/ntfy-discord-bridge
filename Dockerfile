FROM python:3.11-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
WORKDIR /app
RUN uv sync --frozen --no-cache

# Make cli.py executable and create a symlink in venv bin for easy access
RUN chmod +x /app/cli.py && \
    ln -sf /app/cli.py /app/.venv/bin/cli

# Ensure virtualenv binaries are available on PATH for runtime commands
ENV PATH="/app/.venv/bin:${PATH}"

# Run the application.
CMD ["sh", "-c", "exec /app/.venv/bin/python main.py"]