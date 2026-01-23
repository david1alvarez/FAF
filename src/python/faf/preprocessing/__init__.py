"""Preprocessing module for FAF map datasets.

This module provides functionality to transform downloaded FAF maps into
ML-ready datasets, including heightmap normalization and train/val/test splits.
"""

from faf.preprocessing.dataset import DatasetBuilder
from faf.preprocessing.normalize import normalize_heightmap
from faf.preprocessing.stats import DatasetStats
from faf.preprocessing.validate import DatasetValidator

__all__ = [
    "DatasetBuilder",
    "DatasetStats",
    "DatasetValidator",
    "normalize_heightmap",
]
