"""Tests for domain entities."""

from __future__ import annotations

import pytest

from ai_shorts.domain.entities import Story, Topic, VideoMetadata
from ai_shorts.domain.value_objects import Language, TopicStatus


class TestTopic:
    """Tests for the Topic entity."""

    def test_create_valid_topic(self) -> None:
        topic = Topic(text="The Power of Discipline", language=Language.ENGLISH)
        assert topic.text == "The Power of Discipline"
        assert topic.language == Language.ENGLISH
        assert topic.status == TopicStatus.PENDING

    def test_empty_topic_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            Topic(text="", language=Language.ENGLISH)

    def test_whitespace_topic_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            Topic(text="   ", language=Language.ENGLISH)

    def test_status_transitions(self) -> None:
        topic = Topic(text="Test", language=Language.TAMIL)
        assert topic.status == TopicStatus.PENDING

        topic.mark_processing()
        assert topic.status == TopicStatus.PROCESSING

        topic.mark_done()
        assert topic.status == TopicStatus.DONE

    def test_mark_failed(self) -> None:
        topic = Topic(text="Test", language=Language.HINDI)
        topic.mark_processing()
        topic.mark_failed()
        assert topic.status == TopicStatus.FAILED


class TestStory:
    """Tests for the Story entity."""

    def test_word_count_auto_calculated(self, sample_story_text: str) -> None:
        story = Story(text=sample_story_text, language=Language.ENGLISH)
        assert story.word_count > 0
        assert story.word_count == len(sample_story_text.split())

    def test_validate_valid_story(self, sample_story_text: str) -> None:
        story = Story(text=sample_story_text, language=Language.ENGLISH)
        story.validate()  # Should not raise

    def test_validate_too_short(self) -> None:
        story = Story(text="Short story", language=Language.ENGLISH)
        with pytest.raises(ValueError, match="too short"):
            story.validate(min_words=30)

    def test_validate_too_long(self) -> None:
        long_text = " ".join(["word"] * 250)
        story = Story(text=long_text, language=Language.ENGLISH)
        with pytest.raises(ValueError, match="too long"):
            story.validate(max_words=200)


class TestVideoMetadata:
    """Tests for the VideoMetadata entity."""

    def test_create_metadata(self) -> None:
        meta = VideoMetadata(
            title="Test Title",
            description="Test Description",
            tags=["test", "video"],
            language=Language.ENGLISH,
        )
        assert meta.title == "Test Title"
        assert len(meta.tags) == 2

    def test_default_tags(self) -> None:
        meta = VideoMetadata(title="Test", description="Desc")
        assert meta.tags == []
        assert meta.language == Language.ENGLISH


class TestLanguage:
    """Tests for the Language value object."""

    def test_from_str_valid(self) -> None:
        assert Language.from_str("ta") == Language.TAMIL
        assert Language.from_str("en") == Language.ENGLISH
        assert Language.from_str("hi") == Language.HINDI
        assert Language.from_str("both") == Language.BOTH

    def test_from_str_case_insensitive(self) -> None:
        assert Language.from_str("  EN  ") == Language.ENGLISH

    def test_from_str_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            Language.from_str("fr")

    def test_display_name(self) -> None:
        assert Language.TAMIL.display_name == "Tamil"
        assert Language.ENGLISH.display_name == "English"
