"""Shared test fixtures."""

from __future__ import annotations

import pytest

from ai_shorts.domain.value_objects import Language


@pytest.fixture
def sample_topic_text() -> str:
    return "The Power of Discipline"


@pytest.fixture
def sample_language() -> Language:
    return Language.ENGLISH


@pytest.fixture
def sample_story_text() -> str:
    return (
        "A young athlete woke up at 4 AM every day for three years. "
        "People called him crazy. His coach said he would burn out. "
        "But he knew something they did not. Discipline is not punishment. "
        "It is freedom. Freedom from regret. Freedom from what-ifs. "
        "At the Olympics, when his name was called, he smiled. "
        "Not because he won. But because he knew he gave everything. "
        "The medal was just proof. Your discipline today is your trophy tomorrow."
    )
