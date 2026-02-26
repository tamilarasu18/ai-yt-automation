"""
FastAPI Presentation Layer — REST API for the pipeline.

Provides HTTP endpoints to trigger the video generation pipeline,
enabling remote/batch triggering and integration with external tools.

Usage:
    ai-shorts serve --port 8000
    POST http://localhost:8000/generate {"topic": "...", "language": "en"}
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def create_app() -> Any:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI application instance.
    """
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as e:
        raise ImportError(
            "FastAPI not installed. Run: pip install fastapi uvicorn"
        ) from e

    app = FastAPI(
        title="AI YouTube Shorts Pipeline",
        description="Automated motivational video generation API",
        version="2.0.0",
    )

    class GenerateRequest(BaseModel):
        """Request body for the /generate endpoint."""
        topic: str
        language: str = "en"
        mode: str = "full"
        scheduled_time: str = ""

    class BatchRequest(BaseModel):
        """Request body for the /batch endpoint."""
        topics: list[dict[str, str]]

    class GenerateResponse(BaseModel):
        """Response body for the /generate endpoint."""
        success: bool
        message: str = ""
        youtube_url: str = ""
        duration_seconds: float = 0.0
        error: str = ""

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy", "service": "ai-shorts"}

    @app.post("/generate", response_model=GenerateResponse)
    async def generate(request: GenerateRequest) -> GenerateResponse:
        """Trigger the video generation pipeline.

        Args:
            request: Topic, language, mode, and optional schedule time.

        Returns:
            Pipeline result with video URL and duration.
        """
        try:
            from ai_shorts.application.pipeline import PipelineOrchestrator
            from ai_shorts.core.config import Settings
            from ai_shorts.core.container import Container
            from ai_shorts.core.logging import setup_logging

            setup_logging()

            settings = Settings()
            container = Container(settings)
            orchestrator = PipelineOrchestrator(container)
            result = orchestrator.run(mode=request.mode)

            if result is None:
                return GenerateResponse(
                    success=True,
                    message="No pending topics. Add topics to your Google Sheet.",
                )

            if result.success:
                youtube_url = ""
                if result.outputs:
                    youtube_url = result.outputs[0].youtube_url

                return GenerateResponse(
                    success=True,
                    message="Pipeline completed successfully",
                    youtube_url=youtube_url,
                    duration_seconds=result.total_duration_seconds,
                )
            else:
                return GenerateResponse(
                    success=False,
                    error=result.error,
                )

        except Exception as e:
            log.error("Pipeline error: %s", e)
            raise HTTPException(
                status_code=500,
                detail=f"Internal Server Error: {e}",
            ) from e

    @app.post("/batch")
    async def batch_generate(request: BatchRequest) -> dict:
        """Process multiple topics in sequence.

        Args:
            request: List of topics with language info.

        Returns:
            Summary of batch results.
        """
        results = []
        for item in request.topics:
            topic = item.get("topic", "")
            if not topic:
                results.append({"topic": topic, "error": "Empty topic"})
                continue

            try:
                req = GenerateRequest(
                    topic=topic,
                    language=item.get("language", "en"),
                    scheduled_time=item.get("scheduled_time", ""),
                )
                result = await generate(req)
                results.append({
                    "topic": topic,
                    "success": result.success,
                    "youtube_url": result.youtube_url,
                })
            except Exception as e:
                results.append({"topic": topic, "error": str(e)})

        return {
            "total": len(results),
            "success": sum(1 for r in results if r.get("success")),
            "results": results,
        }

    return app
