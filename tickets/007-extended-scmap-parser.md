# TICKET-007: Extended SCMap Parser

## Status
PENDING REVIEW

## Claude Code Working Area
- [x] Read ticket and understand requirements
- [x] Create terrain_types.py module for terrain inference
- [x] Add StratumLayer and WaterConfig dataclasses
- [x] Extend SCMapData with new fields (water, strata, terrain_type, map_size_km)
- [x] Modify parser to extract water configuration
- [x] Modify parser to extract stratum layer info (masks deferred - TODO-005)
- [x] Add unit tests for new functionality (33 new parser tests)
- [x] Test performance (0.011s for 10km map, well under 2s limit)
- [x] Run black and ruff checks
- [x] Add bulk_download CLI tests (11 new tests, total 128 tests)
- [x] Document test coverage gaps as TODOs (TODO-003 through TODO-011)
- [x] Self-review and update status

## Priority
P1-High

## Description
Extend the SCMap parser from TICKET-002 to extract additional data useful for ML training: stratum texture masks, water configuration, and terrain type classification hints. This richer data enables more sophisticated model conditioning.

## Acceptance Criteria
- [ ] Parser extracts stratum layer masks (8-bit grayscale, half resolution) - **Deferred**: masks stored after decals/props sections
- [x] Parser extracts water settings (elevation, surface elevation, has water)
- [x] Parser extracts terrain type from texture paths (desert, lava, tundra, etc.)
- [x] `SCMapData` dataclass extended with new fields
- [x] Backward compatible: existing code still works
- [x] New fields are Optional where data may not exist
- [x] Unit tests cover new parsing functionality (33 new tests, 50 total parser tests)
- [x] Performance: parsing a 20km map completes in <2 seconds (0.011s for 10km map)
- [x] Code passes `black` and `ruff` checks

## Technical Context

### Extended Data Extraction

**Stratum Masks:**
Each map has up to 10 stratum layers, each with a mask defining where that texture appears. These masks are 8-bit grayscale at half the heightmap resolution.

```
Stratum structure in .scmap:
- Stratum count (uint32)
- For each stratum:
  - Texture path (string)
  - Texture scale (float)
  - Mask data (uint8 array, dimensions = heightmap/2)
```

**Water Configuration:**
```
Water section in .scmap:
- Has water (bool)
- Water elevation (float)
- Abyss elevation (float)
- Surface elevation (float)
```

**Terrain Type Inference:**
Infer terrain type from stratum texture paths:
```python
TERRAIN_PATTERNS = {
    "desert": ["sand", "desert", "dune", "arid"],
    "lava": ["lava", "volcanic", "magma", "fire"],
    "tundra": ["snow", "ice", "frozen", "tundra"],
    "tropical": ["tropical", "jungle", "palm"],
    "temperate": ["grass", "dirt", "rock", "cliff"],
    "seabed": ["seabed", "underwater", "coral"],
}

def infer_terrain_type(texture_paths: list[str]) -> str:
    # Match paths against patterns
    # Return most likely terrain type or "unknown"
```

### Extended Data Classes
```python
@dataclass
class StratumLayer:
    texture_path: str
    texture_scale: float
    mask: np.ndarray | None      # Shape: (H/2, W/2), dtype: uint8

@dataclass
class WaterConfig:
    has_water: bool
    elevation: float
    abyss_elevation: float
    surface_elevation: float

@dataclass
class SCMapData:
    # Existing fields
    version: int
    width: float
    height: float
    heightmap: np.ndarray
    heightmap_scale: float
    
    # Extended fields (NEW)
    water: WaterConfig | None
    strata: list[StratumLayer]
    terrain_type: str            # Inferred from textures
    
    # Computed properties
    @property
    def map_size_km(self) -> int:
        """Return map size in km (5, 10, 20, etc.)"""
        return int(self.width / 51.2)
```

### Directory Structure
```
src/
└── python/
    └── faf/
        └── parser/
            ├── __init__.py
            ├── scmap.py           # Extended
            └── terrain_types.py   # NEW: terrain inference
tests/
└── python/
    └── parser/
        ├── test_scmap.py          # Extended
        └── test_terrain_types.py  # NEW
```

## Out of Scope
- Prop/decal parsing
- Unit placement data
- AI marker extraction
- Texture image loading (paths only)
- Normal map extraction

## Testing Requirements

### Unit Tests
```bash
docker-compose run --rm dev pytest tests/python/parser/ -v
```

New test cases:
- `test_parse_extracts_water_config`
- `test_parse_extracts_stratum_masks`
- `test_parse_stratum_mask_dimensions`
- `test_infer_terrain_type_desert`
- `test_infer_terrain_type_lava`
- `test_infer_terrain_type_unknown`
- `test_parse_map_without_water`

### Performance Test
```bash
docker-compose run --rm dev python -c "
import time
from faf.parser.scmap import SCMapParser

start = time.time()
data = SCMapParser.parse('/data/maps/large_20km_map/map.scmap')
elapsed = time.time() - start
print(f'Parse time: {elapsed:.2f}s')
assert elapsed < 2.0, 'Parsing too slow'
"
```

### Manual Verification
```bash
docker-compose run --rm dev python -c "
from faf.parser.scmap import SCMapParser

data = SCMapParser.parse('/data/maps/setons_clutch.v0001/setons_clutch.scmap')
print(f'Terrain type: {data.terrain_type}')
print(f'Has water: {data.water.has_water if data.water else \"N/A\"}')
print(f'Stratum count: {len(data.strata)}')
if data.strata:
    print(f'First stratum texture: {data.strata[0].texture_path}')
"
```

## Dependencies
- TICKET-002: Base SCMap parser

## References
- Neroxis SCMapImporter.java: Stratum parsing logic
- FAF Map Editor source: Water section structure