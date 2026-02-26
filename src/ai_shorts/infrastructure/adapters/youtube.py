"""
YouTube Adapter — VideoUploader implementation.

Uploads videos to YouTube using OAuth2 refresh token authentication
via the YouTube Data API v3.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.domain.exceptions import UploadError
from ai_shorts.domain.ports import VideoUploader

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class YouTubeUploader(VideoUploader):
    """Uploads videos to YouTube via the Data API v3.

    Uses OAuth2 refresh token flow — no interactive browser auth needed
    after initial setup.
    """

    def __init__(self, settings: Settings) -> None:
        self._client_id = settings.youtube.client_id
        self._client_secret = settings.youtube.client_secret
        self._refresh_token = settings.youtube.refresh_token
        self._privacy = settings.video.privacy.value

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        scheduled_time: str = "",
    ) -> str:
        """Upload a video to YouTube.

        Args:
            video_path: Path to the video file.
            title: Video title.
            description: Video description.
            tags: SEO tags.
            scheduled_time: Optional ISO 8601 datetime for scheduled publish.

        Returns:
            URL of the published video.

        Raises:
            UploadError: If upload fails.
        """
        if not all([self._client_id, self._client_secret, self._refresh_token]):
            raise UploadError(
                "YouTube OAuth2 credentials not configured. "
                "Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
                "and YOUTUBE_REFRESH_TOKEN in .env"
            )

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as e:
            raise UploadError(
                "google-api-python-client not installed", cause=e
            ) from e

        log.info("📺 Uploading to YouTube: '%s'...", title)

        try:
            creds = Credentials(
                token=None,
                refresh_token=self._refresh_token,
                client_id=self._client_id,
                client_secret=self._client_secret,
                token_uri="https://oauth2.googleapis.com/token",
            )

            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": f"{description}\n\n{' '.join(f'#{t}' for t in tags[:10])}"[:5000],
                    "tags": tags[:30],
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": "private" if scheduled_time else self._privacy,
                    "selfDeclaredMadeForKids": False,
                    "shorts": {"shortsEligibility": "SHORTS_ELIGIBLE"},
                },
            }

            # Add scheduled publish time if provided
            if scheduled_time:
                body["status"]["publishAt"] = scheduled_time
                log.info("📅 Scheduled for: %s", scheduled_time)

            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=10 * 1024 * 1024,
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            # Resumable upload with progress
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    log.info("   Upload %d%% complete", pct)

            video_id = response.get("id", "")
            url = f"https://youtube.com/shorts/{video_id}"

            log.info("✅ Uploaded to YouTube: %s", url)
            return url

        except Exception as e:
            raise UploadError(f"YouTube upload failed: {e}", cause=e) from e
