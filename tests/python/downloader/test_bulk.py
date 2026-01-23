"""Unit tests for bulk map downloader."""

import json
import tempfile
from pathlib import Path
from unittest import mock

from faf.downloader.bulk import (
    BulkDownloader,
    Checkpoint,
    DownloadProgress,
    CHECKPOINT_FILENAME,
    FAILURES_FILENAME,
)
from faf.downloader.maps import MapInfo


def create_mock_map_info(name: str, root_dir: Path) -> MapInfo:
    """Create a mock MapInfo for testing."""
    map_dir = root_dir / f"{name}.v0001"
    map_dir.mkdir(parents=True, exist_ok=True)
    scmap_path = map_dir / f"{name}.scmap"
    scmap_path.write_bytes(b"fake scmap")

    return MapInfo(
        name=name,
        version="v0001",
        root_dir=map_dir,
        scmap_path=scmap_path,
        scenario_path=map_dir / f"{name}_scenario.lua",
        save_path=map_dir / f"{name}_save.lua",
        script_path=map_dir / f"{name}_script.lua",
    )


class TestBulkDownloaderCheckpointing:
    """Tests for checkpoint functionality."""

    def test_bulk_download_creates_checkpoint(self) -> None:
        """Should create checkpoint.json after successful downloads."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch.object(BulkDownloader, "_download_single") as mock_download:
                mock_download.return_value = create_mock_map_info("test_map", output_dir)

                downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
                downloader.download_from_urls(
                    ["https://example.com/map1.zip", "https://example.com/map2.zip"]
                )

            checkpoint_path = output_dir / CHECKPOINT_FILENAME
            assert checkpoint_path.exists()

            with open(checkpoint_path) as f:
                checkpoint_data = json.load(f)

            assert "completed_urls" in checkpoint_data
            assert len(checkpoint_data["completed_urls"]) == 2

    def test_bulk_download_resumes_from_checkpoint(self) -> None:
        """Should skip URLs already in checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            checkpoint_data = {
                "completed_urls": ["https://example.com/map1.zip"],
                "timestamp": "2025-01-01T00:00:00Z",
            }
            checkpoint_path = output_dir / CHECKPOINT_FILENAME
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint_data, f)

            with mock.patch.object(BulkDownloader, "_download_single") as mock_download:
                mock_download.return_value = create_mock_map_info("test_map", output_dir)

                downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
                progress = downloader.download_from_urls(
                    ["https://example.com/map1.zip", "https://example.com/map2.zip"],
                    resume=True,
                )

            assert progress.skipped == 1
            assert progress.completed == 1
            assert mock_download.call_count == 1


