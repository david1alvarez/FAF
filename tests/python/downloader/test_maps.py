"""Unit tests for map downloader with mocked HTTP."""

import io
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import pytest
import requests

from faf.downloader.maps import (
    MapDownloader,
    MapDownloadError,
    MapInfo,
)


def create_valid_map_zip(map_name: str = "test_map", version: str = "v0001") -> bytes:
    """Create a valid map zip file in memory.

    Args:
        map_name: Base name for the map files.
        version: Version string for the map.

    Returns:
        Bytes of a valid map zip file.
    """
    buffer = io.BytesIO()
    dir_name = f"{map_name}.{version}"

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{dir_name}/{map_name}.scmap", b"fake scmap data")
        zf.writestr(f"{dir_name}/{map_name}_scenario.lua", b"-- scenario")
        zf.writestr(f"{dir_name}/{map_name}_save.lua", b"-- save")
        zf.writestr(f"{dir_name}/{map_name}_script.lua", b"-- script")

    return buffer.getvalue()


def create_invalid_zip() -> bytes:
    """Create bytes that are not a valid zip file.

    Returns:
        Bytes that will fail zip validation.
    """
    return b"not a zip file content"


def create_zip_missing_scmap() -> bytes:
    """Create a zip file without .scmap file.

    Returns:
        Bytes of a zip file missing the .scmap.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_map.v0001/test_map_scenario.lua", b"-- scenario")
        zf.writestr("test_map.v0001/test_map_save.lua", b"-- save")

    return buffer.getvalue()


def create_zip_missing_scenario() -> bytes:
    """Create a zip file without _scenario.lua file.

    Returns:
        Bytes of a zip file missing the scenario file.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_map.v0001/test_map.scmap", b"fake scmap data")
        zf.writestr("test_map.v0001/test_map_save.lua", b"-- save")

    return buffer.getvalue()


class TestMapDownloaderDownloadFromUrl:
    """Tests for downloading maps from direct URLs."""

    def test_download_from_url_extracts_zip(self) -> None:
        """Should extract zip contents to output directory."""
        downloader = MapDownloader()
        zip_content = create_valid_map_zip("test_map", "v0001")

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.content = zip_content

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=mock_response):
                info = downloader.download(
                    "https://content.faforever.com/maps/test_map.v0001.zip",
                    output_dir=output_dir,
                )

            assert info.root_dir.exists()
            assert info.scmap_path.exists()
            assert info.scenario_path.exists()

    def test_download_returns_correct_mapinfo(self) -> None:
        """Should return MapInfo with correct paths and metadata."""
        downloader = MapDownloader()
        zip_content = create_valid_map_zip("my_cool_map", "v0005")

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.content = zip_content

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=mock_response):
                info = downloader.download(
                    "https://content.faforever.com/maps/my_cool_map.v0005.zip",
                    output_dir=output_dir,
                )

            assert info.name == "my cool map"
            assert info.version == "v0005"
            assert info.root_dir == output_dir / "my_cool_map.v0005"
            assert info.scmap_path == info.root_dir / "my_cool_map.scmap"
            assert info.scenario_path == info.root_dir / "my_cool_map_scenario.lua"
            assert info.save_path == info.root_dir / "my_cool_map_save.lua"
            assert info.script_path == info.root_dir / "my_cool_map_script.lua"

    def test_download_raises_on_404(self) -> None:
        """Should raise MapDownloadError with status_code for 404 responses."""
        downloader = MapDownloader()

        mock_response = mock.Mock()
        mock_response.status_code = 404

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=mock_response):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download(
                        "https://content.faforever.com/maps/nonexistent.zip",
                        output_dir=output_dir,
                    )

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value).lower()

    def test_download_raises_on_invalid_zip(self) -> None:
        """Should raise MapDownloadError for invalid zip content."""
        downloader = MapDownloader()

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.content = create_invalid_zip()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=mock_response):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download(
                        "https://content.faforever.com/maps/invalid.zip",
                        output_dir=output_dir,
                    )

            assert "not a valid zip" in str(exc_info.value).lower()

    def test_download_raises_on_missing_output_dir(self) -> None:
        """Should raise FileNotFoundError if output directory doesn't exist."""
        downloader = MapDownloader()

        with pytest.raises(FileNotFoundError) as exc_info:
            downloader.download(
                "https://content.faforever.com/maps/test.zip",
                output_dir=Path("/nonexistent/directory"),
            )

        assert "does not exist" in str(exc_info.value)


