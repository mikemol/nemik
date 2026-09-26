# nemik-serve: read-only graph view. Mount the export (<repo>/paths-forward.{json,ledger}) read-only at /export.
ARG BASE=ghcr.io/astral-sh/uv:python3.13-bookworm-slim
FROM ${BASE} AS base
# nemik:W6/H1: mikemol-pathsforward is a vendored wheel (vendor/wheels), not a build-time git+https
# fetch, so the build has no egress to github.com. No git binary needed: nemik-serve never shells
# out to git (only nemik-check does, for provenance, and it isn't run from inside the image).
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY vendor ./vendor
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
