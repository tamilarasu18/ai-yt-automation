"""
Whisper Adapter — SubtitleGenerator implementation.

Uses OpenAI Whisper for speech-to-text transcription,
generating SRT subtitle files with accurate timestamps.
Features model fallback (large → medium → base) on OOM.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.core.gpu import free_gpu_memory
from ai_shorts.domain.entities import VideoAsset
from ai_shorts.domain.exceptions import SubtitleError
from ai_shorts.domain.ports import SubtitleGenerator
from ai_shorts.domain.value_objects import AssetType, Language

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)

# Whisper language codes
WHISPER_LANG_MAP: dict[Language, str] = {
    Language.TAMIL: "ta",
    Language.ENGLISH: "en",
    Language.HINDI: "hi",
}


class WhisperSubtitleGenerator(SubtitleGenerator):
    """Generates SRT subtitles using OpenAI Whisper.

    Features automatic model fallback on GPU OOM:
    large-v3 → medium → base
    """

    def __init__(self, settings: Settings) -> None:
        self._model_size = settings.gpu.whisper_model_size
        self._fallback_models = ["medium", "base"]

    def transcribe(
        self, audio_path: Path, language: Language, output_path: Path
    ) -> VideoAsset:
        """Transcribe audio to SRT subtitle file.

        Args:
            audio_path: Path to the audio file.
            language: Language hint for Whisper.
            output_path: Where to save the .srt file.

        Returns:
            VideoAsset for the subtitle file.

        Raises:
            SubtitleError: If all model sizes fail.
        """
        try:
            import whisper
        except ImportError as e:
            raise SubtitleError(
                "openai-whisper not installed. Run: pip install openai-whisper",
                cause=e,
            ) from e

        models_to_try = [self._model_size] + [
            m for m in self._fallback_models if m != self._model_size
        ]
        whisper_lang = WHISPER_LANG_MAP.get(language, "en")

        for model_name in models_to_try:
            try:
                log.info("🎙️  Loading Whisper model '%s'...", model_name)
                model = whisper.load_model(model_name)
                result = model.transcribe(
                    str(audio_path),
                    language=whisper_lang,
                    task="transcribe",
                )

                # Write SRT file
                self._write_srt(result["segments"], output_path)

                # Free model from GPU
                del model
                free_gpu_memory()

                log.info("✅ Subtitles generated with Whisper '%s'", model_name)
                return VideoAsset(
                    path=output_path,
                    asset_type=AssetType.SUBTITLE_FILE,
                )

            except RuntimeError as e:
                if "out of memory" in str(e).lower() or "CUDA" in str(e):
                    log.warning(
                        "⚠️  Whisper '%s' OOM, trying smaller model...", model_name
                    )
                    free_gpu_memory()
                    continue
                raise SubtitleError(
                    f"Whisper transcription failed: {e}", cause=e
                ) from e

        raise SubtitleError(
            f"All Whisper models failed ({', '.join(models_to_try)})"
        )

    @staticmethod
    def _write_srt(segments: list[dict], output_path: Path) -> None:
        """Write segments to SRT format.

        Args:
            segments: Whisper transcription segments.
            output_path: Where to save the .srt file.
        """
        lines: list[str] = []
        for i, seg in enumerate(segments, 1):
            start = WhisperSubtitleGenerator._format_srt_time(seg["start"])
            end = WhisperSubtitleGenerator._format_srt_time(seg["end"])
            text = seg["text"].strip()
            lines.append(f"{i}\n{start} --> {end}\n{text}\n")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Convert seconds to SRT timestamp (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
