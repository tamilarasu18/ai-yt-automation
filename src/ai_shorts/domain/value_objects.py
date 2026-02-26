"""
Domain Value Objects — immutable, self-validating types.

Value objects represent concepts defined by their attributes rather than
a unique identity. They are always immutable and validate their own invariants.
"""

from __future__ import annotations

from enum import Enum


class Language(str, Enum):
    """Supported content languages."""

    TAMIL = "ta"
    ENGLISH = "en"
    HINDI = "hi"
    BOTH = "both"

    @property
    def display_name(self) -> str:
        """Human-readable language name."""
        return {
            Language.TAMIL: "Tamil",
            Language.ENGLISH: "English",
            Language.HINDI: "Hindi",
            Language.BOTH: "Both (Tamil + English)",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> Language:
        """Parse a language string (case-insensitive)."""
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"Unsupported language '{value}'. "
            f"Supported: {', '.join(m.value for m in cls)}"
        )


class TopicStatus(str, Enum):
    """Status of a topic in the processing queue."""

    PENDING = "Pending"
    PROCESSING = "Processing"
    DONE = "Done"
    FAILED = "Failed"


class VideoPrivacy(str, Enum):
    """YouTube video privacy setting."""

    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"


class VideoMode(str, Enum):
    """Video composition mode."""

    AVATAR = "avatar"       # Talking-head with background
    SLIDESHOW = "slideshow"  # Image-based with timed transitions


class AssetType(str, Enum):
    """Type of generated media asset."""

    AVATAR_VIDEO = "avatar_video"
    BACKGROUND_IMAGE = "background_image"
    SCENE_IMAGE = "scene_image"
    VOICE_AUDIO = "voice_audio"
    SUBTITLE_FILE = "subtitle_file"
    COMPOSED_VIDEO = "composed_video"
    SHORTS_VIDEO = "shorts_video"