class TestMapDownloaderRetryLogic:
    """Tests for retry behavior on transient errors."""

    def test_download_retries_on_transient_error(self) -> None:
        """Should retry on 503 and succeed on subsequent attempt."""
        downloader = MapDownloader(max_retries=3, retry_delay=0.01)
        zip_content = create_valid_map_zip()

        fail_response = mock.Mock()
        fail_response.status_code = 503

        success_response = mock.Mock()
        success_response.status_code = 200
        success_response.content = zip_content

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch(
                "requests.get", side_effect=[fail_response, fail_response, success_response]
            ):
                info = downloader.download(
                    "https://content.faforever.com/maps/test_map.v0001.zip",
                    output_dir=output_dir,
                )

            assert info.scmap_path.exists()

    def test_download_fails_after_max_retries(self) -> None:
        """Should raise MapDownloadError after exhausting retry attempts."""
        downloader = MapDownloader(max_retries=3, retry_delay=0.01)

        fail_response = mock.Mock()
        fail_response.status_code = 503

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=fail_response):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download(
                        "https://content.faforever.com/maps/test.zip",
                        output_dir=output_dir,
                    )

            assert "3 attempts" in str(exc_info.value)

    def test_download_retries_on_timeout(self) -> None:
        """Should retry on request timeout."""
        downloader = MapDownloader(max_retries=2, retry_delay=0.01)
        zip_content = create_valid_map_zip()

        success_response = mock.Mock()
        success_response.status_code = 200
        success_response.content = zip_content

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch(
                "requests.get",
                side_effect=[requests.exceptions.Timeout(), success_response],
            ):
                info = downloader.download(
                    "https://content.faforever.com/maps/test_map.v0001.zip",
                    output_dir=output_dir,
                )

            assert info.scmap_path.exists()

    def test_no_retry_on_404(self) -> None:
        """Should not retry on 404 errors."""
        downloader = MapDownloader(max_retries=3, retry_delay=0.01)

        mock_response = mock.Mock()
        mock_response.status_code = 404

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", side_effect=mock_get):
                with pytest.raises(MapDownloadError):
                    downloader.download(
                        "https://content.faforever.com/maps/notfound.zip",
                        output_dir=output_dir,
                    )

            assert call_count == 1


class TestMapDownloaderValidation:
    """Tests for map structure validation."""

    def test_download_validates_map_structure_missing_scmap(self) -> None:
        """Should raise MapDownloadError if .scmap file is missing."""
        downloader = MapDownloader()

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.content = create_zip_missing_scmap()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=mock_response):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download(
                        "https://content.faforever.com/maps/test.zip",
                        output_dir=output_dir,
                    )

            assert "no .scmap file" in str(exc_info.value).lower()

    def test_download_validates_map_structure_missing_scenario(self) -> None:
        """Should raise MapDownloadError if _scenario.lua is missing."""
        downloader = MapDownloader()

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.content = create_zip_missing_scenario()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=mock_response):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download(
                        "https://content.faforever.com/maps/test.zip",
                        output_dir=output_dir,
                    )

            assert "missing" in str(exc_info.value).lower()
            assert "scenario" in str(exc_info.value).lower()


