"""
Kokoro TTS Adapter — VoiceGenerator implementation.

Local, CPU-friendly text-to-speech using the Kokoro pipeline.
Alternative to Edge TTS — works offline, no API key needed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.domain.entities import Voice
from ai_shorts.domain.exceptions import VoiceGenerationError
from ai_shorts.domain.ports import VoiceGenerator
from ai_shorts.domain.value_objects import Language

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class KokoroVoiceGenerator(VoiceGenerator):
    """Local TTS using Kokoro pipeline.

    Features:
    - Text chunking (100-word blocks) for stable generation
    - Automatic language detection
    - CPU-friendly (no GPU required)
    - Multiple voice presets available
    """

    VOICE_MAP = {
        Language.ENGLISH: "af_heart",
        Language.TAMIL: "af_heart",
        Language.HINDI: "af_heart",
        Language.BOTH: "af_heart",
    }

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def synthesize(self, text: str, language: Language, output_path: Path) -> Voice:
        """Synthesize speech from text using Kokoro.

        Args:
            text: Text to convert to speech.
            language: Language for voice selection.
            output_path: Where to save the audio file.

        Returns:
            A Voice entity with audio metadata.
        """
        try:
            import numpy as np
            import soundfile as sf
            from kokoro import KPipeline
        except ImportError as e:
            raise VoiceGenerationError(
                "kokoro not installed. Run: pip install kokoro soundfile",
                cause=e,
            ) from e

        log.info("🔊 Generating voice with Kokoro TTS...")

        voice = self.VOICE_MAP.get(language, "af_heart")

        try:
            pipeline = KPipeline(lang_code="a")  # Auto language detection
            chunks = self._split_text(text, max_words=100)
            all_segments: list = []

            for i, chunk in enumerate(chunks):
                log.info("   Processing chunk %d/%d...", i + 1, len(chunks))
                generator = pipeline(chunk, voice=voice)
                for _gs, _ps, audio in generator:
                    all_segments.append(audio)

            if not all_segments:
                raise VoiceGenerationError("No audio segments generated")

            final_audio = np.concatenate(all_segments, axis=0)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), final_audio, 24000)

            duration = len(final_audio) / 24000.0
            log.info("✅ Kokoro TTS: %.1fs audio saved to %s", duration, output_path)

            return Voice(
                audio_path=output_path,
                duration_seconds=duration,
                language=language,
                voice_id=f"kokoro:{voice}",
            )

        except VoiceGenerationError:
            raise
        except Exception as e:
            raise VoiceGenerationError(f"Kokoro TTS failed: {e}", cause=e) from e

    @staticmethod
    def _split_text(text: str, max_words: int = 100) -> list[str]:
        """Split text into chunks of approximately max_words words."""
        words = text.split()
        return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]
