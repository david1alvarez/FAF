"""Unit tests for CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from click.testing import CliRunner

from faf.cli.main import cli, get_map_size_label, EXIT_SUCCESS, EXIT_USER_ERROR
from faf.downloader import DownloadProgress, MapDownloadError, MapInfo
from faf.parser.scmap import SCMapData


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_map_data() -> SCMapData:
    """Create a mock SCMapData object."""
    return SCMapData(
        version=60,
        width=256.0,
        height=256.0,
        heightmap=np.zeros((257, 257), dtype=np.uint16),
        heightmap_scale=0.0078125,
        water_elevation=25.0,
        texture_paths=["/textures/layer1.dds", "/textures/layer2.dds", "", ""],
    )


@pytest.fixture
def mock_map_info(tmp_path: Path) -> MapInfo:
    """Create a mock MapInfo object."""
    root_dir = tmp_path / "test_map.v0001"
    root_dir.mkdir()
    scmap_path = root_dir / "test_map.scmap"
    scmap_path.write_bytes(b"fake scmap")
    scenario_path = root_dir / "test_map_scenario.lua"
    scenario_path.write_text("-- scenario")

    return MapInfo(
        name="test map",
        version="v0001",
        root_dir=root_dir,
        scmap_path=scmap_path,
        scenario_path=scenario_path,
        save_path=root_dir / "test_map_save.lua",
        script_path=root_dir / "test_map_script.lua",
    )


class TestGetMapSizeLabel:
    """Tests for the get_map_size_label helper function."""

    def test_known_sizes(self) -> None:
        """Should return correct labels for known map sizes."""
        assert get_map_size_label(256.0) == "256x256 (5km)"
        assert get_map_size_label(512.0) == "512x512 (10km)"
        assert get_map_size_label(1024.0) == "1024x1024 (20km)"

    def test_unknown_size(self) -> None:
        """Should return 'unknown' for unrecognized sizes."""
        assert get_map_size_label(300.0) == "300x300 (unknown)"


class TestCliHelp:
    """Tests for CLI help output."""

    def test_main_help(self, runner: CliRunner) -> None:
        """Should display main help with command list."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == EXIT_SUCCESS
        assert "FAF Map AI" in result.output
        assert "download" in result.output
        assert "parse" in result.output
        assert "info" in result.output
        assert "fetch" in result.output

    def test_download_help(self, runner: CliRunner) -> None:
        """Should display download command help."""
        result = runner.invoke(cli, ["download", "--help"])
        assert result.exit_code == EXIT_SUCCESS
        assert "Download a map" in result.output
        assert "--output-dir" in result.output

    def test_parse_help(self, runner: CliRunner) -> None:
        """Should display parse command help."""
        result = runner.invoke(cli, ["parse", "--help"])
        assert result.exit_code == EXIT_SUCCESS
        assert "Parse a local .scmap file" in result.output
        assert "--output" in result.output
        assert "--output-file" in result.output

    def test_info_help(self, runner: CliRunner) -> None:
        """Should display info command help."""
        result = runner.invoke(cli, ["info", "--help"])
        assert result.exit_code == EXIT_SUCCESS
        assert "Display information" in result.output

    def test_fetch_help(self, runner: CliRunner) -> None:
        """Should display fetch command help."""
        result = runner.invoke(cli, ["fetch", "--help"])
        assert result.exit_code == EXIT_SUCCESS
        assert "Download a map and display" in result.output


