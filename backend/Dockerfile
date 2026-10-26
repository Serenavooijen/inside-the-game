# Inside the Game backend: one container for Azure Container Apps.
# Run it with exactly 1 replica (min = max = 1): match state lives in memory.
#
# Build from the repo root (the image needs script/ and generator/ too):
#   docker build -f backend/Dockerfile -t itg-backend .
# Or in Azure, without Docker on your laptop:
#   az acr build -r <registry> -t itg-backend:<tag> -f backend/Dockerfile .

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.1

FROM ${UV_IMAGE} AS uv

# ---------------------------------------------------------------- 1. the match
# Generated from its seed at build time, so the image never depends on output/ in git (deterministic, ~10 s).
FROM ${PYTHON_IMAGE} AS match
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --only-group dev --no-install-project
COPY script/ /app/script/
COPY generator/generate_match.py /app/generator/
RUN .venv/bin/python /app/generator/generate_match.py

# ---------------------------------------------------------------- 2. the app
FROM ${PYTHON_IMAGE}
COPY --from=uv /uv /bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app/ ./app/
COPY script/match_script.json /app/script/
COPY fixtures/scouting/ /app/fixtures/scouting/
COPY --from=match /app/output/events.json /app/output/tracking.csv /app/output/

RUN useradd --no-create-home --shell /usr/sbin/nologin itg
USER itg
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
# One worker: the simulator, the event bus and the SSE connections share one process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
