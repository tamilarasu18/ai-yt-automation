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
        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "num_predict": 500,
                },
            }
        ).encode("utf-8")

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
                text = text[len(prefix) :].strip()
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
    """Generates multiple scene-specific image prompts from story text.

    Splits a story into visual scenes and generates one image-generation
    prompt per scene, suitable for slideshow-style video composition.
    """

    def __init__(self, settings: Settings, llm: LLMService) -> None:
        self._settings = settings
        self._llm = llm

    def generate_prompt(self, story_text: str) -> str:
        """Generate a single image prompt (for backward compatibility)."""
        prompts = self.generate_scene_prompts(story_text, num_scenes=1)
        return prompts[0] if prompts else ""

    def generate_scene_prompts(self, story_text: str, num_scenes: int = 5) -> list[str]:
        """Generate multiple scene-specific image prompts from a story.

        Args:
            story_text: The full story text.
            num_scenes: Number of scene prompts to generate (default 5).

        Returns:
            List of image generation prompts (one per scene).
        """
        prompt = (
            f"Read the following motivational story and identify exactly "
            f"{num_scenes} KEY MOMENTS. For each moment, write a vivid "
            f"image generation prompt.\n\n"
            f"CRITICAL RULES:\n"
            f"- Each prompt MUST directly depict a specific scene FROM the story\n"
            f"- Describe the CHARACTERS, their ACTIONS, EMOTIONS, and SETTING\n"
            f"- Include specific visual details: facial expressions, body language, environment\n"
            f"- Each scene must be clearly different and progress the story forward\n"
            f"- Keep prompts 15-25 words each\n"
            f"- NO generic descriptions like 'dramatic lighting' or 'cinematic'\n"
            f"- NO text, words, or letters in the images\n"
            f"- Return ONLY the {num_scenes} prompts, numbered 1-{num_scenes}\n\n"
            f"Story:\n{story_text.strip()}\n\n"
            f"Image Prompts:"
        )

        raw = self._llm.generate(prompt)
        return self._parse_prompts(raw, num_scenes)

    @staticmethod
    def _parse_prompts(raw: str, expected: int) -> list[str]:
        """Parse numbered prompts from LLM output."""
        # Lines that indicate LLM meta-response (not actual prompts)
        skip_prefixes = (
            "here are",
            "here is",
            "sure",
            "of course",
            "certainly",
            "based on",
            "the following",
            "i'll",
            "let me",
            "below are",
        )

        lines = [line.strip() for line in raw.strip().split("\n") if line.strip()]
        prompts = []
        for line in lines:
            # Remove numbering like "1.", "1)", "1:", etc.
            cleaned = re.sub(r"^\d+[\.\)\:\-]\s*", "", line).strip()
            cleaned = cleaned.strip('"').strip("'")
            # Skip meta-response lines
            if cleaned.lower().startswith(skip_prefixes):
                continue
            if cleaned and len(cleaned) > 10:
                prompts.append(cleaned)

        # Pad if fewer than expected
        if len(prompts) < expected and prompts:
            while len(prompts) < expected:
                prompts.append(prompts[-1])

        return prompts[:expected]
