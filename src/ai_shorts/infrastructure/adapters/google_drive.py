"""
Google Drive Adapter — StorageService implementation.

Copies generated videos to Google Drive for persistent storage
and easy sharing.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ai_shorts.domain.ports import StorageService

if TYPE_CHECKING:
    from ai_shorts.core.config import Settings

log = logging.getLogger(__name__)


class GoogleDriveStorage(StorageService):
    """Persistent file storage via Google Drive.

    Copies files to a mounted Drive folder with timestamped filenames.
    Expects Drive to be mounted at /content/drive (Colab default).
    """

    def __init__(self, settings: Settings) -> None:
        self._output_folder = settings.drive_output_folder

    def save(self, local_path: Path) -> str:
        """Copy a file to Google Drive.

        Args:
            local_path: Path to the local file.

        Returns:
            Path to the file in Drive.
        """
        if not self._output_folder:
            log.warning("⚠️  Drive output folder not configured, skipping save")
            return ""

        output_dir = Path(self._output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        ext = local_path.suffix
        dest = output_dir / f"short_{timestamp}{ext}"

        shutil.copy(str(local_path), str(dest))
        log.info("💾 Saved to Drive: %s", dest)

        return str(dest)