class TestDownloadCommand:
    """Tests for the download command."""

    def test_download_command_calls_downloader(
        self, runner: CliRunner, mock_map_info: MapInfo
    ) -> None:
        """Should call MapDownloader with correct arguments."""
        with mock.patch("faf.cli.main.MapDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download.return_value = mock_map_info

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    [
                        "download",
                        "https://example.com/map.zip",
                        "--output-dir",
                        tmpdir,
                    ],
                )

            assert result.exit_code == EXIT_SUCCESS
            mock_instance.download.assert_called_once()
            assert "Downloaded to" in result.output

    def test_download_creates_output_dir(self, runner: CliRunner, mock_map_info: MapInfo) -> None:
        """Should create output directory if it doesn't exist."""
        with mock.patch("faf.cli.main.MapDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download.return_value = mock_map_info

            with tempfile.TemporaryDirectory() as tmpdir:
                new_dir = Path(tmpdir) / "new_maps"
                result = runner.invoke(
                    cli,
                    ["download", "https://example.com/map.zip", "--output-dir", str(new_dir)],
                )

            assert result.exit_code == EXIT_SUCCESS

    def test_download_error_exits_with_code_1(self, runner: CliRunner) -> None:
        """Should exit with code 1 on download error."""
        with mock.patch("faf.cli.main.MapDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download.side_effect = MapDownloadError("Not found", status_code=404)

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["download", "https://example.com/notfound.zip", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_USER_ERROR
            assert "Error:" in result.output


class TestParseCommand:
    """Tests for the parse command."""

    def test_parse_command_calls_parser(self, runner: CliRunner, mock_map_data: SCMapData) -> None:
        """Should call SCMapParser with correct path."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            f.write(b"fake scmap")
            temp_path = f.name

        try:
            with mock.patch("faf.cli.main.SCMapParser") as MockParser:
                MockParser.parse.return_value = mock_map_data

                result = runner.invoke(cli, ["parse", temp_path])

                assert result.exit_code == EXIT_SUCCESS
                MockParser.parse.assert_called_once()
                output = json.loads(result.output)
                assert output["version"] == 60
                assert output["width"] == 256.0
        finally:
            Path(temp_path).unlink()

    def test_parse_json_to_file(self, runner: CliRunner, mock_map_data: SCMapData) -> None:
        """Should write JSON to file when --output-file specified."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            f.write(b"fake scmap")
            scmap_path = f.name

        try:
            with mock.patch("faf.cli.main.SCMapParser") as MockParser:
                MockParser.parse.return_value = mock_map_data

                with tempfile.TemporaryDirectory() as tmpdir:
                    output_file = Path(tmpdir) / "output.json"
                    result = runner.invoke(
                        cli,
                        ["parse", scmap_path, "--output-file", str(output_file)],
                    )

                    assert result.exit_code == EXIT_SUCCESS
                    assert output_file.exists()
                    data = json.loads(output_file.read_text())
                    assert data["version"] == 60
        finally:
            Path(scmap_path).unlink()

    def test_parse_numpy_requires_output_file(
        self, runner: CliRunner, mock_map_data: SCMapData
    ) -> None:
        """Should error if numpy format without output file."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            f.write(b"fake scmap")
            temp_path = f.name

        try:
            with mock.patch("faf.cli.main.SCMapParser") as MockParser:
                MockParser.parse.return_value = mock_map_data

                result = runner.invoke(cli, ["parse", temp_path, "--output", "numpy"])

                assert result.exit_code == EXIT_USER_ERROR
                assert "--output-file is required" in result.output
        finally:
            Path(temp_path).unlink()

    def test_parse_numpy_saves_file(self, runner: CliRunner, mock_map_data: SCMapData) -> None:
        """Should save numpy array to file."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            f.write(b"fake scmap")
            scmap_path = f.name

        try:
            with mock.patch("faf.cli.main.SCMapParser") as MockParser:
                MockParser.parse.return_value = mock_map_data

                with tempfile.TemporaryDirectory() as tmpdir:
                    output_file = Path(tmpdir) / "heightmap.npy"
                    result = runner.invoke(
                        cli,
                        [
                            "parse",
                            scmap_path,
                            "--output",
                            "numpy",
                            "--output-file",
                            str(output_file),
                        ],
                    )

                    assert result.exit_code == EXIT_SUCCESS
                    assert output_file.exists()
                    loaded = np.load(output_file)
                    assert loaded.shape == (257, 257)
        finally:
            Path(scmap_path).unlink()

    def test_missing_file_exits_with_code_1(self, runner: CliRunner) -> None:
        """Should exit with code 1 for missing file."""
        result = runner.invoke(cli, ["parse", "/nonexistent/file.scmap"])
        assert result.exit_code != EXIT_SUCCESS


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_command_prints_summary(self, runner: CliRunner, mock_map_data: SCMapData) -> None:
        """Should print map information summary."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            f.write(b"fake scmap")
            temp_path = f.name

        try:
            with mock.patch("faf.cli.main.SCMapParser") as MockParser:
                MockParser.parse.return_value = mock_map_data

                result = runner.invoke(cli, ["info", temp_path])

                assert result.exit_code == EXIT_SUCCESS
                assert "Map:" in result.output
                assert "Version: 60" in result.output
                assert "Size: 256x256 (5km)" in result.output
                assert "Heightmap: 257x257" in result.output
                assert "Water Elevation: 25.0" in result.output
                assert "Textures: 2 stratum layers" in result.output
        finally:
            Path(temp_path).unlink()

    def test_info_missing_file_exits_with_code_1(self, runner: CliRunner) -> None:
        """Should exit with code 1 for missing file."""
        result = runner.invoke(cli, ["info", "/nonexistent/file.scmap"])
        assert result.exit_code != EXIT_SUCCESS


class TestFetchCommand:
    """Tests for the fetch command."""

    def test_fetch_downloads_and_shows_info(
        self, runner: CliRunner, mock_map_info: MapInfo, mock_map_data: SCMapData
    ) -> None:
        """Should download map and display info."""
        with mock.patch("faf.cli.main.MapDownloader") as MockDownloader:
            with mock.patch("faf.cli.main.SCMapParser") as MockParser:
                mock_instance = MockDownloader.return_value
                mock_instance.download.return_value = mock_map_info
                MockParser.parse.return_value = mock_map_data

                with tempfile.TemporaryDirectory() as tmpdir:
                    result = runner.invoke(
                        cli,
                        ["fetch", "https://example.com/map.zip", "--output-dir", tmpdir],
                    )

                assert result.exit_code == EXIT_SUCCESS
                assert "Downloaded to" in result.output
                assert "Map: test map" in result.output
                assert "Version: v0001" in result.output

    def test_invalid_url_exits_with_code_1(self, runner: CliRunner) -> None:
        """Should exit with code 1 on download error."""
        with mock.patch("faf.cli.main.MapDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download.side_effect = MapDownloadError("Invalid URL")

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["fetch", "not-a-url", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_USER_ERROR
            assert "Error:" in result.output


class TestBulkDownloadCommand:
    """Tests for the bulk-download command."""

    def test_bulk_download_help(self, runner: CliRunner) -> None:
        """Should display bulk-download command help."""
        result = runner.invoke(cli, ["bulk-download", "--help"])
        assert result.exit_code == EXIT_SUCCESS
        assert "Download multiple maps" in result.output
        assert "--limit" in result.output
        assert "--output-dir" in result.output
        assert "--from-file" in result.output
        assert "--concurrency" in result.output
        assert "--resume" in result.output

    def test_bulk_download_with_limit(self, runner: CliRunner) -> None:
        """Should pass limit to BulkDownloader."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=5, completed=5, failed=0, skipped=0
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--limit", "5", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            mock_instance.download_from_seed_file.assert_called_once()
            call_kwargs = mock_instance.download_from_seed_file.call_args[1]
            assert call_kwargs["limit"] == 5

    def test_bulk_download_with_concurrency(self, runner: CliRunner) -> None:
        """Should pass concurrency to BulkDownloader constructor."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=1, completed=1, failed=0, skipped=0
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--concurrency", "8", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            call_kwargs = MockDownloader.call_args[1]
            assert call_kwargs["concurrency"] == 8

    def test_bulk_download_from_file(self, runner: CliRunner) -> None:
        """Should use download_from_file when --from-file specified."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_file.return_value = DownloadProgress(
                total=3, completed=3, failed=0, skipped=0
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                url_file = Path(tmpdir) / "urls.txt"
                url_file.write_text("https://example.com/map1.zip\nhttps://example.com/map2.zip\n")

                result = runner.invoke(
                    cli,
                    ["bulk-download", "--from-file", str(url_file), "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            mock_instance.download_from_file.assert_called_once()

    def test_bulk_download_resume_flag(self, runner: CliRunner) -> None:
        """Should pass resume flag to download method."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=5, completed=2, failed=0, skipped=3
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--resume", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            call_kwargs = mock_instance.download_from_seed_file.call_args[1]
            assert call_kwargs["resume"] is True

    def test_bulk_download_no_resume_flag(self, runner: CliRunner) -> None:
        """Should pass resume=False when --no-resume specified."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=5, completed=5, failed=0, skipped=0
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--no-resume", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            call_kwargs = mock_instance.download_from_seed_file.call_args[1]
            assert call_kwargs["resume"] is False

    def test_bulk_download_displays_progress_summary(self, runner: CliRunner) -> None:
        """Should display download progress summary."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=10, completed=7, failed=2, skipped=1
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--limit", "10", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            assert "Download complete!" in result.output
            assert "Total: 10" in result.output
            assert "Completed: 7" in result.output
            assert "Failed: 2" in result.output
            assert "Skipped: 1" in result.output

    def test_bulk_download_shows_failures_hint(self, runner: CliRunner) -> None:
        """Should show hint about failures.json when there are failures."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=5, completed=3, failed=2, skipped=0
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--limit", "5", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            assert "failures.json" in result.output

    def test_bulk_download_seed_file_not_found(self, runner: CliRunner) -> None:
        """Should exit with error when seed file not found."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.side_effect = FileNotFoundError(
                "Seed URL file not found"
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_USER_ERROR
            assert "Error:" in result.output

    def test_bulk_download_creates_output_dir(self, runner: CliRunner) -> None:
        """Should create output directory if it doesn't exist."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=1, completed=1, failed=0, skipped=0
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                new_dir = Path(tmpdir) / "new_maps_dir"
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--limit", "1", "--output-dir", str(new_dir)],
                )

            assert result.exit_code == EXIT_SUCCESS
            # BulkDownloader was called with the output_dir
            call_kwargs = MockDownloader.call_args[1]
            assert call_kwargs["output_dir"] == new_dir

    def test_bulk_download_displays_settings(self, runner: CliRunner) -> None:
        """Should display download settings at start."""
        with mock.patch("faf.cli.main.BulkDownloader") as MockDownloader:
            mock_instance = MockDownloader.return_value
            mock_instance.download_from_seed_file.return_value = DownloadProgress(
                total=5, completed=5, failed=0, skipped=0
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                result = runner.invoke(
                    cli,
                    ["bulk-download", "--limit", "5", "--concurrency", "4", "--output-dir", tmpdir],
                )

            assert result.exit_code == EXIT_SUCCESS
            assert "Output directory:" in result.output
            assert "Concurrency: 4" in result.output
            assert "Limit: 5" in result.output
