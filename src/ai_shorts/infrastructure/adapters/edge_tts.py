"""
Edge TTS Adapter — VoiceGenerator implementation.

Uses Microsoft Edge's free TTS service for high-quality,
multilingual speech synthesis. Supports Tamil, English, and Hindi.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.domain.entities import Voice
from ai_shorts.domain.exceptions import VoiceGenerationError
from ai_shorts.domain.ports import VoiceGenerator
from ai_shorts.domain.value_objects import Language

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)

# Voice mapping: language → Edge TTS voice ID
VOICE_MAP: dict[Language, str] = {
    Language.TAMIL: "ta-IN-PallaviNeural",
    Language.ENGLISH: "en-US-AriaNeural",
    Language.HINDI: "hi-IN-SwaraNeural",
}


class EdgeTTSVoiceGenerator(VoiceGenerator):
    """Synthesizes speech using Microsoft Edge TTS.

    Free, high-quality neural voices. No API key required.
    Supports async generation with nest_asyncio for Colab compat.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def synthesize(self, text: str, language: Language, output_path: Path) -> Voice:
        """Synthesize speech from text.

        Args:
            text: Text to convert to speech.
            language: Language for voice selection.
            output_path: Where to save the audio file.

        Returns:
            Voice entity with audio metadata.

        Raises:
            VoiceGenerationError: If synthesis fails.
        """
        try:
            import edge_tts
        except ImportError as e:
            raise VoiceGenerationError(
                "edge-tts not installed. Run: pip install edge-tts", cause=e
            ) from e

        voice_id = VOICE_MAP.get(language, VOICE_MAP[Language.ENGLISH])
        log.info("🔊 Generating voice with Edge TTS (%s)...", voice_id)

        async def _generate() -> None:
            communicate = edge_tts.Communicate(text, voice_id, rate="-5%")
            await communicate.save(str(output_path))

        try:
            self._run_async(_generate())
        except Exception as e:
            raise VoiceGenerationError(
                f"Edge TTS synthesis failed: {e}", cause=e
            ) from e

        duration = self._get_audio_duration(output_path)
        log.info("✅ Voice generated: %.1fs (%s, %s)", duration, language.value, voice_id)

        return Voice(
            audio_path=output_path,
            duration_seconds=duration,
            language=language,
            voice_id=voice_id,
        )

    @staticmethod
    def _run_async(coro: object) -> None:
        """Run an async coroutine, handling Colab's running event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio

                nest_asyncio.apply()
                loop.run_until_complete(coro)
            else:
                asyncio.run(coro)
        except RuntimeError:
            asyncio.run(coro)

    @staticmethod
    def _get_audio_duration(path: Path) -> float:
        """Get audio duration in seconds using ffprobe."""
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 30.0  # Fallback duration
