#!/usr/bin/env python3
"""Generate a minimal .scmap test fixture file.

This creates a valid SCMap file with minimal data for testing purposes.
The generated file represents a 5km (256 unit) map with a flat heightmap.
"""

import struct
from pathlib import Path

# SCMap format constants
SCMAP_SIGNATURE = 443572557
SCMAP_VERSION_MAJOR = 2
SCMAP_MAGIC = -1091567891
SCMAP_FORMAT_TYPE = 2
SCMAP_VERSION_MINOR = 56  # SC version

# Map parameters (5km = 256 units)
MAP_SIZE = 256
HEIGHTMAP_DIM = MAP_SIZE + 1  # 257x257


def write_int(f, value: int) -> None:
    """Write a little-endian 32-bit signed integer."""
    f.write(struct.pack("<i", value))


def write_uint(f, value: int) -> None:
    """Write a little-endian 32-bit unsigned integer."""
    f.write(struct.pack("<I", value))


def write_float(f, value: float) -> None:
    """Write a little-endian 32-bit float."""
    f.write(struct.pack("<f", value))


def write_short(f, value: int) -> None:
    """Write a little-endian 16-bit signed integer."""
    f.write(struct.pack("<h", value))


def write_ushort(f, value: int) -> None:
    """Write a little-endian 16-bit unsigned integer."""
    f.write(struct.pack("<H", value))


def write_byte(f, value: int) -> None:
    """Write a single byte."""
    f.write(struct.pack("B", value))


def write_string_null(f, value: str) -> None:
    """Write a null-terminated string."""
    f.write(value.encode("utf-8") + b"\x00")


def generate_minimal_dds_preview() -> bytes:
    """Generate a minimal DDS preview image (1x1 pixel)."""
    # Minimal DDS header for a 1x1 ARGB image
    # DDS magic + header
    dds = bytearray()

    # DDS magic "DDS "
    dds.extend(b"DDS ")

    # DDS_HEADER structure (124 bytes)
    dds.extend(struct.pack("<I", 124))  # dwSize
    dds.extend(
        struct.pack("<I", 0x1 | 0x2 | 0x4 | 0x1000)
    )  # dwFlags (CAPS|HEIGHT|WIDTH|PIXELFORMAT)
    dds.extend(struct.pack("<I", 1))  # dwHeight
    dds.extend(struct.pack("<I", 1))  # dwWidth
    dds.extend(struct.pack("<I", 4))  # dwPitchOrLinearSize
    dds.extend(struct.pack("<I", 0))  # dwDepth
    dds.extend(struct.pack("<I", 0))  # dwMipMapCount
    dds.extend(b"\x00" * 44)  # dwReserved1[11]

    # DDS_PIXELFORMAT structure (32 bytes)
    dds.extend(struct.pack("<I", 32))  # dwSize
    dds.extend(struct.pack("<I", 0x41))  # dwFlags (DDPF_RGB | DDPF_ALPHAPIXELS)
    dds.extend(struct.pack("<I", 0))  # dwFourCC
    dds.extend(struct.pack("<I", 32))  # dwRGBBitCount
    dds.extend(struct.pack("<I", 0x00FF0000))  # dwRBitMask
    dds.extend(struct.pack("<I", 0x0000FF00))  # dwGBitMask
    dds.extend(struct.pack("<I", 0x000000FF))  # dwBBitMask
    dds.extend(struct.pack("<I", 0xFF000000))  # dwABitMask

    # dwCaps
    dds.extend(struct.pack("<I", 0x1000))  # DDSCAPS_TEXTURE
    dds.extend(struct.pack("<I", 0))  # dwCaps2
    dds.extend(struct.pack("<I", 0))  # dwCaps3
    dds.extend(struct.pack("<I", 0))  # dwCaps4
    dds.extend(struct.pack("<I", 0))  # dwReserved2

    # 1x1 pixel data (ARGB)
    dds.extend(struct.pack("<I", 0xFF808080))  # Gray pixel

    return bytes(dds)


