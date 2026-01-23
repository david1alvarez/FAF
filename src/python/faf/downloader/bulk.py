"""Bulk map downloader for FAF content server.

This module provides functionality to download multiple maps in parallel with
checkpointing, resume capability, and graceful error handling.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional

from faf.downloader.maps import MapDownloader, MapDownloadError, MapInfo

# Default configuration
DEFAULT_CONCURRENCY = 4
DEFAULT_DOWNLOAD_DELAY = 0.1  # seconds between starting new downloads
CHECKPOINT_FILENAME = "checkpoint.json"
FAILURES_FILENAME = "failures.json"

# Path to seed URLs file (relative to package)
SEED_URLS_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "seed_map_urls.txt"


@dataclass
class DownloadProgress:
    """Progress information for bulk download.

    Attributes:
        total: Total number of maps to download.
        completed: Number of successfully downloaded maps.
        failed: Number of failed downloads.
        skipped: Number of maps skipped (already downloaded).
    """

    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def remaining(self) -> int:
        """Number of maps remaining to download."""
        return self.total - self.completed - self.failed - self.skipped


@dataclass
class DownloadFailure:
    """Information about a failed download.

    Attributes:
        url: The URL that failed to download.
        error: Error message describing the failure.
        timestamp: When the failure occurred.
        map_name: Name extracted from URL if available.
    """

    url: str
    error: str
    timestamp: str
    map_name: Optional[str] = None


@dataclass
class Checkpoint:
    """Checkpoint for resumable bulk downloads.

    Attributes:
        completed_urls: Set of URLs that have been successfully downloaded.
        timestamp: When the checkpoint was last updated.
        source_file: The source file used for URLs, if any.
    """

    completed_urls: set[str] = field(default_factory=set)
    timestamp: Optional[str] = None
    source_file: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert checkpoint to dictionary for JSON serialization."""
        return {
            "completed_urls": list(self.completed_urls),
            "timestamp": self.timestamp,
            "source_file": self.source_file,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        """Create checkpoint from dictionary."""
        return cls(
            completed_urls=set(data.get("completed_urls", [])),
            timestamp=data.get("timestamp"),
            source_file=data.get("source_file"),
        )


class BulkDownloader:
    """Downloads multiple maps in parallel with checkpointing.

    This class handles bulk downloading of maps from the FAF content server,
    with support for parallel downloads, progress checkpointing, and
    graceful error handling.

    Example:
        >>> downloader = BulkDownloader(output_dir=Path("/data/maps"))
        >>> progress = downloader.download_from_file(Path("urls.txt"), limit=100)
        >>> print(f"Downloaded {progress.completed} maps")
    """

    def __init__(
        self,
        output_dir: Path,
        concurrency: int = DEFAULT_CONCURRENCY,
        download_delay: float = DEFAULT_DOWNLOAD_DELAY,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
    ) -> None:
        """Initialize the bulk downloader.

        Args:
            output_dir: Directory to download maps to.
            concurrency: Maximum number of parallel downloads.
            download_delay: Delay in seconds between starting downloads.
            progress_callback: Optional callback for progress updates.
        """
        self.output_dir = output_dir
        self.concurrency = concurrency
        self.download_delay = download_delay
        self.progress_callback = progress_callback
        self._map_downloader = MapDownloader()
        self._checkpoint_lock = threading.Lock()
        self._failures_lock = threading.Lock()

    def download_from_file(
        self,
        url_file: Path,
        limit: Optional[int] = None,
        resume: bool = True,
    ) -> DownloadProgress:
        """Download maps from a file containing URLs.

        Args:
            url_file: Path to file containing map URLs (one per line).
            limit: Maximum number of maps to download (None for all).
            resume: Whether to resume from checkpoint if available.

        Returns:
            DownloadProgress with final statistics.

        Raises:
            FileNotFoundError: If url_file doesn't exist.
        """
        urls = list(self._read_urls_from_file(url_file))
        return self._download_urls(urls, limit=limit, resume=resume, source_file=str(url_file))

    def download_from_urls(
        self,
        urls: list[str],
        limit: Optional[int] = None,
        resume: bool = True,
    ) -> DownloadProgress:
        """Download maps from a list of URLs.

        Args:
            urls: List of map URLs to download.
            limit: Maximum number of maps to download (None for all).
            resume: Whether to resume from checkpoint if available.

        Returns:
            DownloadProgress with final statistics.
        """
        return self._download_urls(urls, limit=limit, resume=resume)

    def download_from_seed_file(
        self,
        limit: Optional[int] = None,
        resume: bool = True,
    ) -> DownloadProgress:
        """Download maps from the built-in seed URL file.

        This is a fallback method for when the FAF API is not accessible.

        Args:
            limit: Maximum number of maps to download (None for all).
            resume: Whether to resume from checkpoint if available.

        Returns:
            DownloadProgress with final statistics.

        Raises:
            FileNotFoundError: If seed file doesn't exist.
        """
        if not SEED_URLS_PATH.exists():
            raise FileNotFoundError(f"Seed URL file not found: {SEED_URLS_PATH}")

        return self.download_from_file(SEED_URLS_PATH, limit=limit, resume=resume)

    def _download_urls(
        self,
        urls: list[str],
        limit: Optional[int] = None,
        resume: bool = True,
        source_file: Optional[str] = None,
    ) -> DownloadProgress:
        """Internal method to download maps from URLs.

        Args:
            urls: List of URLs to download.
            limit: Maximum number to download.
            resume: Whether to use checkpointing.
            source_file: Source file path for checkpoint tracking.

        Returns:
            DownloadProgress with final statistics.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = self._load_checkpoint() if resume else Checkpoint()
        failures = self._load_failures() if resume else []

        if limit is not None:
            urls = urls[:limit]

        progress = DownloadProgress(total=len(urls))

        urls_to_download = []
        for url in urls:
            if url in checkpoint.completed_urls:
                progress.skipped += 1
            else:
                urls_to_download.append(url)

        if self.progress_callback:
            self.progress_callback(progress)

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_url = {}
            for i, url in enumerate(urls_to_download):
                if i > 0:
                    time.sleep(self.download_delay)
                future = executor.submit(self._download_single, url)
                future_to_url[future] = url

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result is not None:
                        progress.completed += 1
                        with self._checkpoint_lock:
                            checkpoint.completed_urls.add(url)
                            checkpoint.timestamp = datetime.now(timezone.utc).isoformat()
                            checkpoint.source_file = source_file
                            self._save_checkpoint(checkpoint)
                    else:
                        progress.failed += 1
                except Exception as e:
                    progress.failed += 1
                    failure = DownloadFailure(
                        url=url,
                        error=str(e),
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        map_name=self._extract_map_name(url),
                    )
                    with self._failures_lock:
                        failures.append(failure)
                        self._save_failures(failures)

                if self.progress_callback:
                    self.progress_callback(progress)

        return progress

    def _download_single(self, url: str) -> Optional[MapInfo]:
        """Download a single map.

        Args:
            url: URL of the map to download.

        Returns:
            MapInfo if successful, None if failed.
        """
        try:
            return self._map_downloader.download(url, output_dir=self.output_dir)
        except MapDownloadError as e:
            failure = DownloadFailure(
                url=url,
                error=str(e),
                timestamp=datetime.now(timezone.utc).isoformat(),
                map_name=self._extract_map_name(url),
            )
            with self._failures_lock:
                failures = self._load_failures()
                failures.append(failure)
                self._save_failures(failures)
            return None

    def _read_urls_from_file(self, path: Path) -> Iterator[str]:
        """Read URLs from a file, skipping comments and empty lines.

        Args:
            path: Path to the URL file.

        Yields:
            Valid URLs from the file.
        """
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    yield line

    def _load_checkpoint(self) -> Checkpoint:
        """Load checkpoint from file."""
        checkpoint_path = self.output_dir / CHECKPOINT_FILENAME
        if checkpoint_path.exists():
            try:
                with open(checkpoint_path) as f:
                    data = json.load(f)
                return Checkpoint.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return Checkpoint()

    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to file."""
        checkpoint_path = self.output_dir / CHECKPOINT_FILENAME
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

    def _load_failures(self) -> list[DownloadFailure]:
        """Load failures from file."""
        failures_path = self.output_dir / FAILURES_FILENAME
        if failures_path.exists():
            try:
                with open(failures_path) as f:
                    data = json.load(f)
                return [
                    DownloadFailure(
                        url=item.get("url", ""),
                        error=item.get("error", ""),
                        timestamp=item.get("timestamp", ""),
                        map_name=item.get("map_name"),
                    )
                    for item in data
                ]
            except (json.JSONDecodeError, KeyError):
                pass
        return []

    def _save_failures(self, failures: list[DownloadFailure]) -> None:
        """Save failures to file."""
        failures_path = self.output_dir / FAILURES_FILENAME
        data = [
            {
                "url": f.url,
                "error": f.error,
                "timestamp": f.timestamp,
                "map_name": f.map_name,
            }
            for f in failures
        ]
        with open(failures_path, "w") as f:
            json.dump(data, f, indent=2)

    def _extract_map_name(self, url: str) -> Optional[str]:
        """Extract map name from URL.

        Args:
            url: Map download URL.

        Returns:
            Map name extracted from URL, or None.
        """
        try:
            filename = url.split("/")[-1]
            if filename.endswith(".zip"):
                return filename[:-4]
            return filename
        except Exception:
            return None
