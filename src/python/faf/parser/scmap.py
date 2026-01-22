"""Parser for Supreme Commander .scmap binary files.

This module provides functionality to read and extract data from .scmap files,
the map format used by Supreme Commander: Forged Alliance and FAForever.
"""

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Union

import numpy as np

# SCMap format constants (from Neroxis Map Generator)
SCMAP_SIGNATURE = 443572557
SCMAP_VERSION_MAJOR = 2
SCMAP_MAGIC = -1091567891  # 0xBEEFBEEF endian-swapped
SCMAP_FORMAT_TYPE = 2

# Supported minor versions
SCMAP_VERSION_SC = 56  # Supreme Commander
SCMAP_VERSION_FA = 60  # Forged Alliance

# DDS header size (fixed for preview images)
DDS_HEADER_SIZE = 128


@dataclass
class SCMapData:
    """Container for parsed SCMap data.

    Attributes:
        version: SCMap minor version (56 for SC, 60 for FA).
        width: Map width in game units.
        height: Map height in game units.
        heightmap: 2D numpy array of height values (uint16).
        heightmap_scale: Scale factor for heightmap values.
        water_elevation: Water surface elevation level.
        texture_paths: List of stratum texture file paths.
    """

    version: int
    width: float
    height: float
    heightmap: np.ndarray
    heightmap_scale: float
    water_elevation: float
    texture_paths: list[str]


class SCMapParseError(Exception):
    """Raised when an SCMap file cannot be parsed."""

    pass


