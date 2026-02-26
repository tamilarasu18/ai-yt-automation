"""
Google Sheets Adapter — TopicRepository implementation.

Manages the video topic queue stored in a Google Spreadsheet.
Uses service account authentication via gspread.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ai_shorts.core.resilience import retry_with_backoff
from ai_shorts.domain.entities import Topic
from ai_shorts.domain.exceptions import TopicFetchError
from ai_shorts.domain.ports import TopicRepository
from ai_shorts.domain.value_objects import Language, TopicStatus

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class GoogleSheetsTopicRepository(TopicRepository):
    """Fetches and manages topics from a Google Spreadsheet.

    Expected sheet columns: Topic | Language | Status | Video URL

    The service account must have Editor access to the spreadsheet.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def _get_client(self) -> Any:
        """Authenticate and return the gspread client."""
        if self._client is not None:
            return self._client

        import gspread
        from google.oauth2.service_account import Credentials

        sa_file = self._settings.google.service_account_file
        if not sa_file:
            raise TopicFetchError(
                "Google service account file not configured. "
                "Set GOOGLE_SERVICE_ACCOUNT_FILE in .env"
            )

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
        self._client = gspread.authorize(creds)
        return self._client

    def get_next_pending(self) -> Topic | None:
        """Fetch the next topic with 'Pending' status.

        Returns:
            Topic entity, or None if no pending topics.
        """
        try:
            gc = self._get_client()
            sheet_url = self._settings.google.sheet_url
            sheet_name = self._settings.google.sheet_name

            if not sheet_url:
                raise TopicFetchError("Google Sheet URL not configured")

            spreadsheet = gc.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            records = worksheet.get_all_records()

            for i, row in enumerate(records):
                status = str(row.get("Status", "")).strip()
                if status.lower() != "pending":
                    continue

                topic_text = str(row.get("Topic", "")).strip()
                lang_str = str(row.get("Language", "")).strip().lower()

                if not topic_text:
                    continue

                try:
                    language = Language.from_str(lang_str)
                except ValueError:
                    log.warning(
                        "⚠️  Unsupported language '%s' in row %d, skipping",
                        lang_str,
                        i + 2,
                    )
                    continue

                return Topic(
                    text=topic_text,
                    language=language,
                    status=TopicStatus.PENDING,
                    row_index=i + 2,  # +2 for header row + 0-index
                    worksheet_ref=worksheet,
                )

            return None

        except TopicFetchError:
            raise
        except Exception as e:
            raise TopicFetchError(f"Failed to fetch topics: {e}", cause=e) from e

    def update_status(self, topic: Topic) -> None:
        """Update the topic status in the spreadsheet.

        Args:
            topic: Topic with updated status.
        """
        if topic.worksheet_ref is None or topic.row_index is None:
            log.warning("⚠️  Cannot update status: no worksheet reference")
            return

        try:
            topic.worksheet_ref.update_cell(topic.row_index, 3, topic.status.value)
            log.info("📊 Sheet updated: Row %d → %s", topic.row_index, topic.status.value)
        except Exception as e:
            log.warning("⚠️  Failed to update sheet: %s", e)
