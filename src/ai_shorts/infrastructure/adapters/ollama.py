"""
Ollama Adapter — LLMService, StoryGenerator, and MetadataGenerator implementations.

Connects to a local Ollama server for text generation using models
like gemma3:12b. Handles server lifecycle, model pulling, and
GPU memory management.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.request
from typing import TYPE_CHECKING

from ai_shorts.core.resilience import retry_with_backoff
from ai_shorts.domain.entities import Story, VideoMetadata
from ai_shorts.domain.exceptions import StoryGenerationError
from ai_shorts.domain.ports import (
    ImagePromptGenerator,
    LLMService,
    MetadataGenerator,
    StoryGenerator,
)
from ai_shorts.domain.value_objects import Language

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class OllamaLLMService(LLMService):
    """Local LLM service via Ollama REST API.

    Manages server health checks, auto-pull of models, and
    text generation with configurable parameters.
    """

    def __init__(self, settings: Settings) -> None:
        self._host = settings.ollama.host
        self._default_model = settings.ollama.model

    def _is_running(self) -> bool:
        """Check if the Ollama server is responding."""
        try:
            req = urllib.request.Request(f"{self._host}/api/tags")
            urllib.request.urlopen(req, timeout=3)
            return True
        except Exception:
            return False

    def ensure_running(self) -> bool:
        """Ensure the Ollama server is running. Start if needed.

        Returns:
            True if server is available.
        """
        if self._is_running():
            log.info("✅ Ollama server already running")
            return True

        log.info("🚀 Starting Ollama server...")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            log.error("❌ Ollama binary not found — install from https://ollama.com")
            return False

        for i in range(10):
            time.sleep(2)
            if self._is_running():
                log.info("✅ Ollama server ready (took %ds)", (i + 1) * 2)
                return True
            log.info("   Waiting for Ollama server... (%ds)", (i + 1) * 2)

        log.error("❌ Ollama server failed to start after 20s")
        return False

    @retry_with_backoff(max_retries=2, base_delay=3.0)
    def generate(self, prompt: str, model: str = "") -> str:
        """Generate text using Ollama.

        Args:
            prompt: Input prompt.
            model: Model identifier (defaults to config value).

        Returns:
            Generated text.
        """
        if not self.ensure_running():
            raise StoryGenerationError("Ollama server is not available")

        model = model or self._default_model
        url = f"{self._host}/api/generate"
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.9,
                "num_predict": 500,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("response", "").strip()
        except Exception as e:
            if "not found" in str(e).lower() or "404" in str(e):
                log.info("📥 Pulling model '%s' (first time, may take minutes)...", model)
                os.system(f"ollama pull {model}")
                with urllib.request.urlopen(req, timeout=300) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    return result.get("response", "").strip()
            raise

    def unload(self) -> None:
        """Unload models from GPU to free VRAM."""
        try:
            model = self._default_model
            os.system(f"ollama stop {model} > /dev/null 2>&1")
            req = urllib.request.Request(
                f"{self._host}/api/generate",
                data=json.dumps({"model": model, "keep_alive": 0}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
        log.info("🧹 Ollama model unloaded from GPU")


class OllamaStoryGenerator(StoryGenerator):
    """Generates motivational story scripts using Ollama.

    Injects randomized styles, tones, and character settings into
    the prompt for unique, non-repetitive content each run.
    """

    STYLES = [
        "a modern-day moral tale",
        "a historical fiction",
        "a parable set in a village",
        "a science fiction metaphor",
        "a fantasy story with symbolic characters",
        "an emotional story based on a real-life scenario",
        "a story set in a school or college",
        "a corporate drama with ethical choices",
    ]

    TONES = [
        "inspirational and uplifting",
        "emotional and touching",
        "suspenseful and dramatic",
        "subtle and reflective",
        "humorous but meaningful",
    ]

    CHARACTERS = [
        "a curious child and a wise elder",
        "a struggling entrepreneur",
        "a teacher guiding a student",
        "a king learning humility",
        "an AI discovering purpose",
        "a street artist chasing dreams",
        "a monk teaching a traveler",
        "siblings with contrasting beliefs",
    ]

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self._settings = settings
        self._llm = llm

    def generate(self, topic: str, language: Language) -> Story:
        """Generate a motivational story script."""
        prompt = self._build_prompt(topic, language)
        raw_text = self._llm.generate(prompt)
        cleaned = self._clean_story(raw_text)

        return Story(text=cleaned, language=language)

    @classmethod
    def _build_prompt(cls, topic: str, language: Language) -> str:
        """Build a story generation prompt with randomized variety."""
        import random

        style = random.choice(cls.STYLES)
        tone = random.choice(cls.TONES)
        character = random.choice(cls.CHARACTERS)
        lang_name = language.display_name

        return f"""You are a world-class motivational storytelling expert.
