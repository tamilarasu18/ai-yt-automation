"""
SDXL Adapter — BackgroundGenerator implementation.

Uses Stable Diffusion SDXL to generate cinematic background
images optimized for YouTube Shorts (9:16 portrait format).
Uses CPU offload for Colab T4 GPU compatibility.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.core.gpu import free_gpu_memory
from ai_shorts.domain.entities import VideoAsset
from ai_shorts.domain.exceptions import BackgroundGenerationError
from ai_shorts.domain.ports import BackgroundGenerator
from ai_shorts.domain.value_objects import AssetType, Language

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class SDXLBackgroundGenerator(BackgroundGenerator):
    """Generates cinematic backgrounds using Stable Diffusion SDXL.

    Optimized for YouTube Shorts with 9:16 portrait orientation.
    Uses model CPU offload to fit within Colab T4's 15GB VRAM.
    """

    def __init__(self, settings: Settings) -> None:
        self._model_id = settings.gpu.sdxl_model
        self._inference_steps = settings.gpu.sdxl_inference_steps

    def generate(self, topic: str, language: Language, output_path: Path) -> VideoAsset:
        """Generate a cinematic background image.

        Args:
            topic: Theme for the background.
            language: Content language (affects style prompt).
            output_path: Where to save the image.

        Returns:
            VideoAsset for the background image.

        Raises:
            BackgroundGenerationError: If generation fails.
        """
        try:
            import torch
            from diffusers import StableDiffusionXLPipeline
        except ImportError as e:
            raise BackgroundGenerationError(
                "diffusers/torch not installed. Run: pip install 'ai-shorts[gpu]'",
                cause=e,
            ) from e

        prompt = self._build_prompt(topic, language)
        negative_prompt = (
            "text, watermark, logo, blurry, low quality, ugly, deformed, noisy, oversaturated"
        )

        log.info("🖼️  Generating SDXL background (%d steps)...", self._inference_steps)
        log.info("   Prompt: %s", prompt[:100])

        try:
            pipe = StableDiffusionXLPipeline.from_pretrained(
                self._model_id,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True,
            )
            pipe.enable_model_cpu_offload()

            image = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=self._inference_steps,
                guidance_scale=7.5,
                width=768,
                height=1344,  # ~9:16 ratio
            ).images[0]

            image.save(str(output_path))

            del pipe
            free_gpu_memory()

            log.info("✅ Background generated: %s", output_path)
            return VideoAsset(
                path=output_path,
                asset_type=AssetType.BACKGROUND_IMAGE,
                width=768,
                height=1344,
            )

        except Exception as e:
            raise BackgroundGenerationError(
                f"SDXL background generation failed: {e}", cause=e
            ) from e

    # CLIP tokenizer limit: 77 tokens ≈ ~300 characters.
    # Prompt template overhead is ~100 chars, so topic must be ≤ 200 chars.
    _MAX_TOPIC_CHARS = 200

    @classmethod
    def _build_prompt(cls, topic: str, language: Language) -> str:
        """Build an SDXL prompt for cinematic background.

        Keeps the total prompt under CLIP's 77-token limit to avoid
        truncation of important visual details.
        """
        # Truncate topic to stay within CLIP budget
        truncated = (
            topic[: cls._MAX_TOPIC_CHARS].rsplit(" ", 1)[0]
            if len(topic) > cls._MAX_TOPIC_CHARS
            else topic
        )

        cultural_style = {
            Language.TAMIL: "Indian, warm golden tones",
            Language.HINDI: "Indian, Bollywood cinematic",
            Language.ENGLISH: "cinematic, dramatic lighting",
        }.get(language, "cinematic")

        return (
            f"{truncated}, "
            f"{cultural_style}, "
            "8k, professional photography, bokeh, "
            "no text, atmospheric, moody"
        )
