# syntax=docker/dockerfile:1.7
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
COPY skills ./skills
# nemik:W122: test_architecture gates ARCHITECTURE.md against the source, so the image gate carries
# the paper and its checks, and the docs extra (paperkit) that runs them. -rs names every skip.
COPY ARCHITECTURE.md paper.toml warrants.bib rubric.tsv ./
COPY checks ./checks
# paperkit is a pinned git source (nemik:W102), and uv needs a git binary to fetch it. The test stage
# only: the final image never carries git.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
# nemik:W123: test_witnesses evaluates Rego, so the gate carries the same pinned opa Bazel uses
# (MODULE.bazel @opa: v1.20.2, checked by sha256), test stage only; NEMIK_OPA names it.
ADD --checksum=sha256:69da5179ee403d10fa11bab6cfb4ffb0d23dba5f9b682fa977db772a1da5670f --chmod=755 \
    https://github.com/open-policy-agent/opa/releases/download/v1.20.2/opa_linux_amd64_static /usr/local/bin/opa
ENV NEMIK_OPA=/usr/local/bin/opa
RUN uv sync --frozen --extra docs && .venv/bin/pytest -q -rs tests && touch /app/.tested

FROM base
COPY --from=test /app/.tested /app/.tested
USER 1000:1000
EXPOSE 8750
ENV NEMIK_ROOT=/export
ENTRYPOINT ["/app/.venv/bin/nemik-serve", "--bind", "0.0.0.0", "--port", "8750"]
