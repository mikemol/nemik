# nemik-serve: read-only graph view. Mount the export (<repo>/paths-forward.{json,ledger}) read-only at /export.
ARG BASE=ghcr.io/astral-sh/uv:python3.13-bookworm-slim
FROM ${BASE} AS base
# git: uv fetches mikemol-pathsforward from its pinned git sha at build time
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

# The gate: the image does not build unless the tests pass. BuildKit skips stages nothing depends
# on, so the final stage copies the marker this stage writes.
FROM base AS test
COPY tests ./tests
RUN uv sync --frozen && .venv/bin/pytest -q tests && touch /app/.tested

FROM base
COPY --from=test /app/.tested /app/.tested
USER 1000:1000
EXPOSE 8750
ENV NEMIK_ROOT=/export
ENTRYPOINT ["/app/.venv/bin/nemik-serve", "--bind", "0.0.0.0", "--port", "8750"]
