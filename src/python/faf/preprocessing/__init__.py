"""Preprocessing module for FAF map datasets.

This module provides functionality to transform downloaded FAF maps into
ML-ready datasets, including heightmap normalization and train/val/test splits.
"""

from faf.preprocessing.dataset import DatasetBuilder
from faf.preprocessing.normalize import normalize_heightmap

__all__ = [
    "DatasetBuilder",
    "normalize_heightmap",
]