Create a SHORT, POWERFUL motivational story for a YouTube Short.

STYLE: Write {style} in a {tone} tone.
CHARACTERS: Feature {character}.

RULES:
- Language: {lang_name}
- Topic/Inspiration: {topic}
- Duration: MUST be speakable in 45-55 seconds
- Start with a JAW-DROPPING hook (first sentence = instant attention)
- Use natural dialogues and emotional depth
- Sentences: SHORT. PUNCHY. POWERFUL.
- End with ONE unforgettable takeaway line
- Around 100-130 words
- NO emojis, NO hashtags, NO stage directions, NO speaker labels
- If Tamil: use conversational spoken Tamil, not formal literary Tamil
- Write ONLY the spoken script. NOTHING else.
- End with: 'Subscribe to my YouTube channel, like, share, and comment.'

SCRIPT:"""

    @staticmethod
    def _clean_story(text: str) -> str:
        """Clean up raw LLM output."""
        for prefix in ["SCRIPT:", "Here is", "Here's", "Sure", "Okay"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                if text.startswith((",", ":", "!", ".")):
                    text = text[1:].strip()

        # Remove markdown formatting
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = text.strip('"').strip("'")
        return text


class OllamaMetadataGenerator(MetadataGenerator):
    """Generates SEO-optimized YouTube metadata using Ollama."""

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self._settings = settings
        self._llm = llm

    def generate(self, topic: str, language: Language, story: str) -> VideoMetadata:
        """Generate video title, description, and tags.

        Args:
            topic: The video topic.
            language: Content language.
            story: The story script.

        Returns:
            VideoMetadata entity.
        """
        prompt = f"""Generate YouTube Shorts metadata for this video.
Topic: {topic}
Language: {language.display_name}

Return EXACTLY this JSON format (no other text):
{{
  "title": "catchy title under 60 chars",
  "description": "SEO description under 200 chars with hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}"""

        raw = self._llm.generate(prompt)

        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return VideoMetadata(
                    title=data.get("title", f"{topic} | Motivation #Shorts"),
                    description=data.get("description", topic),
                    tags=data.get("tags", [topic, "motivation", "shorts"]),
                    language=language,
                )
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback metadata
        return VideoMetadata(
            title=f"{topic} | Motivation #Shorts",
            description=f"{topic} — motivational story. #shorts #motivation",
            tags=[topic, "motivation", "shorts", language.display_name.lower()],
            language=language,
        )


class OllamaImagePromptGenerator(ImagePromptGenerator):
    """Generates image generation prompts from story text using Ollama.

    Summarizes a story into a single-line visual scene description
    suitable for image generation APIs (SDXL, FLUX.1-dev, etc.).
    """

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self._settings = settings
        self._llm = llm

    def generate_prompt(self, story_text: str) -> str:
        """Generate a single-line image prompt from a story."""
        prompt = (
            "Summarize the following motivational story into a single-line "
            "prompt for AI image generation. The prompt should describe one "
            "key visual scene from the story that captures its essence. "
            "Keep it short, clear, and suitable for generating a single "
            "image without including any text or words in the image.\n\n"
            f"Story:\n{story_text.strip()}\n\n"
            "One-line Image Prompt:"
        )
        result = self._llm.generate(prompt)
        return result.strip().strip('"').strip("'")
