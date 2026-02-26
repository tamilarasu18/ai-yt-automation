"""Tests for use cases with mocked ports."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_shorts.application.use_cases import (
    GenerateStoryUseCase,
    GenerateVoiceUseCase,
    PublishVideoUseCase,
)
from ai_shorts.domain.entities import Story, Voice
from ai_shorts.domain.exceptions import StoryGenerationError, VoiceGenerationError
from ai_shorts.domain.value_objects import Language


class TestGenerateStoryUseCase:
    """Tests for story generation use case."""

    def test_successful_generation(self) -> None:
        mock_generator = MagicMock()
        mock_generator.generate.return_value = Story(
            text=(
                "A young athlete woke up at four in the morning every single day "
                "for three long years. People called him crazy. His coach said he "
                "would burn out. But he knew something they did not. Discipline is "
                "not punishment. It is freedom. Your discipline today is your trophy."
            ),
            language=Language.ENGLISH,
        )

        use_case = GenerateStoryUseCase(mock_generator)
        result = use_case.execute("Discipline", Language.ENGLISH)

        assert isinstance(result, Story)
        assert result.word_count >= 10
        mock_generator.generate.assert_called_once_with("Discipline", Language.ENGLISH)

    def test_generator_failure_raises_domain_error(self) -> None:
        mock_generator = MagicMock()
        mock_generator.generate.side_effect = RuntimeError("LLM unavailable")

        use_case = GenerateStoryUseCase(mock_generator)
        with pytest.raises(StoryGenerationError, match="Failed to generate story"):
            use_case.execute("Test", Language.ENGLISH)

    def test_too_short_story_raises(self) -> None:
        mock_generator = MagicMock()
        mock_generator.generate.return_value = Story(text="Too short", language=Language.ENGLISH)

        use_case = GenerateStoryUseCase(mock_generator)
        with pytest.raises(StoryGenerationError, match="too short"):
            use_case.execute("Test", Language.ENGLISH)


class TestGenerateVoiceUseCase:
    """Tests for voice generation use case."""

    def test_successful_synthesis(self, tmp_path: Path) -> None:
        output_path = tmp_path / "voice.wav"
        mock_generator = MagicMock()
        mock_generator.synthesize.return_value = Voice(
            audio_path=output_path,
            duration_seconds=45.0,
            language=Language.ENGLISH,
            voice_id="en-US-AriaNeural",
        )

        use_case = GenerateVoiceUseCase(mock_generator)
        result = use_case.execute("Hello world", Language.ENGLISH, output_path)

        assert isinstance(result, Voice)
        assert result.duration_seconds == 45.0

    def test_synthesis_failure_raises_domain_error(self, tmp_path: Path) -> None:
        mock_generator = MagicMock()
        mock_generator.synthesize.side_effect = ConnectionError("TTS unavailable")

        use_case = GenerateVoiceUseCase(mock_generator)
        with pytest.raises(VoiceGenerationError):
            use_case.execute("Test", Language.ENGLISH, tmp_path / "voice.wav")


class TestPublishVideoUseCase:
    """Tests for video publishing use case."""

    def test_full_publish(self, tmp_path: Path) -> None:
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        mock_uploader = MagicMock()
        mock_uploader.upload.return_value = "https://youtube.com/shorts/abc123"

        mock_storage = MagicMock()
        mock_storage.save.return_value = "/drive/videos/short_20260226.mp4"

        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True

        use_case = PublishVideoUseCase(
            uploader=mock_uploader,
            storage=mock_storage,
            notifier=mock_notifier,
        )

        youtube_url, drive_path = use_case.execute(
            video_path, "Test Title", "Test Description", ["test"]
        )

        assert youtube_url == "https://youtube.com/shorts/abc123"
        assert "drive" in drive_path.lower()
        mock_notifier.send.assert_called_once()

    def test_publish_without_youtube(self, tmp_path: Path) -> None:
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        mock_storage = MagicMock()
        mock_storage.save.return_value = "/drive/video.mp4"

        use_case = PublishVideoUseCase(storage=mock_storage)
        youtube_url, drive_path = use_case.execute(video_path, "Title", "Desc", [], upload=False)

        assert youtube_url == ""
        assert drive_path == "/drive/video.mp4"

    def test_notification_failure_non_fatal(self, tmp_path: Path) -> None:
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        mock_notifier = MagicMock()
        mock_notifier.send.side_effect = ConnectionError("Network down")

        use_case = PublishVideoUseCase(notifier=mock_notifier)
        # Should not raise despite notification failure
        use_case.execute(video_path, "Title", "Desc", [], upload=False)
