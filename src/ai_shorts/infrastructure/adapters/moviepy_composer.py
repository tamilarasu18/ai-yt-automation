"""
MoviePy Adapter — VideoComposer implementation.

Composes the final YouTube Short (1080x1920, 9:16) from:
  - Avatar video (talking head) or background images (slideshow)
  - Background image (cinematic)
  - Subtitles (JSON-based TextClip rendering)
  - Voice audio + optional background music
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.domain.entities import VideoAsset
from ai_shorts.domain.exceptions import VideoCompositionError
from ai_shorts.domain.ports import VideoComposer
from ai_shorts.domain.value_objects import AssetType

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)

MAX_LINE_LENGTH = 45  # Max characters per subtitle line


class MoviePyVideoComposer(VideoComposer):
    """Composes the final YouTube Short from component assets.

    Layout (9:16 portrait):
    ┌──────────────┐
    │              │
    │  Background  │
    │   (blurred)  │
    │              │
    │ ┌──────────┐ │
    │ │  Avatar  │ │
    │ │ (center) │ │
    │ └──────────┘ │
    │  Subtitles   │
    │              │
    └──────────────┘

    Supports:
    - Background music mixing (looped at 1% volume)
    - Styled subtitle rendering via MoviePy TextClip
    - FFmpeg fallback for subtitle burn-in
    """

    def __init__(self, settings: Settings) -> None:
        self._width = settings.video.width
        self._height = settings.video.height
        self._fps = settings.video.fps
        self._bg_music_path = getattr(settings.video, "background_music_path", None)
        self._font_file = getattr(settings.video, "font_file", None)

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
        """Compose the final video from assets.

        Args:
            avatar_video: Talking-head video.
            background: Background image.
            subtitles: Optional SRT or JSON subtitle file.
            audio: Voice audio file.
            output_path: Where to save the final video.
            duration: Target duration in seconds.
            background_music: Optional background music file path.

        Returns:
            VideoAsset for the composed video.

        Raises:
            VideoCompositionError: If composition fails.
        """
        try:
            from moviepy.editor import (
                AudioFileClip,
                CompositeAudioClip,
                CompositeVideoClip,
                ImageClip,
                VideoFileClip,
                concatenate_audioclips,
            )
        except ImportError as e:
            raise VideoCompositionError(
                "moviepy not installed. Run: pip install moviepy==1.0.3",
                cause=e,
            ) from e

        log.info("🎬 Composing final video (%dx%d)...", self._width, self._height)

        # Resolve background music
        bg_music = background_music or self._bg_music_path

        try:
            # Load avatar video
            avatar_clip = VideoFileClip(str(avatar_video))
            clip_duration = min(avatar_clip.duration, duration)

            # Load and resize background
            bg_clip = (
                ImageClip(str(background))
                .set_duration(clip_duration)
                .resize((self._width, self._height))
            )

            # Center the avatar on the background
            avatar_resized = avatar_clip.resize(width=int(self._width * 0.8))
            avatar_positioned = avatar_resized.set_position("center")

            # Build clip layers
            layers = [bg_clip, avatar_positioned]

            # Add styled subtitles if available
            subtitle_clips = self._build_subtitle_clips(
                subtitles, (self._width, self._height)
            )
            if subtitle_clips:
                layers.extend(subtitle_clips)

            # Composite
            final = CompositeVideoClip(
                layers,
                size=(self._width, self._height),
            ).set_duration(clip_duration)

            # Build audio: speech + optional background music
            voice_audio = AudioFileClip(str(audio)).subclip(0, clip_duration)
            audio_layers = [voice_audio]

            if bg_music and Path(bg_music).exists():
                bg_audio = AudioFileClip(str(bg_music)).volumex(0.01)
                # Loop if shorter than video
                if bg_audio.duration < clip_duration:
                    loops = int(clip_duration / bg_audio.duration) + 1
                    bg_audio = concatenate_audioclips([bg_audio] * loops)
                bg_audio = bg_audio.subclip(0, clip_duration)
                audio_layers.append(bg_audio)
                log.info("🎵 Background music mixed at 1%% volume")

            final_audio = CompositeAudioClip(audio_layers)
            final = final.set_audio(final_audio)

            # Write video
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final.write_videofile(
                str(output_path),
                fps=self._fps,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

            # Clean up
            avatar_clip.close()
            voice_audio.close()

            log.info("✅ Final video composed: %s", output_path)
            return VideoAsset(
                path=output_path,
                asset_type=AssetType.COMPOSED_VIDEO,
                duration_seconds=clip_duration,
                width=self._width,
                height=self._height,
            )

        except VideoCompositionError:
            raise
        except Exception as e:
            raise VideoCompositionError(
                f"Video composition failed: {e}", cause=e
            ) from e

    def _build_subtitle_clips(
        self,
        subtitle_path: Path | None,
        video_size: tuple[int, int],
    ) -> list:
        """Build styled subtitle TextClips from a JSON or SRT file.

        Uses MoviePy TextClip with custom font for beautiful rendering
        instead of FFmpeg burn-in.

        Args:
            subtitle_path: Path to .json or .srt subtitle file.
            video_size: (width, height) of the video.

        Returns:
            List of TextClip objects with timing.
        """
        if not subtitle_path or not Path(subtitle_path).exists():
            return []

        try:
            from moviepy.video.VideoClip import TextClip
        except ImportError:
            return []

        subtitle_path = Path(subtitle_path)

        # Load subtitle data
        if subtitle_path.suffix == ".json":
            subtitles_data = self._load_json_subtitles(subtitle_path)
        elif subtitle_path.suffix == ".srt":
            subtitles_data = self._srt_to_json(subtitle_path)
        else:
            return []

        if not subtitles_data:
            return []

        clips = []
        font = self._font_file or "Arial"

        for sub in subtitles_data:
            formatted = self._word_wrap(sub["text"], MAX_LINE_LENGTH)
            try:
                text_clip = (
                    TextClip(
                        formatted,
                        fontsize=80 if self._height > 1000 else 50,
                        font=font,
                        color="white",
                        stroke_color="black",
                        stroke_width=2,
                        method="caption",
                        size=(video_size[0] - 100, None),
                        align="center",
                    )
                    .set_position("center")
                    .set_start(sub["start"])
                    .set_duration(sub["end"] - sub["start"])
                )
                clips.append(text_clip)
            except Exception as e:
                log.warning("⚠️  Subtitle clip creation failed: %s", e)
                continue

        log.info("📝 Created %d styled subtitle clips", len(clips))
        return clips

    @staticmethod
    def _word_wrap(text: str, max_length: int) -> str:
        """Word-wrap text for subtitle display."""
        words = text.split()
        lines, line = [], ""
        for word in words:
            if len(line + " " + word) <= max_length:
                line += " " + word if line else word
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _load_json_subtitles(path: Path) -> list[dict]:
        """Load subtitles from JSON format."""
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def _srt_to_json(srt_path: Path) -> list[dict]:
        """Convert SRT file to JSON subtitle format."""
        try:
            with open(srt_path, encoding="utf-8") as f:
                content = f.read()

            subtitles = []
            blocks = content.strip().split("\n\n")
            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) >= 3:
                    time_parts = lines[1].split(" --> ")
                    start = _time_to_seconds(time_parts[0])
                    end = _time_to_seconds(time_parts[1])
                    text = " ".join(lines[2:]).strip()
                    subtitles.append({"start": start, "end": end, "text": text})
            return subtitles
        except Exception:
            return []

    @staticmethod
    def _burn_subtitles_ffmpeg(
        input_video: Path, subtitle_path: Path, output_path: Path
    ) -> None:
        """Fallback: burn SRT subtitles into video using FFmpeg."""
        log.info("📝 Burning subtitles via FFmpeg (fallback)...")
        sub_escaped = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-vf", (
                f"subtitles='{sub_escaped}':"
                "force_style='FontName=Arial,FontSize=14,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "Outline=2,Shadow=1,MarginV=40'"
            ),
            "-c:a", "copy",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning("⚠️  FFmpeg subtitle burn failed")


def _time_to_seconds(time_str: str) -> float:
    """Convert SRT timestamp (HH:MM:SS,MS) to seconds."""
    time_str = time_str.strip()
    hours, minutes, rest = time_str.split(":")
    seconds, ms = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(ms) / 1000
