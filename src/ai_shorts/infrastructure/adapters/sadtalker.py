"""
SadTalker Adapter — AvatarAnimator implementation.

Generates talking-head videos from a still face image + audio
using the SadTalker model. Includes GPU memory management,
comprehensive numpy 2.0 / torchvision compatibility patching,
and a Ken Burns fallback for when GPU isn't available.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import site
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

    Before running inference, applies comprehensive compatibility patches
    for numpy 2.0+, torchvision, and basicsr — ported from the battle-tested
    Colab setup in SADTALKER_GUIDE.md.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sadtalker_dir = settings.gpu.sadtalker_dir
        self._enable_enhancer = settings.video.enable_face_enhancement
        self._output_dir = str(settings.output_dir)
        self._patched = False  # Track whether patches have been applied this session

    def animate(self, audio_path: Path, image_path: Path, output_path: Path) -> VideoAsset:
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

        if not os.path.exists(self._sadtalker_dir):
            raise AvatarAnimationError(
                f"SadTalker not found at {self._sadtalker_dir}. "
                "Clone it first or set SADTALKER_DIR in .env"
            )

        # Apply all compatibility patches (idempotent — only runs once per session)
        if not self._patched:
            self._patch_numpy_runtime()
            self._ensure_dependencies()
            self._patch_sadtalker_numpy_compat()
            self._patch_basicsr_torchvision()
            self._patch_preprocess_array()
            self._ensure_checkpoints()
            self._patched = True

        # Build inference command
        enhancer_flag = ["--enhancer", "gfpgan"] if self._enable_enhancer else []

        cmd = [
            sys.executable,
            f"{self._sadtalker_dir}/inference.py",
            "--driven_audio",
            str(audio_path),
            "--source_image",
            str(image_path),
            "--result_dir",
            self._output_dir,
            "--preprocess",
            "crop",
            "--size",
            "256",
            "--expression_scale",
            "1.2",
        ] + enhancer_flag

        log.info("   Command: %s", " ".join(cmd[:6]) + "...")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=self._sadtalker_dir, timeout=600,  # 10-minute timeout
            )
        except subprocess.TimeoutExpired:
            log.warning(
                "⚠️  SadTalker timed out after 10 minutes, using Ken Burns fallback..."
            )
            return self._ken_burns_fallback(audio_path, image_path, output_path)

        if result.returncode != 0:
            log.warning(
                "⚠️  SadTalker failed (exit code %d), attempting Ken Burns fallback...",
                result.returncode,
            )
            log.warning(
                "STDOUT (last 1000 chars): %s",
                result.stdout[-1000:] if result.stdout else "(empty)",
            )
            log.warning(
                "STDERR (last 1000 chars): %s",
                result.stderr[-1000:] if result.stderr else "(empty)",
            )
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
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "zoompan=z='min(zoom+0.001,1.3)':d=1:s=512x512:fps=30",
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

    # ─── Compatibility Patches (ported from SADTALKER_GUIDE.md) ───

    @staticmethod
    def _patch_numpy_runtime() -> None:
        """Patch numpy at runtime for SadTalker compatibility (numpy 2.0+)."""
        try:
            import numpy as np

            if not hasattr(np, "VisibleDeprecationWarning"):
                np.VisibleDeprecationWarning = DeprecationWarning  # type: ignore[attr-defined]
        except ImportError:
            pass

    def _patch_sadtalker_numpy_compat(self) -> None:
        """Walk ALL .py files in SadTalker dir and fix deprecated numpy aliases.

        numpy 2.0 removed np.float, np.int, np.bool, np.complex, np.object, np.str.
        This patches them to their Python built-in equivalents.
        """
        log.info("🔧 Patching numpy 2.0 compatibility in SadTalker source...")
        patched_count = 0

        for root, _dirs, files in os.walk(self._sadtalker_dir):
            # Skip .git directory
            if ".git" in root:
                continue
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    original = content

                    # np.float → float (but NOT np.float32, np.float64, etc.)
                    content = content.replace("np.float)", "float)")
                    content = content.replace("np.float,", "float,")
                    content = content.replace("np.float]", "float]")
                    content = content.replace("np.float\n", "float\n")
                    content = content.replace("dtype=np.float", "dtype=np.float64")

                    # np.int → int (but NOT np.int32, np.int64, etc.)
                    content = re.sub(r"np\.int([^0-9e_a-zA-Z])", r"int\1", content)

                    # np.bool → bool (but NOT np.bool_)
                    content = re.sub(r"np\.bool([^_a-zA-Z0-9])", r"bool\1", content)

                    # np.complex → complex (but NOT np.complex64, etc.)
                    content = re.sub(r"np\.complex([^0-9_a-zA-Z])", r"complex\1", content)

                    # np.object → object
                    content = re.sub(r"np\.object([^_a-zA-Z0-9])", r"object\1", content)

                    # np.str → str
                    content = re.sub(r"np\.str([^_a-zA-Z0-9])", r"str\1", content)

                    # np.VisibleDeprecationWarning → DeprecationWarning
                    content = content.replace("np.VisibleDeprecationWarning", "DeprecationWarning")

                    if content != original:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write(content)
                        patched_count += 1
                except Exception:
                    pass

        log.info("✅ Patched %d SadTalker source files for numpy 2.0 compat", patched_count)

    @staticmethod
    def _patch_basicsr_torchvision() -> None:
        """Fix basicsr importing removed torchvision.transforms.functional_tensor.

        In newer torchvision versions, functional_tensor was merged into functional.
        """
        try:
            sp = site.getsitepackages()[0]
        except Exception:
            return

        patch_files = [
            os.path.join(sp, "basicsr", "data", "degradations.py"),
            os.path.join(sp, "basicsr", "data", "transforms.py"),
        ]

        patched = False
        for patch_file in patch_files:
            if not os.path.exists(patch_file):
                continue
            try:
                with open(patch_file, encoding="utf-8") as f:
                    content = f.read()
                original = content
                content = content.replace(
                    "from torchvision.transforms.functional_tensor import",
                    "from torchvision.transforms.functional import",
                )
                if content != original:
                    with open(patch_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    patched = True
            except Exception:
                pass

        if patched:
            log.info("✅ Patched basicsr torchvision compatibility")

    def _patch_preprocess_array(self) -> None:
        """Fix numpy 2.0 inhomogeneous array error in preprocess.py.

        The line: trans_params = np.array([w0, h0, s, t[0], t[1]])
        fails because t[0] and t[1] are arrays, not scalars. Fix: convert to float.
        """
        preprocess_file = os.path.join(
            self._sadtalker_dir, "src", "face3d", "util", "preprocess.py"
        )
        if not os.path.exists(preprocess_file):
            return

        try:
            with open(preprocess_file, encoding="utf-8") as f:
                content = f.read()

            old = "trans_params = np.array([w0, h0, s, t[0], t[1]])"
            new = "trans_params = np.array([w0, h0, s, float(t[0]), float(t[1])])"

            if old in content:
                content = content.replace(old, new)
                with open(preprocess_file, "w", encoding="utf-8") as f:
                    f.write(content)
                log.info("✅ Patched preprocess.py inhomogeneous array fix")
        except Exception:
            pass

    def _ensure_checkpoints(self) -> None:
        """Check and download SadTalker model checkpoints if missing."""
        checkpoints_dir = os.path.join(self._sadtalker_dir, "checkpoints")
        if os.path.exists(checkpoints_dir) and len(os.listdir(checkpoints_dir)) >= 3:
            log.info("✅ SadTalker checkpoints found (%d files)", len(os.listdir(checkpoints_dir)))
            return

        download_script = os.path.join(self._sadtalker_dir, "scripts", "download_models.sh")
        if not os.path.exists(download_script):
            log.warning("⚠️  SadTalker download script not found, skipping checkpoint check")
            return

        log.info("📥 Downloading SadTalker model checkpoints...")
        result = subprocess.run(
            ["bash", download_script],
            capture_output=True,
            text=True,
            cwd=self._sadtalker_dir,
        )
        if result.returncode == 0:
            log.info("✅ SadTalker checkpoints downloaded")
        else:
            log.warning(
                "⚠️  Checkpoint download may have failed: %s",
                result.stderr[-300:] if result.stderr else "",
            )

    @staticmethod
    def _ensure_dependencies() -> None:
        """Install missing SadTalker dependencies.

        dlib is separated because it requires CMake + C++ compiler
        and may fail on systems without build tools.
        """
        pip_deps = ["kornia", "facexlib", "gfpgan", "basicsr"]
        missing = []
        for pkg in pip_deps:
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

        # dlib requires CMake + C++ compiler — install separately with warning
        try:
            __import__("dlib")
        except ImportError:
            log.info("📦 Installing dlib (requires CMake + C++ compiler)...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "dlib"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                log.warning(
                    "⚠️  dlib installation failed. Install CMake and a C++ compiler, "
                    "then run: pip install dlib\n   Error: %s",
                    result.stderr[-300:] if result.stderr else "(unknown)",
                )
