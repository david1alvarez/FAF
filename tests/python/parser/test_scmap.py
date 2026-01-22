"""Unit tests for SCMap parser.

Tests verify the parser correctly reads .scmap binary files and extracts
heightmap data, metadata, and texture paths.
"""

import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest

from faf.parser.scmap import (
    SCMAP_SIGNATURE,
    SCMAP_VERSION_MAJOR,
    SCMapData,
    SCMapParseError,
    SCMapParser,
)

# Path to test fixture
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "test_5km_minimal.scmap"


class TestSCMapParserValidFile:
    """Tests for parsing valid .scmap files."""

    def test_parse_valid_scmap_returns_scmapdata(self) -> None:
        """Parsing a valid scmap file should return an SCMapData instance."""
        result = SCMapParser.parse(FIXTURE_PATH)

        assert isinstance(result, SCMapData)

    def test_parse_extracts_correct_version(self) -> None:
        """Parser should extract the correct minor version."""
        result = SCMapParser.parse(FIXTURE_PATH)

        assert result.version == 56

    def test_parse_extracts_correct_dimensions(self) -> None:
        """Parser should extract correct map width and height."""
        result = SCMapParser.parse(FIXTURE_PATH)

        assert result.width == 256.0
        assert result.height == 256.0

    def test_parse_extracts_correct_heightmap_dimensions(self) -> None:
        """Heightmap dimensions should be (map_size + 1) x (map_size + 1)."""
        result = SCMapParser.parse(FIXTURE_PATH)

        # 256 unit map should have 257x257 heightmap
        assert result.heightmap.shape == (257, 257)

    def test_parse_heightmap_is_uint16(self) -> None:
        """Heightmap should be stored as uint16 values."""
        result = SCMapParser.parse(FIXTURE_PATH)

        assert result.heightmap.dtype == np.uint16

    def test_parse_heightmap_values_in_valid_range(self) -> None:
        """Heightmap values should be within uint16 range [0, 65535]."""
        result = SCMapParser.parse(FIXTURE_PATH)

        assert result.heightmap.min() >= 0
        assert result.heightmap.max() <= 65535

    def test_parse_extracts_heightmap_scale(self) -> None:
        """Parser should extract heightmap scale factor."""
        result = SCMapParser.parse(FIXTURE_PATH)

        # Default scale is 1/128
        assert abs(result.heightmap_scale - (1.0 / 128.0)) < 0.0001

    def test_parse_extracts_water_elevation(self) -> None:
        """Parser should extract water elevation."""
        result = SCMapParser.parse(FIXTURE_PATH)

        assert result.water_elevation == 25.0

    def test_parse_extracts_texture_paths(self) -> None:
        """Parser should extract texture paths."""
        result = SCMapParser.parse(FIXTURE_PATH)

        assert isinstance(result.texture_paths, list)
        assert len(result.texture_paths) > 0
        # Check known texture paths from fixture
        assert "/textures/terrain/rock_albedo.dds" in result.texture_paths
        assert "/textures/terrain/grass_albedo.dds" in result.texture_paths


class TestSCMapParserInvalidFiles:
    """Tests for error handling with invalid files."""

    def test_parse_raises_on_nonexistent_file(self) -> None:
        """Should raise FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            SCMapParser.parse(Path("/nonexistent/path/map.scmap"))

    def test_parse_raises_on_invalid_magic_bytes(self) -> None:
        """Should raise SCMapParseError for files with invalid signature."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            # Write invalid signature
            f.write(struct.pack("<i", 12345678))
            f.write(b"\x00" * 100)  # Padding
            temp_path = Path(f.name)

        try:
            with pytest.raises(SCMapParseError) as exc_info:
                SCMapParser.parse(temp_path)
            assert "Invalid SCMap signature" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_parse_raises_on_invalid_version_major(self) -> None:
        """Should raise SCMapParseError for unsupported major version."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            # Write valid signature but invalid major version
            f.write(struct.pack("<i", SCMAP_SIGNATURE))
            f.write(struct.pack("<i", 99))  # Invalid major version
            f.write(b"\x00" * 100)
            temp_path = Path(f.name)

        try:
            with pytest.raises(SCMapParseError) as exc_info:
                SCMapParser.parse(temp_path)
            assert "Unsupported SCMap major version" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_parse_raises_on_invalid_magic_number(self) -> None:
        """Should raise SCMapParseError for invalid magic number."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            f.write(struct.pack("<i", SCMAP_SIGNATURE))
            f.write(struct.pack("<i", SCMAP_VERSION_MAJOR))
            f.write(struct.pack("<i", 0))  # Invalid magic
            f.write(b"\x00" * 100)
            temp_path = Path(f.name)

        try:
            with pytest.raises(SCMapParseError) as exc_info:
                SCMapParser.parse(temp_path)
            assert "Invalid SCMap magic number" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_parse_raises_on_truncated_file(self) -> None:
        """Should raise SCMapParseError for truncated files."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            # Write only partial header
            f.write(struct.pack("<i", SCMAP_SIGNATURE))
            f.write(struct.pack("<i", SCMAP_VERSION_MAJOR))
            # File ends abruptly
            temp_path = Path(f.name)

        try:
            with pytest.raises(SCMapParseError) as exc_info:
                SCMapParser.parse(temp_path)
            assert "Truncated or corrupted" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_parse_raises_on_empty_file(self) -> None:
        """Should raise SCMapParseError for empty files."""
        with tempfile.NamedTemporaryFile(suffix=".scmap", delete=False) as f:
            temp_path = Path(f.name)

        try:
            with pytest.raises(SCMapParseError):
                SCMapParser.parse(temp_path)
        finally:
            temp_path.unlink()


class TestSCMapData:
    """Tests for SCMapData dataclass."""

    def test_scmapdata_fields_accessible(self) -> None:
        """SCMapData should have all expected fields accessible."""
        data = SCMapParser.parse(FIXTURE_PATH)

        # All fields should be accessible
        assert hasattr(data, "version")
        assert hasattr(data, "width")
        assert hasattr(data, "height")
        assert hasattr(data, "heightmap")
        assert hasattr(data, "heightmap_scale")
        assert hasattr(data, "water_elevation")
        assert hasattr(data, "texture_paths")

    def test_scmapdata_heightmap_is_2d_array(self) -> None:
        """Heightmap should be a 2D numpy array."""
        data = SCMapParser.parse(FIXTURE_PATH)

        assert isinstance(data.heightmap, np.ndarray)
        assert len(data.heightmap.shape) == 2
