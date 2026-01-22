"""Integration tests for map downloader (requires network access).

These tests download real maps from the FAF content server.
Run with: pytest tests/python/downloader/test_maps_integration.py -v -m integration
"""

import tempfile
from pathlib import Path

import pytest

from faf.downloader.maps import MapDownloader, MapDownloadError

pytestmark = pytest.mark.integration


class TestMapDownloaderIntegration:
    """Integration tests that download real maps from FAF."""

    def test_download_real_map_from_url(self) -> None:
        """Should successfully download and extract a real map.

        Uses theta_passage_5.v0001 as it's a small, stable map.
        """
        downloader = MapDownloader()
        url = "https://content.faforever.com/maps/theta_passage_5.v0001.zip"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            info = downloader.download(url, output_dir=output_dir)

            assert info.root_dir.exists()
            assert info.scmap_path.exists()
            assert info.scmap_path.suffix == ".scmap"
            assert info.scenario_path.exists()
            assert info.root_dir.name == "theta_passage_5.v0001"

            scmap_size = info.scmap_path.stat().st_size
            assert scmap_size > 1000, f"SCMAP file too small: {scmap_size} bytes"

    def test_download_nonexistent_map_returns_error(self) -> None:
        """Should raise MapDownloadError for nonexistent map URL."""
        downloader = MapDownloader()
        url = "https://content.faforever.com/maps/this_map_does_not_exist_12345.zip"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with pytest.raises(MapDownloadError) as exc_info:
                downloader.download(url, output_dir=output_dir)

            assert exc_info.value.status_code == 404

    def test_download_creates_valid_map_structure(self) -> None:
        """Should extract all expected files in correct locations."""
        downloader = MapDownloader()
        url = "https://content.faforever.com/maps/theta_passage_5.v0001.zip"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            info = downloader.download(url, output_dir=output_dir)

            scmap_files = list(info.root_dir.glob("*.scmap"))
            assert len(scmap_files) == 1

            lua_files = list(info.root_dir.glob("*.lua"))
            assert len(lua_files) >= 3, f"Expected at least 3 lua files, found {len(lua_files)}"

            assert info.scmap_path.parent == info.root_dir

    def test_mapinfo_version_extracted_correctly(self) -> None:
        """Should correctly parse version from downloaded map."""
        downloader = MapDownloader()
        url = "https://content.faforever.com/maps/theta_passage_5.v0001.zip"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            info = downloader.download(url, output_dir=output_dir)

            assert info.version == "v0001"
            assert "theta" in info.name.lower() or "passage" in info.name.lower()
