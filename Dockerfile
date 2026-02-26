# ═══════════════════════════════════════════════════════════
# AI YouTube Shorts — Multi-Stage Docker Build
# ═══════════════════════════════════════════════════════════

# ── Stage 1: Base ──
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

# ── Stage 2: Dependencies ──
FROM base AS deps

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# ── Stage 3: Runtime ──
FROM deps AS runtime

COPY src/ ./src/
COPY README.md ./

RUN pip install --no-cache-dir -e .

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from ai_shorts.core.config import Settings; print('healthy')" || exit 1

ENTRYPOINT ["ai-shorts"]
CMD ["run"]
