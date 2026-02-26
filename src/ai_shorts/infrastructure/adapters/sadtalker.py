"""
SadTalker Adapter — AvatarAnimator implementation.

Generates talking-head videos from a still face image + audio
using the SadTalker model. Includes GPU memory management and
a Ken Burns fallback for when GPU isn't available.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.core.gpu import free_gpu_memory
from ai_shorts.domain.entities import VideoAsset
from ai_shorts.domain.exceptions import AvatarAnimationError
from ai_shorts.domain.ports import AvatarAnimator
from ai_shorts.domain.value_objects import AssetType

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class SadTalkerAnimator(AvatarAnimator):
    """Generates talking-head videos using SadTalker.

    Takes a still face image and audio file, producing a realistic
    lip-synced video. Falls back to Ken Burns zoom effect on failure.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sadtalker_dir = settings.gpu.sadtalker_dir
        self._enable_enhancer = settings.video.enable_face_enhancement
        self._output_dir = str(settings.output_dir)

    def animate(
        self, audio_path: Path, image_path: Path, output_path: Path
    ) -> VideoAsset:
        """Generate a talking-head video.

        Args:
            audio_path: Path to driving audio.
            image_path: Path to source face image.
            output_path: Where to save the output video.

        Returns:
            VideoAsset for the generated video.

        Raises:
            AvatarAnimationError: If both SadTalker and fallback fail.
        """
        log.info("🗣️  Generating talking avatar with SadTalker...")

        # Ensure numpy compatibility
        self._patch_numpy()

        # Install missing dependencies
        self._ensure_dependencies()

        if not os.path.exists(self._sadtalker_dir):
            raise AvatarAnimationError(
                f"SadTalker not found at {self._sadtalker_dir}. "
                "Clone it first or set SADTALKER_DIR in .env"
            )

        # Build inference command
        enhancer_flag = (
            ["--enhancer", "gfpgan"] if self._enable_enhancer else []
        )

        cmd = [
            sys.executable,
            f"{self._sadtalker_dir}/inference.py",
            "--driven_audio", str(audio_path),
            "--source_image", str(image_path),
            "--result_dir", self._output_dir,
            "--still",
            "--preprocess", "crop",
        ] + enhancer_flag

        log.info("   Command: %s", " ".join(cmd[:6]) + "...")
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=self._sadtalker_dir
        )

        if result.returncode != 0:
            log.warning("⚠️  SadTalker failed, attempting Ken Burns fallback...")
            log.debug("STDERR: %s", result.stderr[-500:] if result.stderr else "")
            return self._ken_burns_fallback(audio_path, image_path, output_path)

        # Find the generated video
        generated = sorted(
            glob.glob(f"{self._output_dir}/**/*.mp4", recursive=True),
            key=os.path.getmtime,
            reverse=True,
        )

        if not generated:
            log.warning("⚠️  SadTalker produced no output, using Ken Burns fallback")
            return self._ken_burns_fallback(audio_path, image_path, output_path)

        shutil.move(generated[0], str(output_path))
        log.info("✅ Talking avatar video generated: %s", output_path)
        free_gpu_memory()

        return VideoAsset(
            path=output_path,
            asset_type=AssetType.AVATAR_VIDEO,
        )

    def _ken_burns_fallback(
        self, audio_path: Path, image_path: Path, output_path: Path
    ) -> VideoAsset:
        """Create a slow zoom video from a still image as fallback.

        Args:
            audio_path: Path to audio file.
            image_path: Path to face image.
            output_path: Where to save the video.

        Returns:
            VideoAsset for the fallback video.
        """
        log.info("🖼️  Creating Ken Burns zoom effect as fallback...")
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-vf", "zoompan=z='min(zoom+0.001,1.3)':d=1:s=512x512:fps=30",
            "-shortest",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise AvatarAnimationError(
                f"Both SadTalker and Ken Burns fallback failed: {result.stderr[-300:]}"
            )

        log.info("✅ Ken Burns fallback video created: %s", output_path)
        return VideoAsset(path=output_path, asset_type=AssetType.AVATAR_VIDEO)

    @staticmethod
    def _patch_numpy() -> None:
        """Patch numpy for SadTalker compatibility (numpy 2.0+)."""
        try:
            import numpy as np

            if not hasattr(np, "VisibleDeprecationWarning"):
                np.VisibleDeprecationWarning = DeprecationWarning  # type: ignore[attr-defined]
        except ImportError:
            pass

    @staticmethod
    def _ensure_dependencies() -> None:
        """Install missing SadTalker dependencies."""
        deps = ["kornia", "facexlib", "gfpgan", "basicsr", "dlib"]
        missing = []
        for pkg in deps:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)

        if missing:
            log.info("📦 Installing missing SadTalker deps: %s", ", ".join(missing))
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q"] + missing,
                capture_output=True,
                text=True,
            )
