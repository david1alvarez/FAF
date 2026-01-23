"""SCMap file parsing utilities."""

from faf.parser.scmap import SCMapData, SCMapParser, StratumLayer, WaterConfig
from faf.parser.terrain_types import (
    TERRAIN_PATTERNS,
    get_all_terrain_types,
    get_terrain_keywords,
    infer_terrain_type,
)

__all__ = [
    "SCMapData",
    "SCMapParser",
    "StratumLayer",
    "WaterConfig",
    "TERRAIN_PATTERNS",
    "get_all_terrain_types",
    "get_terrain_keywords",
    "infer_terrain_type",
]
