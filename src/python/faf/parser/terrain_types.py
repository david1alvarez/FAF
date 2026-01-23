"""Terrain type inference from texture paths.

This module provides functionality to infer the terrain type (desert, lava, tundra, etc.)
from the texture paths used in an SCMap file.
"""

from typing import Optional

# Terrain type patterns - keywords that indicate specific terrain types
TERRAIN_PATTERNS: dict[str, list[str]] = {
    "desert": ["sand", "desert", "dune", "arid", "dry", "sahara"],
    "lava": ["lava", "volcanic", "magma", "fire", "molten", "ember"],
    "tundra": ["snow", "ice", "frozen", "tundra", "arctic", "frost", "glacier"],
    "tropical": ["tropical", "jungle", "palm", "rainforest", "humid"],
    "temperate": ["grass", "dirt", "rock", "cliff", "stone", "earth", "soil"],
    "seabed": ["seabed", "underwater", "coral", "ocean", "seafloor"],
}

# Default terrain type when no patterns match
DEFAULT_TERRAIN_TYPE = "unknown"


def infer_terrain_type(texture_paths: list[str]) -> str:
    """Infer the terrain type from a list of texture paths.

    Analyzes texture file paths to determine the most likely terrain type
    based on keyword matching. The terrain type with the most keyword matches
    across all texture paths is returned.

    Args:
        texture_paths: List of texture file paths from the SCMap.

    Returns:
        Inferred terrain type string (e.g., "desert", "lava", "temperate").
        Returns "unknown" if no patterns match.

    Example:
        >>> paths = ["/textures/sand_albedo.dds", "/textures/desert_rock.dds"]
        >>> infer_terrain_type(paths)
        'desert'
    """
    if not texture_paths:
        return DEFAULT_TERRAIN_TYPE

    # Count matches for each terrain type
    terrain_scores: dict[str, int] = {terrain: 0 for terrain in TERRAIN_PATTERNS}

    for path in texture_paths:
        if not path:
            continue

        # Normalize path for matching (lowercase, extract filename)
        path_lower = path.lower()

        for terrain_type, keywords in TERRAIN_PATTERNS.items():
            for keyword in keywords:
                if keyword in path_lower:
                    terrain_scores[terrain_type] += 1

    # Find terrain type with highest score
    max_score = max(terrain_scores.values())

    if max_score == 0:
        return DEFAULT_TERRAIN_TYPE

    # Return the terrain type with the highest score
    for terrain_type, score in terrain_scores.items():
        if score == max_score:
            return terrain_type

    return DEFAULT_TERRAIN_TYPE


def get_terrain_keywords(terrain_type: str) -> Optional[list[str]]:
    """Get the keywords associated with a terrain type.

    Args:
        terrain_type: The terrain type to look up.

    Returns:
        List of keywords for the terrain type, or None if not found.
    """
    return TERRAIN_PATTERNS.get(terrain_type)


def get_all_terrain_types() -> list[str]:
    """Get a list of all known terrain types.

    Returns:
        List of terrain type names.
    """
    return list(TERRAIN_PATTERNS.keys())
