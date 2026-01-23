"""Heightmap normalization functions.

This module provides functions for normalizing heightmap data from SCMap files
into formats suitable for machine learning training.
"""

import numpy as np

# Maximum uint16 value for normalization
UINT16_MAX = 65535


def normalize_heightmap(raw: np.ndarray) -> np.ndarray:
    """Normalize uint16 heightmap to float32 [0, 1] range.

    Args:
        raw: uint16 array from SCMap parser with values in [0, 65535].

    Returns:
        float32 array in [0, 1] range with same shape as input.

    Raises:
        ValueError: If the input array is not uint16 dtype.

    Example:
        >>> from faf.parser import SCMapParser
        >>> data = SCMapParser.parse("map.scmap")
        >>> normalized = normalize_heightmap(data.heightmap)
        >>> print(normalized.dtype)  # float32
        >>> print(normalized.min(), normalized.max())  # 0.0 - 1.0
    """
    if raw.dtype != np.uint16:
        raise ValueError(f"Expected uint16 array, got {raw.dtype}")

    return raw.astype(np.float32) / UINT16_MAX


def denormalize_heightmap(normalized: np.ndarray) -> np.ndarray:
    """Convert normalized float32 heightmap back to uint16.

    Args:
        normalized: float32 array in [0, 1] range.

    Returns:
        uint16 array with values in [0, 65535] range.

    Raises:
        ValueError: If the input array is not float32 dtype.
    """
    if normalized.dtype != np.float32:
        raise ValueError(f"Expected float32 array, got {normalized.dtype}")

    # Clip to [0, 1] range to handle any floating point errors
    clipped = np.clip(normalized, 0.0, 1.0)
    return (clipped * UINT16_MAX).astype(np.uint16)
