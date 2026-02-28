"""
Pipeline Orchestrator — sequences use cases into a complete workflow.

The orchestrator is the application-level coordinator that drives
the entire video generation pipeline. It manages:
  - Step sequencing and dependency flow
  - GPU memory lifecycle between stages
  - Error handling and status updates
  - Timing instrumentation

Supports two modes:
  - **full**: Complete pipeline (story → voice → avatar → subtitles → background → compose → publish)
  - **test**: Simplified pipeline (story → voice → avatar only)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from ai_shorts.core.container import Container
from ai_shorts.core.gpu import free_gpu_memory, get_gpu_info
from ai_shorts.core.timer import PipelineTimer
from ai_shorts.domain.entities import PipelineResult, Topic, VideoOutput
from ai_shorts.domain.exceptions import PipelineError
from ai_shorts.domain.value_objects import Language

log = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the full AI YouTube Shorts generation pipeline.

    The orchestrator follows the Template Method pattern, defining the
    overall algorithm while delegating each step to specific use cases.
    """

    def __init__(self, container: Container) -> None:
        self._container = container
        self._settings = container._settings
        self._timer = PipelineTimer()

    def run(self, mode: str = "full") -> PipelineResult | None:
        """Execute the pipeline.

        Args:
            mode: Pipeline mode — "full" or "test".

        Returns:
            PipelineResult with all outputs, or None if no topics.
        """
        log.info("=" * 60)
        log.info("🤖 AI YOUTUBE SHORTS — %s PIPELINE", mode.upper())
        log.info("📅 %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        log.info("=" * 60)

        self._settings.ensure_directories()
        get_gpu_info()

        # Step 1: Fetch topic
        topic = self._fetch_topic()
        if topic is None:
            return None

        result = PipelineResult(topic=topic)

        try:
            # Resolve languages
            languages = (
                [Language.ENGLISH, Language.TAMIL]
                if topic.language == Language.BOTH
                else [topic.language]
            )

            for lang in languages:
                output = self._generate_video(topic.text, lang, mode)
                result.outputs.append(output)

            # Mark success
            topic.mark_done()
            self._update_topic_status(topic)
            result.success = True

        except PipelineError as e:
            log.error("❌ PIPELINE FAILED at stage '%s': %s", e.stage, e)
            topic.mark_failed()
            self._update_topic_status(topic)
            result.error = str(e)

        except Exception as e:
            log.error("❌ UNEXPECTED ERROR: %s", e)
            topic.mark_failed()
            self._update_topic_status(topic)
            result.error = str(e)

        result.total_duration_seconds = self._timer.summary()
        return result

    def _fetch_topic(self) -> Topic | None:
        """Fetch the next pending topic from the queue."""
        with self._timer.step("Fetch Topic"):
            repo = self._container.topic_repository()
            topic = repo.get_next_pending()

            if topic is None:
                log.warning("⚠️  No pending topics in queue!")
                log.info("   Add more rows with Status = Pending")
                return None

            topic.mark_processing()
            repo.update_status(topic)
            log.info("📋 Topic: '%s' (%s)", topic.text, topic.language.display_name)
            return topic

    def _generate_video(self, topic_text: str, language: Language, mode: str) -> VideoOutput:
        """Generate a single video for one language.

        11-step pipeline:
        1. Fetch topic (done before this method)
        2. Generate story
        3. Generate SEO metadata
        4. Generate 5 image prompts from story
        5. Generate 5 scene images (Stable Diffusion)
        6. Generate audio
        7. Generate avatar (SadTalker)
        8. Generate subtitles
        9. Compose slideshow video
        10. Upload YouTube (with scheduler)
        11. Backup + Notify

        Args:
            topic_text: The topic text.
            language: Target language.
            mode: "full" or "test".

        Returns:
            VideoOutput with paths and metadata.
        """
        from concurrent.futures import Future, ThreadPoolExecutor

        from ai_shorts.application.use_cases import (
            CreateAvatarVideoUseCase,
            GenerateMetadataUseCase,
            GenerateStoryUseCase,
            GenerateSubtitlesUseCase,
            GenerateVoiceUseCase,
            PublishVideoUseCase,
        )

        output_dir = self._settings.output_dir / language.value
        output_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 2: Generate Story ──
        with self._timer.step(f"Story Generation ({language.display_name})"):
            story_uc = GenerateStoryUseCase(self._container.story_generator())
            story = story_uc.execute(topic_text, language)

        # ── Step 3: Generate SEO Metadata + Image Prompt (same LLM, back-to-back) ──
        with self._timer.step("SEO + Image Prompt"):
            meta_uc = GenerateMetadataUseCase(self._container.metadata_generator())
            metadata = meta_uc.execute(topic_text, language, story.text)

            prompt_gen = self._container.image_prompt_generator()
            log.info("🎨 Generating 1 image prompt from story...")
            prompts = prompt_gen.generate_scene_prompts(story.text, num_scenes=1)
            log.info("   Image prompt: %s", prompts[0][:80] if prompts else "N/A")

        # Free GPU: unload LLM before image gen / TTS
        self._unload_ollama()

        # ── Steps 4+5: Generate Image + Voice IN PARALLEL ──
        # TTS is cloud-based (Edge TTS) — uses zero GPU, safe to run alongside SD
        scene_dir = output_dir / "scenes"
        audio_path = output_dir / "voice.wav"

        def _generate_voice():
            voice_uc = GenerateVoiceUseCase(self._container.voice_generator())
            return voice_uc.execute(story.text, language, audio_path)

        with (
            self._timer.step("Image + Voice (parallel)"),
            ThreadPoolExecutor(max_workers=1) as executor,
        ):
            # Start TTS in a background thread
            voice_future: Future = executor.submit(_generate_voice)

            # Generate 1 high-quality image on the main thread (uses GPU)
            scene_dir.mkdir(parents=True, exist_ok=True)
            image_path = scene_dir / "scene_01.png"
            bg_gen = self._container.background_generator()
            bg_gen.generate(prompts[0], language, image_path)
            scene_images = [image_path]

            # Wait for TTS to complete
            voice = voice_future.result()

        free_gpu_memory()

        if mode == "test":
            # Test mode: stop after story + images + audio
            log.info("✅ TEST PIPELINE COMPLETE")
            return VideoOutput(
                local_path=audio_path,
                duration_seconds=voice.duration_seconds,
            )

        # ── Step 7: Generate Avatar Video (SadTalker) ──
        avatar_path = output_dir / "avatar.mp4"
        avatar_image = Path(self._settings.avatar_image_path)
        with self._timer.step(f"Avatar Animation ({language.display_name})"):
            avatar_uc = CreateAvatarVideoUseCase(self._container.avatar_animator())
            avatar_asset = avatar_uc.execute(audio_path, avatar_image, avatar_path)
        free_gpu_memory()

        # ── Step 8: Generate Subtitles ──
        subtitle_path = output_dir / "subtitles.srt"
        subtitle_asset = None
        try:
            with self._timer.step(f"Subtitle Generation ({language.display_name})"):
                sub_uc = GenerateSubtitlesUseCase(self._container.subtitle_generator())
                subtitle_asset = sub_uc.execute(audio_path, language, subtitle_path)
            free_gpu_memory()
        except Exception as e:
            log.warning("⚠️  Subtitle generation failed (continuing): %s", e)

        # ── Step 9: Compose Slideshow Video ──
        final_path = output_dir / "final_video.mp4"
        with self._timer.step("Slideshow Video Composition"):
            composer = self._container.video_composer()
            composer.compose_slideshow(
                scene_images=scene_images,
                avatar_video=avatar_asset.path,
                subtitles=subtitle_asset.path if subtitle_asset else None,
                audio=audio_path,
                output_path=final_path,
                duration=voice.duration_seconds,
            )

        # ── Step 10 + 11: Publish (YouTube + Drive + Telegram) ──
        youtube_url = ""
        drive_path = ""
        with self._timer.step("Publishing"):
            publish_uc = PublishVideoUseCase(
                uploader=self._container.video_uploader(),
                storage=self._container.storage_service(),
                notifier=self._container.notification_service(),
            )
            youtube_url, drive_path = publish_uc.execute(
                video_path=final_path,
                title=metadata.title,
                description=metadata.description,
                tags=metadata.tags,
                upload=self._settings.video.auto_upload_youtube,
            )

        return VideoOutput(
            local_path=final_path,
            drive_path=drive_path,
            youtube_url=youtube_url,
            metadata=metadata,
            duration_seconds=voice.duration_seconds,
        )

    def _unload_ollama(self) -> None:
        """Unload Ollama models from GPU to free VRAM."""
        try:
            from ai_shorts.infrastructure.adapters.ollama import OllamaLLMService

            llm = self._container.llm_service()
            if isinstance(llm, OllamaLLMService):
                llm.unload()
        except Exception:
            pass
        free_gpu_memory()
        log.info("🧹 LLM unloaded from GPU")

    def _update_topic_status(self, topic: Topic) -> None:
        """Update topic status in the queue."""
        try:
            repo = self._container.topic_repository()
            repo.update_status(topic)
            log.info("📊 Topic status updated: %s", topic.status.value)
        except Exception as e:
            log.warning("⚠️  Failed to update topic status: %s", e)