def generate_test_scmap(output_path: Path) -> None:
    """Generate a minimal valid .scmap file for testing."""
    with open(output_path, "wb") as f:
        # Header
        write_int(f, SCMAP_SIGNATURE)
        write_int(f, SCMAP_VERSION_MAJOR)
        write_int(f, SCMAP_MAGIC)
        write_int(f, SCMAP_FORMAT_TYPE)
        write_float(f, float(MAP_SIZE))  # width
        write_float(f, float(MAP_SIZE))  # height
        write_int(f, 0)  # reserved
        write_short(f, 0)  # reserved

        # Preview image
        preview_data = generate_minimal_dds_preview()
        write_int(f, len(preview_data))
        f.write(preview_data)

        # Minor version
        write_int(f, SCMAP_VERSION_MINOR)

        # Heightmap header
        write_int(f, MAP_SIZE)  # width
        write_int(f, MAP_SIZE)  # height
        write_float(f, 1.0 / 128.0)  # heightmap scale

        # Heightmap data (257x257 uint16 values)
        # Create a simple terrain: edges at 0, center raised
        for y in range(HEIGHTMAP_DIM):
            for x in range(HEIGHTMAP_DIM):
                # Simple bowl-shaped terrain
                cx, cy = HEIGHTMAP_DIM // 2, HEIGHTMAP_DIM // 2
                dx, dy = abs(x - cx), abs(y - cy)
                dist = max(dx, dy)
                height = max(0, 32768 - dist * 100)
                write_ushort(f, height)

        # Validation byte
        write_byte(f, 0)

        # Texture paths
        write_string_null(f, "/textures/terrain/normals.dds")  # shader
        write_string_null(f, "/textures/background.dds")  # background
        write_string_null(f, "/textures/sky/sky.dds")  # sky cube

        # Cube maps (0 entries)
        write_int(f, 0)

        # Lighting settings (52 bytes)
        # Ambient color (3 floats)
        write_float(f, 0.2)
        write_float(f, 0.2)
        write_float(f, 0.2)
        # Sun color (3 floats)
        write_float(f, 1.0)
        write_float(f, 1.0)
        write_float(f, 0.9)
        # Sun direction (3 floats)
        write_float(f, 0.5)
        write_float(f, -0.7)
        write_float(f, 0.5)
        # Shadow fill (3 floats)
        write_float(f, 0.1)
        write_float(f, 0.1)
        write_float(f, 0.15)
        # Sun multiplier (1 float)
        write_float(f, 1.5)

        # Water settings
        write_byte(f, 1)  # water present
        write_float(f, 25.0)  # water elevation
        write_float(f, 20.0)  # water elevation deep
        write_float(f, 10.0)  # water elevation abyss

        # Surface color (3 floats)
        write_float(f, 0.0)
        write_float(f, 0.2)
        write_float(f, 0.4)
        # Color lerp (2 floats)
        write_float(f, 0.064)
        write_float(f, 0.119)
        # Refraction scale (1 float)
        write_float(f, 0.375)
        # Fresnel bias (1 float)
        write_float(f, 0.15)
        # Fresnel power (1 float)
        write_float(f, 1.5)
        # Unit reflection (1 float)
        write_float(f, 0.5)
        # Sky reflection (1 float)
        write_float(f, 1.5)
        # Sun shininess (1 float)
        write_float(f, 100.0)
        # Sun strength (1 float)
        write_float(f, 10.0)
        # Sun direction (3 floats)
        write_float(f, 0.09954818)
        write_float(f, -0.9626309)
        write_float(f, 0.2518569)
        # Sun color (3 floats)
        write_float(f, 0.8)
        write_float(f, 0.7)
        write_float(f, 0.5)
        # Sun reflection (1 float)
        write_float(f, 5.0)
        # Sun glow (1 float)
        write_float(f, 0.1)
        # Water texture path
        write_string_null(f, "/textures/engine/waterramp.dds")
        # Wave normal repeats (4 floats)
        write_float(f, 0.0009)
        write_float(f, 0.009)
        write_float(f, 0.05)
        write_float(f, 0.5)

        # Wave generators (0 entries)
        write_int(f, 0)

        # Minimap settings
        write_int(f, 24)  # contour interval
        write_uint(f, 0xFF1E3C64)  # shallow color
        write_uint(f, 0xFF0A1428)  # deep color
        write_uint(f, 0x00000000)  # contour color
        write_uint(f, 0xFF6E9632)  # shore color
        write_uint(f, 0xFF19320A)  # land start color
        write_uint(f, 0xFF7D9619)  # land end color

        # Preview size (version 56+)
        write_float(f, 1024.0)

        # Terrain textures (10 entries)
        terrain_textures = [
            "/textures/terrain/rock_albedo.dds",
            "/textures/terrain/grass_albedo.dds",
            "/textures/terrain/sand_albedo.dds",
            "/textures/terrain/dirt_albedo.dds",
            "",  # empty slots
            "",
            "",
            "",
            "",
            "",
        ]
        for tex in terrain_textures:
            write_string_null(f, tex)
            write_float(f, 4.0)  # scale

        # Terrain normals (9 entries)
        terrain_normals = [
            "/textures/terrain/rock_normal.dds",
            "/textures/terrain/grass_normal.dds",
            "/textures/terrain/sand_normal.dds",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        for normal in terrain_normals:
            write_string_null(f, normal)
            write_float(f, 4.0)  # scale

    print(f"Generated test SCMap: {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")


if __name__ == "__main__":
    output_path = Path(__file__).parent.parent / "tests" / "fixtures" / "test_5km_minimal.scmap"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_test_scmap(output_path)
