"""
Configuration — type-safe settings via Pydantic BaseSettings.

Loads from environment variables or .env file. Each service has its own
nested config group for clean separation and validation.

Usage:
    settings = Settings()  # auto-loads from .env
    print(settings.google.sheet_url)
    print(settings.ollama.model)
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_shorts.domain.value_objects import VideoMode, VideoPrivacy


class GoogleConfig(BaseSettings):
    """Google API configuration."""

    model_config = SettingsConfigDict(env_prefix="GOOGLE_")

    service_account_file: str = ""
    sheet_url: str = ""
    sheet_name: str = "Sheet1"


class YouTubeConfig(BaseSettings):
    """YouTube upload configuration."""

    model_config = SettingsConfigDict(env_prefix="YOUTUBE_")

    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""


class TelegramConfig(BaseSettings):
    """Telegram notification configuration."""

    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")

    bot_token: str = ""
    chat_id: str = ""

    @property
    def is_configured(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return bool(self.bot_token and self.chat_id)


class OllamaConfig(BaseSettings):
    """Ollama LLM configuration."""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    host: str = "http://localhost:11434"
    model: str = "gemma3:12b"


class VideoConfig(BaseSettings):
    """Video generation settings."""

    width: int = 1080
    height: int = 1920
    fps: int = 30
    max_duration_seconds: int = 58
    privacy: VideoPrivacy = VideoPrivacy.PUBLIC
    enable_face_enhancement: bool = True
    auto_upload_youtube: bool = True
    background_music_path: str = ""
    font_file: str = ""
    video_mode: VideoMode = VideoMode.AVATAR

    model_config = SettingsConfigDict(env_prefix="VIDEO_")


class GPUConfig(BaseSettings):
    """GPU-dependent model configuration."""

    whisper_model_size: str = "base"
    sdxl_model: str = "stabilityai/stable-diffusion-xl-base-1.0"
    sdxl_inference_steps: int = 20
    sadtalker_dir: str = "/content/SadTalker"

    model_config = SettingsConfigDict(env_prefix="")

    @field_validator("whisper_model_size")
    @classmethod
    def validate_whisper_model(cls, v: str) -> str:
        allowed = {"tiny", "base", "small", "medium", "large-v3"}
        if v not in allowed:
            raise ValueError(f"whisper_model_size must be one of {allowed}")
        return v


class Settings(BaseSettings):
    """Root application settings — aggregates all config groups.

    Load order:
        1. Environment variables
        2. .env file (if present)
        3. Default values

    Usage:
        settings = Settings()
        settings = Settings(_env_file=".env.local")
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    work_dir: Path = Path("/content/ai-shorts")
    output_dir: Path = Path("/content/ai-shorts/output")
    avatar_image_path: str = "assets/images/avatar.png"
    drive_output_folder: str = ""

    # Nested configs
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    gpu: GPUConfig = Field(default_factory=GPUConfig)

    # API tokens
    sd_model: str = "CompVis/stable-diffusion-v1-4"

    # Pipeline
    max_retries: int = 3
    tts_engine: str = "edge"  # "edge" or "kokoro"
    image_engine: str = "sdxl"  # "sdxl" or "sd" (Stable Diffusion 2.1)

    def ensure_directories(self) -> None:
        """Create working directories if they don't exist."""
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
