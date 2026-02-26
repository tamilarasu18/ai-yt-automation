"""
Use Cases — application-level business operations.

Each use case represents a single, well-defined operation in the pipeline.
Use cases depend only on domain ports (interfaces), never on concrete
infrastructure implementations.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ai_shorts.domain.entities import Story, VideoAsset, VideoMetadata, Voice
from ai_shorts.domain.exceptions import (
    AvatarAnimationError,
    BackgroundGenerationError,
    StoryGenerationError,
    SubtitleError,
    UploadError,
    VoiceGenerationError,
)
from ai_shorts.domain.ports import (
    AvatarAnimator,
    BackgroundGenerator,
    MetadataGenerator,
    NotificationService,
    StorageService,
    StoryGenerator,
    SubtitleGenerator,
    VideoUploader,
    VoiceGenerator,
)
from ai_shorts.domain.value_objects import Language

log = logging.getLogger(__name__)


class GenerateStoryUseCase:
    """Generate a motivational story script from a topic.

    Flow: Topic → LLM → Story (validated)
    """

    def __init__(self, story_generator: StoryGenerator) -> None:
        self._generator = story_generator

    def execute(self, topic: str, language: Language) -> Story:
        """Generate and validate a story.

        Args:
            topic: The video topic/theme.
            language: Target language.

        Returns:
            Validated Story entity.

        Raises:
            StoryGenerationError: If generation fails or story is invalid.
        """
        try:
            log.info("📝 Generating story for '%s' (%s)...", topic, language.display_name)
            story = self._generator.generate(topic, language)
            story.validate()
            log.info(
                "✅ Story generated (%d words, %s)",
                story.word_count,
                language.display_name,
            )
            return story
        except ValueError as e:
            raise StoryGenerationError(str(e), cause=e) from e
        except Exception as e:
            raise StoryGenerationError(f"Failed to generate story: {e}", cause=e) from e


class GenerateMetadataUseCase:
    """Generate SEO-optimized video metadata.

    Flow: Topic + Story → LLM → VideoMetadata
    """

    def __init__(self, metadata_generator: MetadataGenerator) -> None:
        self._generator = metadata_generator

    def execute(self, topic: str, language: Language, story: str) -> VideoMetadata:
        """Generate title, description, and tags.

        Args:
            topic: The video topic.
            language: Content language.
            story: The story script text.

        Returns:
            VideoMetadata entity.
        """
        log.info("🏷️  Generating SEO metadata...")
        return self._generator.generate(topic, language, story)


class GenerateVoiceUseCase:
    """Generate speech audio from text.

    Flow: Story text → TTS → Voice audio
    """

    def __init__(self, voice_generator: VoiceGenerator) -> None:
        self._generator = voice_generator

    def execute(self, text: str, language: Language, output_path: Path) -> Voice:
        """Synthesize speech from text.

        Args:
            text: Text to speak.
            language: Voice language.
            output_path: Where to save the audio.

        Returns:
            Voice entity with audio metadata.

        Raises:
            VoiceGenerationError: If synthesis fails.
        """
        try:
            log.info("🔊 Generating voice audio (%s)...", language.display_name)
            voice = self._generator.synthesize(text, language, output_path)
            log.info("✅ Voice generated: %.1fs", voice.duration_seconds)
            return voice
        except Exception as e:
            raise VoiceGenerationError(f"Voice synthesis failed: {e}", cause=e) from e


class CreateAvatarVideoUseCase:
    """Generate a talking-head avatar video.

    Flow: Audio + Face image → SadTalker → Avatar video
    """

    def __init__(self, animator: AvatarAnimator) -> None:
        self._animator = animator

    def execute(self, audio_path: Path, image_path: Path, output_path: Path) -> VideoAsset:
        """Create a talking-head video.

        Args:
            audio_path: Path to driving audio.
            image_path: Path to face image.
            output_path: Where to save the video.

        Returns:
            VideoAsset for the avatar video.

        Raises:
            AvatarAnimationError: If animation fails.
        """
        try:
            log.info("🗣️  Generating talking avatar...")
            result = self._animator.animate(audio_path, image_path, output_path)
            log.info("✅ Avatar video generated: %s", result.path)
            return result
        except Exception as e:
            raise AvatarAnimationError(f"Avatar animation failed: {e}", cause=e) from e


class GenerateSubtitlesUseCase:
    """Generate subtitles from audio using speech recognition.

    Flow: Audio → Whisper → SRT subtitles
    """

    def __init__(self, subtitle_generator: SubtitleGenerator) -> None:
        self._generator = subtitle_generator

    def execute(self, audio_path: Path, language: Language, output_path: Path) -> VideoAsset:
        """Transcribe audio to subtitles.

        Args:
            audio_path: Path to audio file.
            language: Language hint.
            output_path: Where to save the .srt file.

        Returns:
            VideoAsset for the subtitle file.

        Raises:
            SubtitleError: If transcription fails.
        """
        try:
            log.info("📝 Generating subtitles (%s)...", language.display_name)
            result = self._generator.transcribe(audio_path, language, output_path)
            log.info("✅ Subtitles generated: %s", result.path)
            return result
        except Exception as e:
            raise SubtitleError(f"Subtitle generation failed: {e}", cause=e) from e


class GenerateBackgroundUseCase:
    """Generate a cinematic background image.

    Flow: Topic → SDXL → Background image
    """

    def __init__(self, background_generator: BackgroundGenerator) -> None:
        self._generator = background_generator

    def execute(self, topic: str, language: Language, output_path: Path) -> VideoAsset:
        """Generate a thematic background image.

        Args:
            topic: Theme for the background.
            language: Content language.
            output_path: Where to save the image.

        Returns:
            VideoAsset for the background image.

        Raises:
            BackgroundGenerationError: If generation fails.
        """
        try:
            log.info("🖼️  Generating background image...")
            result = self._generator.generate(topic, language, output_path)
            log.info("✅ Background generated: %s", result.path)
            return result
        except Exception as e:
            raise BackgroundGenerationError(f"Background generation failed: {e}", cause=e) from e


class PublishVideoUseCase:
    """Publish a video: upload, store, notify.

    Flow: Video → YouTube + Drive + Telegram
    """

    def __init__(
        self,
        uploader: VideoUploader | None = None,
        storage: StorageService | None = None,
        notifier: NotificationService | None = None,
    ) -> None:
        self._uploader = uploader
        self._storage = storage
        self._notifier = notifier

    def execute(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        *,
        upload: bool = True,
    ) -> tuple[str, str]:
        """Publish the video to all channels.

        Args:
            video_path: Path to the final video.
            title: Video title.
            description: Video description.
            tags: SEO tags.
            upload: Whether to upload to YouTube.

        Returns:
            Tuple of (youtube_url, drive_path).

        Raises:
            UploadError: If YouTube upload fails.
        """
        youtube_url = ""
        drive_path = ""

        # Save to persistent storage
        if self._storage:
            try:
                drive_path = self._storage.save(video_path)
                log.info("💾 Saved to Drive: %s", drive_path)
            except Exception as e:
                log.warning("⚠️  Drive save failed: %s", e)

        # Upload to YouTube
        if upload and self._uploader:
            try:
                youtube_url = self._uploader.upload(video_path, title, description, tags)
                log.info("📺 Uploaded to YouTube: %s", youtube_url)
            except Exception as e:
                raise UploadError(f"YouTube upload failed: {e}", cause=e) from e

        # Send notification
        if self._notifier:
            try:
                msg = (
                    f"✅ New video published!\n"
                    f"📋 {title}\n"
                    f"📺 {youtube_url or 'Upload skipped'}\n"
                    f"💾 {drive_path or 'N/A'}"
                )
                self._notifier.send(msg)
            except Exception as e:
                log.warning("⚠️  Notification failed (non-fatal): %s", e)

        return youtube_url, drive_path
