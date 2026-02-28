"""
Stable Diffusion Adapter — BackgroundGenerator + SceneImageGenerator.

Uses local Stable Diffusion models via the diffusers library.
Generates single backgrounds and multi-scene images for slideshow videos.
Supports SDXL Turbo for fast, high-quality generation.
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

# Default model — SDXL Turbo (fast + high quality)
DEFAULT_SD_MODEL = "stabilityai/sdxl-turbo"

# Models that use the Turbo pipeline (few-step, no guidance)
TURBO_MODELS = {"stabilityai/sdxl-turbo", "stabilityai/sd-turbo"}


def _is_turbo(model_id: str) -> bool:
    """Check if a model is a Turbo distilled model."""
    return model_id in TURBO_MODELS or "turbo" in model_id.lower()


class StableDiffusionBackgroundGenerator(BackgroundGenerator):
    """Local Stable Diffusion image generation via diffusers.

    Features:
    - Fully local — no API keys, no cloud dependency
    - GPU accelerated with CPU offload for low-VRAM cards
    - Supports SDXL Turbo for fast generation (4 steps)
    - Cultural style prompts per language
    - Automatic retry with exponential backoff
    """

    def __init__(self, settings: Settings) -> None:
        self._model_id = getattr(settings, "sd_model", "") or DEFAULT_SD_MODEL
        self._image_style = getattr(settings, "image_style", "anime illustration")
        self._inference_steps = (
            4 if _is_turbo(self._model_id) else settings.gpu.sdxl_inference_steps
        )

    @retry_with_backoff(max_retries=2, base_delay=5.0)
    def generate(self, topic: str, language: Language, output_path: Path) -> VideoAsset:
        """Generate a cinematic background image using local Stable Diffusion."""
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError as e:
            raise BackgroundGenerationError(
                "diffusers/torch not installed. Run: pip install 'ai-shorts[gpu]'",
                cause=e,
            ) from e

        prompt = self._build_prompt(topic, language)
        negative_prompt = (
            "text, watermark, logo, blurry, low quality, ugly, "
            "deformed, noisy, oversaturated, extra fingers, bad anatomy"
        )

        # Portrait for YouTube Shorts
        width, height = 512, 912  # ~9:16 ratio, upscaled by MoviePy
        turbo = _is_turbo(self._model_id)

        log.info(
            "🖼️  Generating image (%s, %d steps%s)...",
            self._model_id.split("/")[-1],
            self._inference_steps,
            ", turbo" if turbo else "",
        )
        log.info("   Prompt: %s", prompt[:120])

        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                self._model_id,
                torch_dtype=torch.float16,
                variant="fp16" if not turbo else None,
                safety_checker=None,
                token=False,
            )
            pipe.enable_model_cpu_offload()

            gen_kwargs = {
                "prompt": prompt,
                "num_inference_steps": self._inference_steps,
                "width": width,
                "height": height,
            }

            if turbo:
                gen_kwargs["guidance_scale"] = 0.0
            else:
                gen_kwargs["negative_prompt"] = negative_prompt
                gen_kwargs["guidance_scale"] = 7.5

            image = pipe(**gen_kwargs).images[0]

            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(output_path))

            del pipe
            free_gpu_memory()

            log.info("✅ Image saved: %s", output_path)
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
        """Generate both landscape and portrait images."""
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError:
            return {}

        prompt = self._build_prompt(topic, language)
        turbo = _is_turbo(self._model_id)
        formats = {"landscape": (1280, 720), "portrait": (720, 1280)}
        results: dict[str, VideoAsset] = {}

        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                self._model_id,
                torch_dtype=torch.float16,
                safety_checker=None,
            )
            pipe.enable_model_cpu_offload()

            for orientation, (w, h) in formats.items():
                log.info("   Generating %s (%dx%d)...", orientation, w, h)

                gen_kwargs = {
                    "prompt": prompt,
                    "num_inference_steps": self._inference_steps,
                    "width": w,
                    "height": h,
                }
                if turbo:
                    gen_kwargs["guidance_scale"] = 0.0
                else:
                    gen_kwargs["guidance_scale"] = 7.5

                image = pipe(**gen_kwargs).images[0]
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

    def _build_prompt(self, topic: str, language: Language) -> str:
        """Build a styled prompt with cultural context."""
        cultural_style = {
            Language.TAMIL: "Indian cultural, warm golden tones, Tamil Nadu landscape",
            Language.HINDI: "Indian cultural, Bollywood cinematic, vibrant colors",
            Language.ENGLISH: "dramatic lighting, modern",
        }.get(language, "dramatic lighting")

        return (
            f"{self._image_style} style, "
            f"scene about '{topic}', "
            f"{cultural_style}, "
            "highly detailed, vivid colors, "
            "professional quality, no text, no watermark"
        )


class StableDiffusionSceneImageGenerator(SceneImageGenerator):
    """Generates per-segment scene images using local Stable Diffusion.

    Creates multiple images (one per SceneSegment) in a single pipeline
    session for efficiency, reusing the loaded model.
    """

    def __init__(self, settings: Settings) -> None:
        self._model_id = getattr(settings, "sd_model", "") or DEFAULT_SD_MODEL
        self._image_style = getattr(settings, "image_style", "anime illustration")
        self._inference_steps = (
            4 if _is_turbo(self._model_id) else settings.gpu.sdxl_inference_steps
        )

    def generate_scenes(
        self,
        segments: list[SceneSegment],
        output_dir: Path,
    ) -> list[VideoAsset]:
        """Generate one image per scene segment."""
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError as e:
            raise BackgroundGenerationError(
                "diffusers/torch not installed. Run: pip install 'ai-shorts[gpu]'",
                cause=e,
            ) from e

        output_dir.mkdir(parents=True, exist_ok=True)
        turbo = _is_turbo(self._model_id)

        # Portrait for YouTube Shorts
        width, height = 512, 912

        log.info(
            "🖼️  Generating %d scene images (%s, %d steps)...",
            len(segments),
            self._model_id.split("/")[-1],
            self._inference_steps,
        )

        assets: list[VideoAsset] = []

        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                self._model_id,
                torch_dtype=torch.float16,
                variant="fp16" if not turbo else None,
                safety_checker=None,
                token=False,
            )
            pipe.enable_model_cpu_offload()

            for i, segment in enumerate(segments):
                # Inject style into each scene prompt
                prompt = (
                    f"{self._image_style} style, "
                    f"{segment.prompt}, "
                    "highly detailed, vivid colors, expressive characters, "
                    "professional quality, no text, no watermark"
                )
                log.info(
                    "   [%d/%d] Generating: %s",
                    i + 1,
                    len(segments),
                    segment.prompt[:60],
                )

                gen_kwargs = {
                    "prompt": prompt,
                    "num_inference_steps": self._inference_steps,
                    "width": width,
                    "height": height,
                }

                if turbo:
                    gen_kwargs["guidance_scale"] = 0.0
                else:
                    gen_kwargs["negative_prompt"] = (
                        "text, watermark, logo, blurry, low quality, ugly, "
                        "deformed, extra fingers, bad anatomy"
                    )
                    gen_kwargs["guidance_scale"] = 7.5

                image = pipe(**gen_kwargs).images[0]

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
