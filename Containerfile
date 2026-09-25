# nemik-serve: read-only graph view. Mount the export (<repo>/paths-forward.{json,ledger}) read-only at /export.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
# git: uv fetches mikemol-pathsforward from its pinned git sha at build time
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev
USER 1000:1000
EXPOSE 8750
ENV NEMIK_ROOT=/export
ENTRYPOINT ["/app/.venv/bin/nemik-serve", "--bind", "0.0.0.0", "--port", "8750"]