class SCMapParser:
    """Parser for SCMap binary files.

    This class provides methods to read and parse .scmap files, extracting
    heightmap data, metadata, and texture paths.

    Example:
        >>> data = SCMapParser.parse("map.scmap")
        >>> print(f"Map size: {data.width}x{data.height}")
        >>> print(f"Heightmap shape: {data.heightmap.shape}")
    """

    @classmethod
    def parse(cls, path: Union[str, Path]) -> SCMapData:
        """Parse an SCMap file and return its data.

        Args:
            path: Path to the .scmap file.

        Returns:
            SCMapData containing the parsed map information.

        Raises:
            FileNotFoundError: If the scmap file doesn't exist.
            SCMapParseError: If the file is not a valid SCMap or is corrupted.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"SCMap file not found: {path}")

        with open(path, "rb") as f:
            return cls._parse_stream(f, path)

    @classmethod
    def _parse_stream(cls, f: BinaryIO, path: Path) -> SCMapData:
        """Parse an SCMap from an open binary stream.

        Args:
            f: Binary file stream positioned at the start.
            path: Path to the file (for error messages).

        Returns:
            SCMapData containing the parsed map information.

        Raises:
            SCMapParseError: If the file is not a valid SCMap or is corrupted.
        """
        try:
            # Read and validate header
            signature = cls._read_int(f)
            if signature != SCMAP_SIGNATURE:
                raise SCMapParseError(
                    f"Invalid SCMap signature: expected {SCMAP_SIGNATURE}, got {signature}"
                )

            version_major = cls._read_int(f)
            if version_major != SCMAP_VERSION_MAJOR:
                raise SCMapParseError(
                    f"Unsupported SCMap major version: expected {SCMAP_VERSION_MAJOR}, "
                    f"got {version_major}"
                )

            magic = cls._read_int(f)
            if magic != SCMAP_MAGIC:
                raise SCMapParseError(f"Invalid SCMap magic number: {magic}")

            format_type = cls._read_int(f)
            if format_type != SCMAP_FORMAT_TYPE:
                raise SCMapParseError(f"Unsupported SCMap format type: {format_type}")

            # Read map dimensions
            width = cls._read_float(f)
            height = cls._read_float(f)

            # Skip reserved fields
            cls._read_int(f)  # Reserved (should be 0)
            cls._read_short(f)  # Reserved (should be 0)

            # Skip preview image (DDS header + image data)
            preview_byte_count = cls._read_int(f)
            f.seek(preview_byte_count, 1)  # Skip preview data

            # Read minor version
            version = cls._read_int(f)
            if version not in (SCMAP_VERSION_SC, SCMAP_VERSION_FA):
                raise SCMapParseError(
                    f"Unsupported SCMap minor version: {version}. "
                    f"Expected {SCMAP_VERSION_SC} (SC) or {SCMAP_VERSION_FA} (FA)"
                )

            # Read heightmap
            heightmap_width = cls._read_int(f)
            heightmap_height = cls._read_int(f)
            heightmap_scale = cls._read_float(f)

            # Heightmap dimensions are (size + 1) x (size + 1)
            heightmap_size = (heightmap_width + 1) * (heightmap_height + 1)
            heightmap_data = cls._read_shorts(f, heightmap_size)
            heightmap = np.array(heightmap_data, dtype=np.uint16).reshape(
                (heightmap_height + 1, heightmap_width + 1)
            )

            # Validation byte after heightmap
            cls._read_byte(f)

            # Skip texture paths (shader, background, sky cube)
            cls._read_string_null(f)  # shader_path
            cls._read_string_null(f)  # background_path
            cls._read_string_null(f)  # sky_cube_path

            # Skip cube map entries
            cube_map_count = cls._read_int(f)
            for _ in range(cube_map_count):
                cls._read_string_null(f)  # name
                cls._read_string_null(f)  # cube_path

            # Skip lighting settings (52 bytes total)
            # LightingSettings: 3 floats ambient + 3 floats sun color +
            # 3 floats sun direction + 3 floats shadow fill = 48 bytes
            # + 1 float sun multiplier = 4 bytes = 52 bytes
            f.seek(52, 1)

            # Read water settings
            cls._read_byte(f)  # water_present
            water_elevation = cls._read_float(f)
            cls._read_float(f)  # water_elevation_deep
            cls._read_float(f)  # water_elevation_abyss

            # Skip rest of water settings (surface color, color lerp, refraction,
            # fresnel bias/power, unit reflection, sky reflection, sun shininess,
            # sun strength, sun direction, sun color, sun reflection, sun glow,
            # texture path, wave normal repeats)
            # Surface color (3 floats) + color lerp (2 floats) = 20 bytes
            f.seek(20, 1)
            # Refraction scale (1 float) + fresnel bias (1 float) +
            # fresnel power (1 float) = 12 bytes
            f.seek(12, 1)
            # Unit reflection (1 float) + sky reflection (1 float) = 8 bytes
            f.seek(8, 1)
            # Sun shininess (1 float) + sun strength (1 float) = 8 bytes
            f.seek(8, 1)
            # Sun direction (3 floats) + sun color (3 floats) = 24 bytes
            f.seek(24, 1)
            # Sun reflection (1 float) + sun glow (1 float) = 8 bytes
            f.seek(8, 1)
            # Texture path (string)
            cls._read_string_null(f)
            # Wave normal repeats (4 floats) = 16 bytes
            f.seek(16, 1)

            # Skip wave generators
            wave_generator_count = cls._read_int(f)
            for _ in range(wave_generator_count):
                cls._read_string_null(f)  # texture path
                cls._read_string_null(f)  # ramp path
                # Position (3 floats) + rotation (1 float) + velocity (3 floats) = 28 bytes
                f.seek(28, 1)
                # lifetime start/end (2 floats) + period start/end (2 floats) = 16 bytes
                f.seek(16, 1)
                # scale start/end (2 floats) + frame count (1 float) +
                # frame rate start/end (2 floats) = 20 bytes
                f.seek(20, 1)
                # Strip count (1 float) = 4 bytes
                f.seek(4, 1)

            # Skip minimap data (7 ints = 28 bytes)
            for _ in range(7):
                cls._read_int(f)

            # Version 56+ has additional minimap settings
            if version >= 56:
                cls._read_float(f)  # minimap_preview_size

            # Version 60+ has cartographic contour settings
            if version >= 60:
                f.seek(4, 1)  # Unknown value

            # Read terrain materials (texture paths)
            texture_paths = []

            # There are typically 10 stratum layers (9 terrain + 1 upper)
            # Each has: path (string) + scale (float) + normal path (string) + scale (float)
            # But we'll read what we can and handle variations

            # The terrain materials section has:
            # - TERRAIN_TEXTURE_COUNT texture entries (each: path string + float scale)
            # - TERRAIN_NORMAL_COUNT normal entries (each: path string + float scale)
            # TERRAIN_TEXTURE_COUNT and TERRAIN_NORMAL_COUNT are typically 10 each

            terrain_texture_count = 10
            for _ in range(terrain_texture_count):
                tex_path = cls._read_string_null(f)
                cls._read_float(f)  # tex_scale
                if tex_path:
                    texture_paths.append(tex_path)

            terrain_normal_count = 9
            for _ in range(terrain_normal_count):
                normal_path = cls._read_string_null(f)
                cls._read_float(f)  # normal_scale
                if normal_path:
                    texture_paths.append(normal_path)

            return SCMapData(
                version=version,
                width=width,
                height=height,
                heightmap=heightmap,
                heightmap_scale=heightmap_scale,
                water_elevation=water_elevation,
                texture_paths=texture_paths,
            )

        except struct.error as e:
            raise SCMapParseError(f"Truncated or corrupted SCMap file: {path}") from e

    @staticmethod
    def _read_int(f: BinaryIO) -> int:
        """Read a little-endian 32-bit signed integer."""
        data = f.read(4)
        if len(data) < 4:
            raise struct.error("Unexpected end of file")
        return struct.unpack("<i", data)[0]

    @staticmethod
    def _read_float(f: BinaryIO) -> float:
        """Read a little-endian 32-bit float."""
        data = f.read(4)
        if len(data) < 4:
            raise struct.error("Unexpected end of file")
        return struct.unpack("<f", data)[0]

    @staticmethod
    def _read_short(f: BinaryIO) -> int:
        """Read a little-endian 16-bit signed integer."""
        data = f.read(2)
        if len(data) < 2:
            raise struct.error("Unexpected end of file")
        return struct.unpack("<h", data)[0]

    @staticmethod
    def _read_shorts(f: BinaryIO, count: int) -> list[int]:
        """Read multiple little-endian 16-bit unsigned integers."""
        data = f.read(count * 2)
        if len(data) < count * 2:
            raise struct.error("Unexpected end of file")
        return list(struct.unpack(f"<{count}H", data))

    @staticmethod
    def _read_byte(f: BinaryIO) -> int:
        """Read a single byte."""
        data = f.read(1)
        if len(data) < 1:
            raise struct.error("Unexpected end of file")
        return data[0]

    @staticmethod
    def _read_string_null(f: BinaryIO) -> str:
        """Read a null-terminated string."""
        chars = []
        while True:
            char = f.read(1)
            if not char or char == b"\x00":
                break
            chars.append(char)
        return b"".join(chars).decode("utf-8", errors="replace")