class TestMapDownloaderByName:
    """Tests for downloading maps by name via FAF API."""

    def test_download_by_name_resolves_url(self) -> None:
        """Should look up map URL via API and download."""
        downloader = MapDownloader()
        zip_content = create_valid_map_zip("setons_clutch", "v0001")

        api_response = mock.Mock()
        api_response.status_code = 200
        api_response.json.return_value = {
            "data": [
                {
                    "attributes": {
                        "downloadUrl": "https://content.faforever.com/maps/setons_clutch.v0001.zip"
                    }
                }
            ]
        }

        download_response = mock.Mock()
        download_response.status_code = 200
        download_response.content = zip_content

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            def mock_get(url, **kwargs):
                if "api.faforever.com" in url:
                    return api_response
                return download_response

            with mock.patch("requests.get", side_effect=mock_get):
                info = downloader.download_by_name("Seton's Clutch", output_dir=output_dir)

            assert info.scmap_path.exists()

    def test_download_by_name_raises_on_not_found(self) -> None:
        """Should raise MapDownloadError if map is not found in API."""
        downloader = MapDownloader()

        api_response = mock.Mock()
        api_response.status_code = 200
        api_response.json.return_value = {"data": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=api_response):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download_by_name("Nonexistent Map", output_dir=output_dir)

            assert "not found" in str(exc_info.value).lower()

    def test_download_by_name_raises_on_api_error(self) -> None:
        """Should raise MapDownloadError if API request fails."""
        downloader = MapDownloader()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download_by_name("Some Map", output_dir=output_dir)

            assert "api request failed" in str(exc_info.value).lower()

    def test_download_by_name_raises_on_missing_download_url(self) -> None:
        """Should raise MapDownloadError if map has no downloadUrl."""
        downloader = MapDownloader()

        api_response = mock.Mock()
        api_response.status_code = 200
        api_response.json.return_value = {"data": [{"attributes": {}}]}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with mock.patch("requests.get", return_value=api_response):
                with pytest.raises(MapDownloadError) as exc_info:
                    downloader.download_by_name("Broken Map", output_dir=output_dir)

            assert "no download url" in str(exc_info.value).lower()


class TestMapInfo:
    """Tests for the MapInfo dataclass."""

    def test_mapinfo_stores_all_fields(self) -> None:
        """MapInfo should store all provided fields."""
        info = MapInfo(
            name="Test Map",
            version="v0001",
            root_dir=Path("/maps/test_map.v0001"),
            scmap_path=Path("/maps/test_map.v0001/test_map.scmap"),
            scenario_path=Path("/maps/test_map.v0001/test_map_scenario.lua"),
            save_path=Path("/maps/test_map.v0001/test_map_save.lua"),
            script_path=Path("/maps/test_map.v0001/test_map_script.lua"),
        )

        assert info.name == "Test Map"
        assert info.version == "v0001"
        assert info.root_dir == Path("/maps/test_map.v0001")
        assert info.scmap_path == Path("/maps/test_map.v0001/test_map.scmap")


class TestMapDownloaderParseMapName:
    """Tests for map name parsing from directory names."""

    def test_parse_name_with_dot_version(self) -> None:
        """Should parse name.v0001 format correctly."""
        downloader = MapDownloader()
        name, version = downloader._parse_map_name("cool_map.v0005")

        assert name == "cool map"
        assert version == "v0005"

    def test_parse_name_with_underscore_version(self) -> None:
        """Should parse name_v0001 format correctly."""
        downloader = MapDownloader()
        name, version = downloader._parse_map_name("cool_map_v0003")

        assert name == "cool map"
        assert version == "v0003"

    def test_parse_name_without_version(self) -> None:
        """Should default to v0001 if no version found."""
        downloader = MapDownloader()
        name, version = downloader._parse_map_name("cool_map")

        assert name == "cool map"
        assert version == "v0001"

    def test_parse_name_preserves_spaces(self) -> None:
        """Should convert underscores to spaces in name."""
        downloader = MapDownloader()
        name, version = downloader._parse_map_name("my_awesome_map.v0002")

        assert name == "my awesome map"
        assert version == "v0002"
