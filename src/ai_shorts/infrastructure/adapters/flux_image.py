"""
Stable Diffusion Adapter — BackgroundGenerator + SceneImageGenerator.

Uses local Stable Diffusion models via the diffusers library.
Generates single backgrounds and multi-scene images for slideshow videos.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.core.gpu import free_gpu_memory
from ai_shorts.core.resilience import retry_with_backoff
from ai_shorts.domain.entities import SceneSegment, VideoAsset
from ai_shorts.domain.exceptions import BackgroundGenerationError
from ai_shorts.domain.ports import BackgroundGenerator, SceneImageGenerator
from ai_shorts.domain.value_objects import AssetType, Language

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)

# Default lightweight SD model (good balance of speed + quality)
DEFAULT_SD_MODEL = "stabilityai/stable-diffusion-2-1"


class StableDiffusionBackgroundGenerator(BackgroundGenerator):
    """Local Stable Diffusion image generation via diffusers.

    Features:
    - Fully local — no API keys, no cloud dependency
    - GPU accelerated with CPU offload for low-VRAM cards
    - Dual-orientation: landscape (1280x720) + portrait (720x1280)
    - Cultural style prompts per language
    - Automatic retry with exponential backoff
    """

    def __init__(self, settings: Settings) -> None:
        self._model_id = getattr(settings, "sd_model", "") or DEFAULT_SD_MODEL
        self._inference_steps = settings.gpu.sdxl_inference_steps

    @retry_with_backoff(max_retries=2, base_delay=5.0)
    def generate(self, topic: str, language: Language, output_path: Path) -> VideoAsset:
        """Generate a cinematic background image using local Stable Diffusion.

        Args:
            topic: Image prompt or topic.
            language: Content language (affects cultural style).
            output_path: Where to save the image.

        Returns:
            VideoAsset for the generated image.

        Raises:
            BackgroundGenerationError: If generation fails.
        """
        try:
            import torch
            from diffusers import StableDiffusionPipeline
        except ImportError as e:
            raise BackgroundGenerationError(
                "diffusers/torch not installed. Run: pip install 'ai-shorts[gpu]'",
                cause=e,
            ) from e

        prompt = self._build_prompt(topic, language)
        negative_prompt = (
            "text, watermark, logo, blurry, low quality, ugly, "
            "deformed, noisy, oversaturated, cartoon, anime"
        )

        # Portrait for YouTube Shorts
        width, height = 768, 1344  # ~9:16 ratio

        log.info(
            "🖼️  Generating SD image (%s, %d steps)...",
            self._model_id.split("/")[-1],
            self._inference_steps,
        )
        log.info("   Prompt: %s", prompt[:100])

        try:
            pipe = StableDiffusionPipeline.from_pretrained(
                self._model_id,
                torch_dtype=torch.float16,
                safety_checker=None,
            )
            pipe.enable_model_cpu_offload()

            image = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=self._inference_steps,
                guidance_scale=7.5,
                width=width,
                height=height,
            ).images[0]

            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(output_path))

            del pipe
            free_gpu_memory()

            log.info("✅ SD image saved: %s", output_path)
            return VideoAsset(
                path=output_path,
                asset_type=AssetType.BACKGROUND_IMAGE,
                width=width,
                height=height,
            )

        except BackgroundGenerationError:
            raise
        except Exception as e:
            raise BackgroundGenerationError(
                f"Stable Diffusion image generation failed: {e}",
                cause=e,
            ) from e

    def generate_multi(
        self, topic: str, language: Language, output_dir: Path
    ) -> dict[str, VideoAsset]:
        """Generate both landscape and portrait images.

        Args:
            topic: Image generation topic/prompt.
            language: Content language.
            output_dir: Directory to save images.

        Returns:
            Dict with 'landscape' and 'portrait' VideoAsset entries.
        """
        try:
            import torch
            from diffusers import StableDiffusionPipeline
        except ImportError:
            return {}

        prompt = self._build_prompt(topic, language)
        negative_prompt = (
            "text, watermark, logo, blurry, low quality, ugly, deformed, noisy, oversaturated"
        )

        formats = {
            "landscape": (1280, 720),
            "portrait": (720, 1280),
        }

        results: dict[str, VideoAsset] = {}

        try:
            log.info("🖼️  Loading SD model: %s", self._model_id)
            pipe = StableDiffusionPipeline.from_pretrained(
                self._model_id,
                torch_dtype=torch.float16,
                safety_checker=None,
            )
            pipe.enable_model_cpu_offload()

            for orientation, (w, h) in formats.items():
                log.info("   Generating %s (%dx%d)...", orientation, w, h)

                image = pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=self._inference_steps,
                    guidance_scale=7.5,
                    width=w,
                    height=h,
                ).images[0]

                path = output_dir / f"{orientation}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(str(path))

                results[orientation] = VideoAsset(
                    path=path,
                    asset_type=AssetType.BACKGROUND_IMAGE,
                    width=w,
                    height=h,
                )
                log.info("   ✅ Saved %s: %s", orientation, path)

            del pipe
            free_gpu_memory()

        except Exception as e:
            log.warning("⚠️  Multi-image generation failed: %s", e)

        return results

    @staticmethod
    def _build_prompt(topic: str, language: Language) -> str:
        """Build a cinematic prompt with cultural style."""
        cultural_style = {
            Language.TAMIL: "Indian cultural, warm golden tones, Tamil Nadu landscape",
            Language.HINDI: "Indian cultural, Bollywood cinematic, vibrant colors",
            Language.ENGLISH: "Western cinematic, dramatic lighting, modern",
        }.get(language, "cinematic, dramatic lighting")

        return (
            f"Cinematic background for motivational video about '{topic}', "
            f"{cultural_style}, "
            "ultra high quality, 8k, professional photography, "
            "dramatic lighting, bokeh background, no people, no text, "
            "atmospheric, moody, inspirational"
        )


class StableDiffusionSceneImageGenerator(SceneImageGenerator):
    """Generates per-segment scene images using local Stable Diffusion.

    Creates multiple images (one per SceneSegment) in a single pipeline
    session for efficiency, reusing the loaded model.
    """

    def __init__(self, settings: Settings) -> None:
        self._model_id = getattr(settings, "sd_model", "") or DEFAULT_SD_MODEL
        self._inference_steps = settings.gpu.sdxl_inference_steps

    def generate_scenes(
        self,
        segments: list[SceneSegment],
        output_dir: Path,
    ) -> list[VideoAsset]:
        """Generate one image per scene segment.

        Args:
            segments: Scene segments with prompts.
            output_dir: Directory to save images.

        Returns:
            List of VideoAsset entities (one per segment).
        """
        try:
            import torch
            from diffusers import StableDiffusionPipeline
        except ImportError as e:
            raise BackgroundGenerationError(
                "diffusers/torch not installed. Run: pip install 'ai-shorts[gpu]'",
                cause=e,
            ) from e

        output_dir.mkdir(parents=True, exist_ok=True)
        negative = (
            "text, watermark, logo, blurry, low quality, ugly, "
            "deformed, noisy, oversaturated, cartoon, anime"
        )

        # Portrait for YouTube Shorts
        width, height = 768, 1344

        log.info(
            "🖼️  Generating %d scene images (%s)...",
            len(segments),
            self._model_id.split("/")[-1],
        )

        assets: list[VideoAsset] = []

        try:
            pipe = StableDiffusionPipeline.from_pretrained(
                self._model_id,
                torch_dtype=torch.float16,
                safety_checker=None,
            )
            pipe.enable_model_cpu_offload()

            for i, segment in enumerate(segments):
                prompt = (
                    f"{segment.prompt}, cinematic lighting, "
                    "professional photography, highly detailed, "
                    "4k resolution, no text, no watermark"
                )
                log.info(
                    "   [%d/%d] Generating: %s",
                    i + 1,
                    len(segments),
                    segment.prompt[:60],
                )

                image = pipe(
                    prompt=prompt,
                    negative_prompt=negative,
                    num_inference_steps=self._inference_steps,
                    guidance_scale=7.5,
                    width=width,
                    height=height,
                ).images[0]

                path = output_dir / f"scene_{i + 1:02d}.png"
                image.save(str(path))

                assets.append(
                    VideoAsset(
                        path=path,
                        asset_type=AssetType.SCENE_IMAGE,
                        width=width,
                        height=height,
                    )
                )

            del pipe
            free_gpu_memory()

            log.info("✅ Generated %d scene images", len(assets))
            return assets

        except BackgroundGenerationError:
            raise
        except Exception as e:
            raise BackgroundGenerationError(f"Scene image generation failed: {e}", cause=e) from e
