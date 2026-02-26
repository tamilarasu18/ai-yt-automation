"""
Data Transfer Objects — clean boundaries between layers.

DTOs decouple the application layer from infrastructure details.
They carry data across layer boundaries without exposing internal
implementation details of any layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_shorts.domain.value_objects import Language


@dataclass(frozen=True)
class GenerateStoryRequest:
    """Request to generate a story."""

    topic: str
    language: Language


@dataclass(frozen=True)
class GenerateStoryResponse:
    """Response from story generation."""

    text: str
    word_count: int
    language: Language


@dataclass(frozen=True)
class GenerateVoiceRequest:
    """Request to generate voice audio."""

    text: str
    language: Language
    output_path: Path


@dataclass(frozen=True)
class GenerateVoiceResponse:
    """Response from voice generation."""

    audio_path: Path
    duration_seconds: float
    voice_id: str


@dataclass(frozen=True)
class CreateVideoRequest:
    """Request to create a talking-head video."""

    audio_path: Path
    avatar_image_path: Path
    output_path: Path


@dataclass(frozen=True)
class ComposeVideoRequest:
    """Request to compose the final video."""

    avatar_video_path: Path
    background_path: Path
    subtitle_path: Path | None
    audio_path: Path
    output_path: Path
    duration: float


@dataclass(frozen=True)
class PublishVideoRequest:
    """Request to publish a video."""

    video_path: Path
    title: str
    description: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for a pipeline run."""

    mode: str = "full"  # "full" or "test"
    languages: list[Language] = field(default_factory=lambda: [Language.ENGLISH])
