"""
Domain Exceptions — typed error hierarchy for the pipeline.

Each pipeline stage has its own exception type, enabling precise error
handling and recovery strategies at the orchestration layer.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    def __init__(self, message: str, stage: str = "", cause: Exception | None = None):
        self.stage = stage
        self.cause = cause
        super().__init__(message)


class ConfigurationError(PipelineError):
    """Raised when configuration is missing or invalid."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="configuration", cause=cause)


class TopicFetchError(PipelineError):
    """Raised when fetching topics from the queue fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="topic_fetch", cause=cause)


class StoryGenerationError(PipelineError):
    """Raised when LLM story generation fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="story_generation", cause=cause)


class VoiceGenerationError(PipelineError):
    """Raised when TTS voice synthesis fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="voice_generation", cause=cause)


class AvatarAnimationError(PipelineError):
    """Raised when talking-head video generation fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="avatar_animation", cause=cause)


class SubtitleError(PipelineError):
    """Raised when subtitle generation fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="subtitle_generation", cause=cause)


class BackgroundGenerationError(PipelineError):
    """Raised when background image generation fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="background_generation", cause=cause)


class VideoCompositionError(PipelineError):
    """Raised when video composition fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="video_composition", cause=cause)


class UploadError(PipelineError):
    """Raised when video upload fails."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="upload", cause=cause)


class NotificationError(PipelineError):
    """Raised when notification delivery fails (non-fatal)."""

    def __init__(self, message: str, cause: Exception | None = None):
        super().__init__(message, stage="notification", cause=cause)
