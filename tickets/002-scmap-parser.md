# TICKET-002: SCMap Binary File Parser

## Status
COMPLETE

## Priority
P0-Critical

## Description
Implement a Python parser for the `.scmap` binary file format used by Supreme Commander: Forged Alliance. This parser will extract heightmap data and map metadata, which are essential inputs for the ML training pipeline.

## Acceptance Criteria
- [x] `src/python/faf/parser/scmap.py` exists with `SCMapParser` class
- [x] Parser can read .scmap files (v56 and v60 formats)
- [x] Parser extracts heightmap as numpy array (uint16)
- [x] Parser extracts map metadata: version, width, height, water elevation
- [x] Parser extracts texture/stratum mask paths (not the textures themselves)
- [x] Includes dataclass `SCMapData` to hold parsed results
- [x] Unit tests exist in `tests/python/parser/test_scmap.py`
- [x] Tests use a small fixture .scmap file committed to `tests/fixtures/`
- [x] Code passes `black` and `ruff` checks
- [x] All public functions have type hints and docstrings

## Technical Context

### SCMap File Format Overview
The .scmap file is a binary format containing terrain and visual data. Key structure (derived from Neroxis Map Generator source):

```
Header:
  - bytes 0-3: "Map\x1a" magic bytes
  - byte 4: file version (56 for SC, 60 for FA)
  - bytes 5-8: unknown/reserved
  - bytes 9-12: width (float, map units)
  - bytes 13-16: height (float, map units)
  - bytes 17-20: unknown/reserved
  - bytes 21-22: heightmap scale (uint16)

Heightmap Section:
  - Dimensions: (width/heightmapScale + 1) x (height/heightmapScale + 1)
  - Data: uint16 little-endian values
  - Example: 10km map (512 units) with scale 1 = 513x513 heightmap

Texture Paths Section:
  - String table of texture file paths
  - Each stratum layer references paths here

[Additional sections for props, decals, etc. - OUT OF SCOPE for this ticket]
```

### Reference Implementation
Study these files from Neroxis Map Generator (https://github.com/FAForever/Neroxis-Map-Generator):
- `shared/src/main/java/com/faforever/neroxis/map/SCMap.java`
- `shared/src/main/java/com/faforever/neroxis/exporter/SCMapExporter.java`
- `shared/src/main/java/com/faforever/neroxis/importer/SCMapImporter.java`

### Data Classes
```python
@dataclass
class SCMapData:
    version: int                    # 56 or 60
    width: float                    # Map width in game units
    height: float                   # Map height in game units
    heightmap: np.ndarray           # 2D uint16 array
    heightmap_scale: float          # Usually 1.0
    water_elevation: float          # Water level
    texture_paths: list[str]        # Stratum texture paths
```

### Directory Structure After Completion
```
src/
└── python/
    └── faf/
        ├── __init__.py
        └── parser/
            ├── __init__.py
            └── scmap.py
tests/
├── fixtures/
│   └── test_5km_minimal.scmap    # Small test map
└── python/
    └── parser/
        └── test_scmap.py
```

## Out of Scope
- Parsing prop/decal data (future ticket)
- Parsing unit placement data
- Writing/exporting .scmap files
- Texture image extraction (paths only)
- Skybox data (v60 specific)
- Full parity with Neroxis parser

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/parser/test_scmap.py -v
```

Expected test cases:
- `test_parse_valid_scmap_returns_scmapdata`
- `test_parse_extracts_correct_heightmap_dimensions`
- `test_parse_heightmap_values_in_valid_range`
- `test_parse_raises_on_invalid_magic_bytes`
- `test_parse_raises_on_truncated_file`

### Manual Verification
```bash
docker-compose run --rm dev python -c "
from faf.parser.scmap import SCMapParser
data = SCMapParser.parse('tests/fixtures/test_5km_minimal.scmap')
print(f'Version: {data.version}')
print(f'Size: {data.width}x{data.height}')
print(f'Heightmap shape: {data.heightmap.shape}')
print(f'Heightmap range: {data.heightmap.min()}-{data.heightmap.max()}')
"
```

## References
- Neroxis SCMapImporter.java: https://github.com/FAForever/Neroxis-Map-Generator/tree/develop/shared
- FAF Wiki on map format: https://wiki.faforever.com/en/Development/Mapping/FA-Forever-Map-Editor
- Heightmap spec: 16-bit grayscale, dimensions = mapSize + 1

## Claude Code Working Area

### Implementation Summary

Implemented a complete SCMap binary parser with the following components:

1. **`src/python/faf/parser/scmap.py`**: Main parser module containing:
   - `SCMapData` dataclass with all required fields
   - `SCMapParser` class with `parse()` classmethod
   - `SCMapParseError` exception for error handling
   - Format constants (SCMAP_SIGNATURE, SCMAP_VERSION_MAJOR, etc.)

2. **`tests/python/parser/test_scmap.py`**: 17 unit tests covering:
   - Valid file parsing (9 tests)
   - Invalid file handling (6 tests)
   - SCMapData dataclass verification (2 tests)

3. **`tests/fixtures/test_5km_minimal.scmap`**: Generated test fixture (132KB)
   - 256x256 unit map (5km)
   - 257x257 heightmap with bowl-shaped terrain
   - Includes texture paths and water settings

4. **`scripts/generate_test_scmap.py`**: Utility to regenerate test fixtures

### Key Technical Decisions

- Used little-endian byte order throughout (matches game format)
- Read heightmap as uint16 array (preserving original precision)
- Texture paths extracted from terrain materials section (10 textures + 9 normals)
- Skipped non-essential data sections (props, decals, compressed maps) as per scope

### Test Results

All 17 tests pass in both local and Docker environments:
- `pytest tests/python/parser/test_scmap.py -v` passes
- Code passes `black --line-length 100` formatting
- Code passes `ruff` linting checks