"""
Dependency Injection Container — wires ports to adapters.

A simple, explicit DI container that resolves domain ports to their
concrete infrastructure adapters based on application settings.

This avoids complex DI frameworks while maintaining clean separation
between layers. All wiring happens in one place.

Usage:
    settings = Settings()
    container = Container(settings)
    story_gen = container.story_generator()
    voice_gen = container.voice_generator()
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings
    from ai_shorts.domain.ports import (
        AvatarAnimator,
        BackgroundGenerator,
        ImagePromptGenerator,
        LLMService,
        MetadataGenerator,
        NotificationService,
        StorageService,
        StoryGenerator,
        SubtitleGenerator,
        TopicRepository,
        VideoComposer,
        VideoUploader,
        VoiceGenerator,
    )

log = logging.getLogger(__name__)


class Container:
    """Dependency injection container.

    Lazily creates and caches adapter instances. Each adapter is created
    only when first requested and reused for subsequent calls.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        log.info("🔌 DI Container initialized")

    @lru_cache(maxsize=1)
    def topic_repository(self) -> TopicRepository:
        """Resolve TopicRepository → GoogleSheetsTopicRepository."""
        from ai_shorts.infrastructure.adapters.google_sheets import (
            GoogleSheetsTopicRepository,
        )

        return GoogleSheetsTopicRepository(self._settings)

    @lru_cache(maxsize=1)
    def llm_service(self) -> LLMService:
        """Resolve LLMService → OllamaLLMService."""
        from ai_shorts.infrastructure.adapters.ollama import OllamaLLMService

        return OllamaLLMService(self._settings)

    @lru_cache(maxsize=1)
    def story_generator(self) -> StoryGenerator:
        """Resolve StoryGenerator → OllamaStoryGenerator."""
        from ai_shorts.infrastructure.adapters.ollama import OllamaStoryGenerator

        return OllamaStoryGenerator(self._settings, self.llm_service())

    @lru_cache(maxsize=1)
    def metadata_generator(self) -> MetadataGenerator:
        """Resolve MetadataGenerator → OllamaMetadataGenerator."""
        from ai_shorts.infrastructure.adapters.ollama import OllamaMetadataGenerator

        return OllamaMetadataGenerator(self._settings, self.llm_service())

    @lru_cache(maxsize=1)
    def voice_generator(self) -> VoiceGenerator:
        """Resolve VoiceGenerator → EdgeTTS or Kokoro based on config."""
        engine = self._settings.tts_engine

        if engine == "kokoro":
            from ai_shorts.infrastructure.adapters.kokoro_tts import (
                KokoroVoiceGenerator,
            )

            log.info("🔊 TTS engine: Kokoro (local)")
            return KokoroVoiceGenerator(self._settings)

        from ai_shorts.infrastructure.adapters.edge_tts import EdgeTTSVoiceGenerator

        log.info("🔊 TTS engine: Edge TTS (cloud)")
        return EdgeTTSVoiceGenerator(self._settings)

    @lru_cache(maxsize=1)
    def avatar_animator(self) -> AvatarAnimator:
        """Resolve AvatarAnimator → SadTalkerAnimator."""
        from ai_shorts.infrastructure.adapters.sadtalker import SadTalkerAnimator

        return SadTalkerAnimator(self._settings)

    @lru_cache(maxsize=1)
    def subtitle_generator(self) -> SubtitleGenerator:
        """Resolve SubtitleGenerator → WhisperSubtitleGenerator."""
        from ai_shorts.infrastructure.adapters.whisper import WhisperSubtitleGenerator

        return WhisperSubtitleGenerator(self._settings)

    @lru_cache(maxsize=1)
    def background_generator(self) -> BackgroundGenerator:
        """Resolve BackgroundGenerator → SDXL or FLUX based on config."""
        engine = self._settings.image_engine

        if engine == "flux":
            from ai_shorts.infrastructure.adapters.flux_image import (
                StableDiffusionBackgroundGenerator,
            )

            log.info("🖼️  Image engine: Stable Diffusion (local GPU)")
            return StableDiffusionBackgroundGenerator(self._settings)

        from ai_shorts.infrastructure.adapters.sdxl import SDXLBackgroundGenerator

        log.info("🖼️  Image engine: SDXL (local GPU)")
        return SDXLBackgroundGenerator(self._settings)

    @lru_cache(maxsize=1)
    def image_prompt_generator(self) -> ImagePromptGenerator:
        """Resolve ImagePromptGenerator → OllamaImagePromptGenerator."""
        from ai_shorts.infrastructure.adapters.ollama import (
            OllamaImagePromptGenerator,
        )

        return OllamaImagePromptGenerator(self._settings, self.llm_service())

    @lru_cache(maxsize=1)
    def video_composer(self) -> VideoComposer:
        """Resolve VideoComposer → MoviePyVideoComposer."""
        from ai_shorts.infrastructure.adapters.moviepy_composer import (
            MoviePyVideoComposer,
        )

        return MoviePyVideoComposer(self._settings)

    @lru_cache(maxsize=1)
    def video_uploader(self) -> VideoUploader:
        """Resolve VideoUploader → YouTubeUploader."""
        from ai_shorts.infrastructure.adapters.youtube import YouTubeUploader

        return YouTubeUploader(self._settings)

    @lru_cache(maxsize=1)
    def storage_service(self) -> StorageService:
        """Resolve StorageService → GoogleDriveStorage."""
        from ai_shorts.infrastructure.adapters.google_drive import GoogleDriveStorage

        return GoogleDriveStorage(self._settings)

    @lru_cache(maxsize=1)
    def notification_service(self) -> NotificationService:
        """Resolve NotificationService → TelegramNotifier."""
        from ai_shorts.infrastructure.adapters.telegram import TelegramNotifier

        return TelegramNotifier(self._settings)
