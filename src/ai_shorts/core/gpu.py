"""
GPU Memory Manager — lifecycle management for GPU resources.

Provides utilities for monitoring, clearing, and safely managing
GPU memory across pipeline stages that compete for VRAM.

Usage:
    with gpu_context("SadTalker inference"):
        run_sadtalker(...)
    # GPU memory is automatically freed after the block
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GPUInfo:
    """GPU device information."""

    name: str
    total_gb: float
    available: bool = True


def get_gpu_info() -> GPUInfo | None:
    """Detect and return GPU information.

    Returns:
        GPUInfo if a CUDA GPU is available, else None.
    """
    try:
        import torch

        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            info = GPUInfo(name=name, total_gb=round(total, 1))
            log.info("🖥️  GPU: %s (%.1fGB)", info.name, info.total_gb)
            return info
        else:
            log.warning("⚠️  No GPU detected. GPU-dependent steps will be slow or fail.")
            return None
    except ImportError:
        log.warning("⚠️  PyTorch not installed — GPU info unavailable")
        return None


def free_gpu_memory() -> None:
    """Release GPU memory and clear CUDA cache.

    Call this between GPU-intensive pipeline stages to prevent OOM errors.
    """
    try:
        import gc

        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            allocated = torch.cuda.memory_allocated() / (1024**3)
            reserved = torch.cuda.memory_reserved() / (1024**3)
            log.info(
                "🧹 GPU memory: %.1fGB allocated, %.1fGB reserved",
                allocated,
                reserved,
            )
    except ImportError:
        pass


@contextmanager
def gpu_context(stage_name: str) -> Generator[None, None, None]:
    """Context manager that frees GPU memory on exit.

    Args:
        stage_name: Name of the pipeline stage (for logging).

    Usage:
        with gpu_context("SadTalker"):
            generate_avatar_video(...)
    """
    log.info("🔒 GPU acquired for: %s", stage_name)
    try:
        yield
    finally:
        log.info("🔓 Releasing GPU from: %s", stage_name)
        free_gpu_memory()
