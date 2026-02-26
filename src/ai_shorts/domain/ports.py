"""
Domain Ports — abstract interfaces for infrastructure dependencies.

Ports define the contracts that the domain layer requires from the outside world.
Infrastructure adapters implement these interfaces, enabling the Dependency
Inversion Principle: the domain depends on abstractions, not concretions.

This is the "Ports" half of the Hexagonal (Ports & Adapters) Architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ai_shorts.domain.entities import (
    SceneSegment,
    Story,
    Topic,
    VideoAsset,
    VideoMetadata,
    Voice,
)
from ai_shorts.domain.value_objects import Language

# ═══════════════════════════════════════════════════════════════
# Content Source Ports
# ═══════════════════════════════════════════════════════════════


class TopicRepository(ABC):
    """Port for fetching and managing video topics from a queue.

    Implementations: GoogleSheetsTopicRepository
    """

    @abstractmethod
    def get_next_pending(self) -> Topic | None:
        """Fetch the next topic with 'Pending' status.

        Returns:
            The next pending Topic, or None if queue is empty.
        """

    @abstractmethod
    def update_status(self, topic: Topic) -> None:
        """Update the status of a topic in the queue.

        Args:
            topic: Topic entity with updated status.
        """


# ═══════════════════════════════════════════════════════════════
# Generation Ports
# ═══════════════════════════════════════════════════════════════


class LLMService(ABC):
    """Port for Large Language Model text generation.

    Implementations: OllamaLLMService
    """

    @abstractmethod
    def generate(self, prompt: str, model: str = "") -> str:
        """Generate text from a prompt.

        Args:
            prompt: Input prompt for the LLM.
            model: Model identifier (adapter-specific).

        Returns:
            Generated text string.
        """


class StoryGenerator(ABC):
    """Port for generating video story scripts.

    Implementations: OllamaStoryGenerator
    """

    @abstractmethod
    def generate(self, topic: str, language: Language) -> Story:
        """Generate a motivational story script.

        Args:
            topic: The topic/theme for the story.
            language: Target language.

        Returns:
            A validated Story entity.
        """


class MetadataGenerator(ABC):
    """Port for generating SEO-optimized video metadata.

    Implementations: OllamaMetadataGenerator
    """

    @abstractmethod
    def generate(self, topic: str, language: Language, story: str) -> VideoMetadata:
        """Generate title, description, and tags for a video.

        Args:
            topic: The video topic.
            language: Content language.
            story: The story script.

        Returns:
            A VideoMetadata entity.
        """


class VoiceGenerator(ABC):
    """Port for text-to-speech voice synthesis.

    Implementations: EdgeTTSVoiceGenerator, KokoroVoiceGenerator
    """

    @abstractmethod
    def synthesize(self, text: str, language: Language, output_path: Path) -> Voice:
        """Synthesize speech from text.

        Args:
            text: Text to convert to speech.
            language: Language for voice selection.
            output_path: Where to save the audio file.

        Returns:
            A Voice entity with audio metadata.
        """


class ImagePromptGenerator(ABC):
    """Port for generating image prompts from story text.

    Uses LLM to summarize a story into a single-line image-generation
    prompt that captures the visual essence of the narrative.

    Implementations: OllamaImagePromptGenerator
    """

    @abstractmethod
    def generate_prompt(self, story_text: str) -> str:
        """Generate a single-line image prompt from a story.

        Args:
            story_text: The full story text.

        Returns:
            A concise image generation prompt.
        """


class SceneImageGenerator(ABC):
    """Port for generating per-segment scene images.

    Generates multiple images (one per time segment) by combining
    SRT-derived scene descriptions with an image generation API.

    Implementations: FluxSceneImageGenerator
    """

    @abstractmethod
    def generate_scenes(
        self,
        segments: list[SceneSegment],
        output_dir: Path,
    ) -> list[VideoAsset]:
        """Generate images for each scene segment.

        Args:
            segments: Time-aligned scene segments with prompts.
            output_dir: Directory to save the images.

        Returns:
            List of VideoAsset entities (one per segment).
        """


# ═══════════════════════════════════════════════════════════════
# Video Production Ports
# ═══════════════════════════════════════════════════════════════


class AvatarAnimator(ABC):
    """Port for generating talking-head avatar videos.

    Implementations: SadTalkerAnimator
    """

    @abstractmethod
    def animate(self, audio_path: Path, image_path: Path, output_path: Path) -> VideoAsset:
        """Generate a talking-head video from audio + still image.

        Args:
            audio_path: Path to the driving audio.
            image_path: Path to the source face image.
            output_path: Where to save the output video.

        Returns:
            A VideoAsset entity for the generated video.
        """


class SubtitleGenerator(ABC):
    """Port for generating subtitles from audio.

    Implementations: WhisperSubtitleGenerator
    """

    @abstractmethod
    def transcribe(self, audio_path: Path, language: Language, output_path: Path) -> VideoAsset:
        """Transcribe audio to SRT subtitle file.

        Args:
            audio_path: Path to the audio file.
            language: Language hint for transcription.
            output_path: Where to save the .srt file.

        Returns:
            A VideoAsset entity for the subtitle file.
        """


class BackgroundGenerator(ABC):
    """Port for generating cinematic background images.

    Implementations: SDXLBackgroundGenerator, FluxBackgroundGenerator
    """

    @abstractmethod
    def generate(self, topic: str, language: Language, output_path: Path) -> VideoAsset:
        """Generate a cinematic background image.

        Args:
            topic: Theme for the background.
            language: Content language (affects cultural style).
            output_path: Where to save the image.

        Returns:
            A VideoAsset entity for the background image.
        """


class VideoComposer(ABC):
    """Port for composing the final video from assets.

    Implementations: MoviePyVideoComposer
    """

    @abstractmethod
    def compose(
        self,
        avatar_video: Path,
        background: Path,
        subtitles: Path | None,
        audio: Path,
        output_path: Path,
        duration: float,
        background_music: Path | None = None,
    ) -> VideoAsset:
        """Compose the final YouTube Short from all assets.

        Args:
            avatar_video: Talking-head video.
            background: Background image.
            subtitles: Optional SRT subtitle file.
            audio: Voice audio file.
            output_path: Where to save the final video.
            duration: Target duration in seconds.
            background_music: Optional background music file.

        Returns:
            A VideoAsset entity for the composed video.
        """


class ShortsComposer(ABC):
    """Port for splitting long videos into YouTube Shorts segments.

    Implementations: MoviePyShortsComposer
    """

    @abstractmethod
    def split(
        self,
        video_path: Path,
        audio_path: Path,
        output_dir: Path,
        max_duration: int = 60,
    ) -> list[VideoAsset]:
        """Split a video into Shorts-length segments.

        Args:
            video_path: Source video (or background image).
            audio_path: Voice audio.
            output_dir: Directory for output segments.
            max_duration: Maximum duration per segment (default 60s).

        Returns:
            List of VideoAsset entities for each segment.
        """


# ═══════════════════════════════════════════════════════════════
# Distribution Ports
# ═══════════════════════════════════════════════════════════════


class VideoUploader(ABC):
    """Port for uploading videos to a platform.

    Implementations: YouTubeUploader
    """

    @abstractmethod
    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        scheduled_time: str = "",
    ) -> str:
        """Upload a video and return the public URL.

        Args:
            video_path: Path to the video file.
            title: Video title.
            description: Video description.
            tags: SEO tags.
            scheduled_time: Optional ISO 8601 datetime for scheduled publish.

        Returns:
            URL of the published video.
        """


class StorageService(ABC):
    """Port for persistent file storage.

    Implementations: GoogleDriveStorage
    """

    @abstractmethod
    def save(self, local_path: Path) -> str:
        """Save a file to persistent storage.

        Args:
            local_path: Path to the local file.

        Returns:
            Path/URL in the storage service.
        """


class NotificationService(ABC):
    """Port for sending notifications.

    Implementations: TelegramNotifier
    """

    @abstractmethod
    def send(self, message: str) -> bool:
        """Send a notification message.

        Args:
            message: The message text.

        Returns:
            True if sent successfully.
        """