class TestBulkDownloaderFailureLogging:
    """Tests for failure logging functionality."""

    def test_bulk_download_logs_failures(self) -> None:
        """Should log failed downloads to failures.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch.object(BulkDownloader, "_download_single") as mock_download:
                mock_download.side_effect = Exception("Download failed")

                downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
                progress = downloader.download_from_urls(["https://example.com/broken.zip"])

            assert progress.failed == 1

            failures_path = output_dir / FAILURES_FILENAME
            assert failures_path.exists()


class TestBulkDownloaderLimits:
    """Tests for limit and concurrency options."""

    def test_bulk_download_respects_limit(self) -> None:
        """Should only download up to limit maps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch.object(BulkDownloader, "_download_single") as mock_download:
                mock_download.return_value = create_mock_map_info("test_map", output_dir)

                downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
                progress = downloader.download_from_urls(
                    [f"https://example.com/map{i}.zip" for i in range(10)],
                    limit=3,
                )

            assert progress.total == 3
            assert mock_download.call_count == 3

    def test_bulk_download_respects_concurrency(self) -> None:
        """Should use specified number of concurrent downloads."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Mock as_completed to return completed futures immediately
            with mock.patch("faf.downloader.bulk.ThreadPoolExecutor") as MockExecutor:
                with mock.patch("faf.downloader.bulk.as_completed") as mock_as_completed:
                    mock_executor = mock.MagicMock()
                    MockExecutor.return_value.__enter__.return_value = mock_executor

                    # Create a mock future that returns a result
                    mock_future = mock.MagicMock()
                    mock_future.result.return_value = create_mock_map_info("test", output_dir)
                    mock_executor.submit.return_value = mock_future

                    # Make as_completed yield our mock future
                    mock_as_completed.return_value = iter([mock_future])

                    downloader = BulkDownloader(output_dir=output_dir, concurrency=8)
                    downloader.download_from_urls(["https://example.com/map.zip"])

                    MockExecutor.assert_called_once_with(max_workers=8)


class TestBulkDownloaderFileReading:
    """Tests for reading URLs from files."""

    def test_bulk_download_reads_from_file(self) -> None:
        """Should read URLs from specified file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            url_file = output_dir / "urls.txt"

            urls = [
                "https://example.com/map1.zip",
                "https://example.com/map2.zip",
                "https://example.com/map3.zip",
            ]
            url_file.write_text("\n".join(urls))

            with mock.patch.object(BulkDownloader, "_download_single") as mock_download:
                mock_download.return_value = create_mock_map_info("test_map", output_dir)

                downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
                progress = downloader.download_from_file(url_file)

            assert progress.total == 3
            assert mock_download.call_count == 3

    def test_bulk_download_skips_comments_in_url_file(self) -> None:
        """Should skip lines starting with # in URL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            url_file = output_dir / "urls.txt"

            content = """# This is a comment
https://example.com/map1.zip
# Another comment
https://example.com/map2.zip

# Empty lines above should be skipped too
https://example.com/map3.zip
"""
            url_file.write_text(content)

            with mock.patch.object(BulkDownloader, "_download_single") as mock_download:
                mock_download.return_value = create_mock_map_info("test_map", output_dir)

                downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
                progress = downloader.download_from_file(url_file)

            assert progress.total == 3

    def test_bulk_download_falls_back_to_seed_file(self) -> None:
        """Should use seed file when download_from_seed_file is called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch.object(BulkDownloader, "_read_urls_from_file") as mock_read:
                mock_read.return_value = iter(["https://example.com/map.zip"])

                with mock.patch.object(BulkDownloader, "_download_single") as mock_download:
                    mock_download.return_value = create_mock_map_info("test", output_dir)

                    with mock.patch("faf.downloader.bulk.SEED_URLS_PATH") as mock_path:
                        mock_path.exists.return_value = True

                        downloader = BulkDownloader(output_dir=output_dir, concurrency=1)
                        progress = downloader.download_from_seed_file(limit=1)

                assert progress.total == 1


class TestDownloadProgress:
    """Tests for DownloadProgress dataclass."""

    def test_remaining_calculation(self) -> None:
        """Should correctly calculate remaining downloads."""
        progress = DownloadProgress(total=10, completed=3, failed=2, skipped=1)
        assert progress.remaining == 4


class TestCheckpoint:
    """Tests for Checkpoint dataclass."""

    def test_checkpoint_to_dict(self) -> None:
        """Should convert checkpoint to dictionary."""
        checkpoint = Checkpoint(
            completed_urls={"url1", "url2"},
            timestamp="2025-01-01T00:00:00Z",
            source_file="test.txt",
        )
        data = checkpoint.to_dict()

        assert set(data["completed_urls"]) == {"url1", "url2"}
        assert data["timestamp"] == "2025-01-01T00:00:00Z"
        assert data["source_file"] == "test.txt"

    def test_checkpoint_from_dict(self) -> None:
        """Should create checkpoint from dictionary."""
        data = {
            "completed_urls": ["url1", "url2"],
            "timestamp": "2025-01-01T00:00:00Z",
            "source_file": "test.txt",
        }
        checkpoint = Checkpoint.from_dict(data)

        assert checkpoint.completed_urls == {"url1", "url2"}
        assert checkpoint.timestamp == "2025-01-01T00:00:00Z"
        assert checkpoint.source_file == "test.txt"
