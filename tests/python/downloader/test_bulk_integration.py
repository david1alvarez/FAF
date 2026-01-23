"""Integration tests for bulk map downloader (requires network access).

These tests download real maps from the FAF content server.
Run with: pytest tests/python/downloader/test_bulk_integration.py -v -m integration
"""

import tempfile
from pathlib import Path

import pytest

from faf.downloader.bulk import BulkDownloader, CHECKPOINT_FILENAME

pytestmark = pytest.mark.integration


class TestBulkDownloaderIntegration:
    """Integration tests that download real maps."""

    def test_bulk_download_real_maps(self) -> None:
        """Should successfully download a small batch of real maps."""
        urls = [
            "https://content.faforever.com/maps/theta_passage_5.v0001.zip",
            "https://content.faforever.com/maps/canis_river.v0001.zip",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            downloader = BulkDownloader(output_dir=output_dir, concurrency=2)
            progress = downloader.download_from_urls(urls)

            assert progress.completed >= 1
            assert progress.total == 2

            checkpoint_path = output_dir / CHECKPOINT_FILENAME
            assert checkpoint_path.exists()

            scmap_files = list(output_dir.glob("**/*.scmap"))
            assert len(scmap_files) >= 1

    def test_bulk_download_handles_missing_map(self) -> None:
        """Should continue downloading when some maps fail."""
        urls = [
            "https://content.faforever.com/maps/theta_passage_5.v0001.zip",
            "https://content.faforever.com/maps/nonexistent_map_12345.zip",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            downloader = BulkDownloader(output_dir=output_dir, concurrency=2)
            progress = downloader.download_from_urls(urls)

            assert progress.completed == 1
            assert progress.failed == 1
            assert progress.total == 2

    def test_bulk_download_resumes_correctly(self) -> None:
        """Should skip already downloaded maps on resume."""
        urls = [
            "https://content.faforever.com/maps/theta_passage_5.v0001.zip",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
            progress1 = downloader.download_from_urls(urls)

            assert progress1.completed == 1

            progress2 = downloader.download_from_urls(urls, resume=True)

            assert progress2.skipped == 1
            assert progress2.completed == 0
