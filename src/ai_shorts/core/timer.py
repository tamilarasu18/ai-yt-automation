"""
Pipeline Timer — tracks elapsed time for each pipeline step.

Provides timing instrumentation for performance monitoring and
debugging. Produces a formatted summary at pipeline completion.

Usage:
    timer = PipelineTimer()
    with timer.step("Story Generation"):
        generate_story(...)
    timer.summary()
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class StepTiming:
    """Timing record for a single pipeline step."""

    name: str
    elapsed_seconds: float


@dataclass
class PipelineTimer:
    """Tracks elapsed time for each pipeline step.

    Supports both explicit start/end and context manager usage.
    """

    _start: float = field(default_factory=time.time, init=False, repr=False)
    _step_start: float | None = field(default=None, init=False, repr=False)
    _current_step: str = field(default="", init=False, repr=False)
    steps: list[StepTiming] = field(default_factory=list, init=False)

    @contextmanager
    def step(self, name: str) -> Generator[None, None, None]:
        """Time a pipeline step using a context manager.

        Args:
            name: Display name for the step.
        """
        self.start_step(name)
        try:
            yield
        finally:
            self.end_step()

    def start_step(self, name: str) -> None:
        """Start timing a step.

        Args:
            name: Display name for the step.
        """
        self._step_start = time.time()
        self._current_step = name
        log.info("⏱️  Starting: %s", name)

    def end_step(self) -> float:
        """End timing the current step.

        Returns:
            Elapsed time in seconds.
        """
        if self._step_start is None:
            return 0.0

        elapsed = time.time() - self._step_start
        self.steps.append(StepTiming(name=self._current_step, elapsed_seconds=elapsed))
        log.info("⏱️  %s completed in %.1fs", self._current_step, elapsed)
        self._step_start = None
        return elapsed

    def summary(self) -> float:
        """Log a formatted timing summary.

        Returns:
            Total elapsed time in seconds.
        """
        total = time.time() - self._start
        log.info("=" * 50)
        log.info("⏱️  TIMING SUMMARY")
        log.info("=" * 50)
        for s in self.steps:
            log.info("  %-35s %6.1fs", s.name, s.elapsed_seconds)
        log.info("  %-35s %6.1fs", "TOTAL", total)
        log.info("=" * 50)
        return total

    @property
    def total_elapsed(self) -> float:
        """Total elapsed time since timer creation."""
        return time.time() - self._start
