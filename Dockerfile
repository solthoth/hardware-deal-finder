FROM ghcr.io/astral-sh/uv:0.11.33 AS uv

FROM python:3.12-slim-trixie AS runtime

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PATH="/app/.venv/bin:$PATH" \
    DEALFINDER_STATE_PATH=/state/dealfinder.db

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
COPY config ./config
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable && \
    mkdir -p /state && \
    chown 65532:65532 /state

USER 65532:65532

ENTRYPOINT ["dealfinder"]
CMD ["search", "--format", "json", "--state", "/state/dealfinder.db"]

