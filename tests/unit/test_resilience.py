"""Tests for resilience utilities."""

from __future__ import annotations

import pytest

from ai_shorts.core.resilience import retry_with_backoff


class TestRetryWithBackoff:
    """Tests for the retry decorator."""

    def test_success_on_first_try(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def always_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()
        assert result == "success"
        assert call_count == 1

    def test_success_after_retry(self) -> None:
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def fails_then_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "recovered"

        result = fails_then_succeeds()
        assert result == "recovered"
        assert call_count == 3

    def test_max_retries_exceeded(self) -> None:
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails() -> str:
            raise ValueError("Permanent failure")

        with pytest.raises(ValueError, match="Permanent failure"):
            always_fails()

    def test_specific_exception_types(self) -> None:
        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            exceptions=(ConnectionError,),
        )
        def raises_wrong_type() -> str:
            raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            raises_wrong_type()

    def test_on_retry_callback(self) -> None:
        retries: list[int] = []

        def on_retry(exc: Exception, attempt: int) -> None:
            retries.append(attempt)

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01, on_retry=on_retry)
        def fails_twice() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("fail")
            return "ok"

        fails_twice()
        assert retries == [1, 2]
