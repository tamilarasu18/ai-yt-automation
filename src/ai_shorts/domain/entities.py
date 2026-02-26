"""
Domain Entities — core business objects with identity.

Entities are distinguished by their identity rather than their attributes.
They represent the fundamental concepts of the AI Shorts pipeline domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_shorts.domain.value_objects import AssetType, Language, TopicStatus, VideoMode


@dataclass
class Topic:
    """A video topic fetched from the content queue.

    Attributes:
        text: The topic/prompt text.
        language: Target language for content generation.
        status: Current processing status.
        row_index: Row number in the source spreadsheet (1-indexed).
        worksheet_ref: Opaque reference to the source worksheet (for updates).
    """

    text: str
    language: Language
    status: TopicStatus = TopicStatus.PENDING
    row_index: int | None = None
    worksheet_ref: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Topic text cannot be empty")

    def mark_processing(self) -> None:
        """Transition to processing state."""
        self.status = TopicStatus.PROCESSING

    def mark_done(self) -> None:
        """Transition to completed state."""
        self.status = TopicStatus.DONE

    def mark_failed(self) -> None:
        """Transition to failed state."""
        self.status = TopicStatus.FAILED


@dataclass
class Story:
    """A generated story/script for a video.

    Attributes:
        text: The story content (spoken script only).
        language: Language the story is written in.
        word_count: Number of words in the story.
        generated_at: Timestamp of generation.
    """

    text: str
    language: Language
    word_count: int = 0
    generated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.word_count:
            self.word_count = len(self.text.split())

    def validate(self, min_words: int = 30, max_words: int = 200) -> None:
        """Validate story meets length requirements.

        Raises:
            ValueError: If story doesn't meet length requirements.
        """
        if self.word_count < min_words:
            raise ValueError(
                f"Story too short ({self.word_count} words, minimum {min_words}). "
                "Generation may have failed."
            )
        if self.word_count > max_words:
            raise ValueError(
                f"Story too long ({self.word_count} words, maximum {max_words}). "
                "Video will exceed YouTube Shorts limit."
            )


@dataclass
class Voice:
    """A generated voice audio file.

    Attributes:
        audio_path: Path to the generated WAV/MP3 file.
        duration_seconds: Audio duration in seconds.
        language: Language of the spoken content.
        voice_id: Identifier of the TTS voice used.
    """

    audio_path: Path
    duration_seconds: float
    language: Language
    voice_id: str = ""

    def __post_init__(self) -> None:
        self.audio_path = Path(self.audio_path)


@dataclass
class VideoAsset:
    """A media asset used in video composition.

    Attributes:
        path: File system path to the asset.
        asset_type: Category of the asset.
        duration_seconds: Duration for video/audio assets.
        width: Width in pixels (for image/video assets).
        height: Height in pixels (for image/video assets).
    """

    path: Path
    asset_type: AssetType
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    @property
    def exists(self) -> bool:
        """Check if the asset file exists on disk."""
        return self.path.exists()


@dataclass
class VideoMetadata:
    """SEO-optimized metadata for a published video.

    Attributes:
        title: YouTube video title.
        description: YouTube video description.
        tags: List of SEO tags.
        language: Content language.
    """

    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    language: Language = Language.ENGLISH


@dataclass
class SceneSegment:
    """A time-aligned scene segment for multi-image composition.

    Attributes:
        start: Segment start time in seconds.
        end: Segment end time in seconds.
        image_number: 1-indexed image number.
        prompt: LLM-generated image prompt for this segment.
    """

    start: float
    end: float
    image_number: int
    prompt: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class VideoOutput:
    """Final output of the video pipeline.

    Attributes:
        local_path: Path to the final composed video.
        drive_path: Path to the Google Drive backup.
        youtube_url: URL of the uploaded YouTube video.
        metadata: SEO metadata used for publishing.
        duration_seconds: Final video duration.
        scheduled_time: ISO 8601 datetime for scheduled publish.
        video_mode: Composition mode used (avatar or slideshow).
    """

    local_path: Path
    drive_path: str = ""
    youtube_url: str = ""
    metadata: VideoMetadata | None = None
    duration_seconds: float = 0.0
    scheduled_time: str = ""
    video_mode: VideoMode = VideoMode.AVATAR


@dataclass
class PipelineResult:
    """Aggregated result of a complete pipeline execution.

    Attributes:
        topic: The original topic.
        story: The generated story.
        voice: The generated voice audio.
        outputs: List of video outputs (one per language).
        total_duration_seconds: Total pipeline execution time.
        success: Whether the pipeline completed successfully.
        error: Error message if pipeline failed.
    """

    topic: Topic
    story: Story | None = None
    voice: Voice | None = None
    outputs: list[VideoOutput] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    success: bool = False
    error: str = ""
