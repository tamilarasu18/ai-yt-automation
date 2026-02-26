"""Tests for configuration loading and validation."""

from __future__ import annotations

from ai_shorts.domain.value_objects import Language, TopicStatus, VideoPrivacy


class TestValueObjects:
    """Tests for value objects used in configuration."""

    def test_language_values(self) -> None:
        assert Language.TAMIL.value == "ta"
        assert Language.ENGLISH.value == "en"
        assert Language.HINDI.value == "hi"

    def test_topic_status_values(self) -> None:
        assert TopicStatus.PENDING.value == "Pending"
        assert TopicStatus.DONE.value == "Done"
        assert TopicStatus.FAILED.value == "Failed"

    def test_video_privacy_values(self) -> None:
        assert VideoPrivacy.PUBLIC.value == "public"
        assert VideoPrivacy.PRIVATE.value == "private"
        assert VideoPrivacy.UNLISTED.value == "unlisted"
