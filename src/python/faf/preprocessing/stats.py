"""Dataset statistics for preprocessed FAF map datasets.

This module provides functionality to analyze preprocessed datasets,
generating statistics about map sizes, terrain types, and heightmap values.
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HeightmapStats:
    """Statistics for heightmap values across the dataset.

    Attributes:
        mean: Mean elevation value across all heightmaps.
        std: Standard deviation of elevation values.
        min_value: Minimum value across all heightmaps.
        max_value: Maximum value across all heightmaps.
    """

    mean: float
    std: float
    min_value: float
    max_value: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "mean": self.mean,
            "std": self.std,
            "min": self.min_value,
            "max": self.max_value,
        }


@dataclass
class DatasetStatistics:
    """Complete statistics for a dataset.

    Attributes:
        dataset_path: Path to the dataset.
        total_samples: Total number of samples.
        split_counts: Number of samples in each split.
        map_sizes: Distribution of map sizes (units -> count).
        terrain_types: Distribution of terrain types.
        water_counts: Count of maps with and without water.
        heightmap_stats: Statistics for heightmap values.
    """

    dataset_path: str
    total_samples: int
    split_counts: dict[str, int] = field(default_factory=dict)
    map_sizes: dict[int, int] = field(default_factory=dict)
    terrain_types: dict[str, int] = field(default_factory=dict)
    water_counts: dict[str, int] = field(default_factory=dict)
    heightmap_stats: Optional[HeightmapStats] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "dataset_path": self.dataset_path,
            "total_samples": self.total_samples,
            "splits": self.split_counts,
            "map_sizes": {str(k): v for k, v in self.map_sizes.items()},
            "terrain_types": self.terrain_types,
            "water": self.water_counts,
        }
        if self.heightmap_stats:
            result["heightmap_stats"] = self.heightmap_stats.to_dict()
        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def format_human_readable(self) -> str:
        """Format statistics as human-readable text."""
        lines = []
        lines.append(f"Dataset Statistics: {self.dataset_path}")
        lines.append("=" * (len(lines[0])))
        lines.append("")

        # Sample counts
        lines.append(f"Samples: {self.total_samples:,} total")
        if self.split_counts:
            for split_name in ["train", "val", "test"]:
                count = self.split_counts.get(split_name, 0)
                pct = (count / self.total_samples * 100) if self.total_samples > 0 else 0
                lines.append(f"  {split_name.capitalize():5}: {count:,} ({pct:.1f}%)")
        lines.append("")

        # Map sizes
        if self.map_sizes:
            lines.append("Map Sizes:")
            size_to_km = {128: "2.5km", 256: "5km", 512: "10km", 1024: "20km", 2048: "40km"}
            for size in sorted(self.map_sizes.keys()):
                count = self.map_sizes[size]
                pct = (count / self.total_samples * 100) if self.total_samples > 0 else 0
                km_label = size_to_km.get(size, f"{size}u")
                lines.append(f"  {km_label:8} ({size}): {count:,} ({pct:.1f}%)")
            lines.append("")

        # Terrain types
        if self.terrain_types:
            lines.append("Terrain Types:")
            for terrain in sorted(self.terrain_types.keys()):
                count = self.terrain_types[terrain]
                pct = (count / self.total_samples * 100) if self.total_samples > 0 else 0
                lines.append(f"  {terrain:12}: {count:,} ({pct:.1f}%)")
            lines.append("")

        # Heightmap stats
        if self.heightmap_stats:
            lines.append("Heightmap Stats:")
            lines.append(f"  Mean elevation: {self.heightmap_stats.mean:.3f}")
            lines.append(f"  Std elevation:  {self.heightmap_stats.std:.3f}")
            lines.append(f"  Min across all: {self.heightmap_stats.min_value:.3f}")
            lines.append(f"  Max across all: {self.heightmap_stats.max_value:.3f}")
            lines.append("")

        # Water stats
        if self.water_counts:
            lines.append("Water:")
            with_water = self.water_counts.get("with_water", 0)
            without_water = self.water_counts.get("without_water", 0)
            with_pct = (with_water / self.total_samples * 100) if self.total_samples > 0 else 0
            without_pct = (
                (without_water / self.total_samples * 100) if self.total_samples > 0 else 0
            )
            lines.append(f"  Maps with water: {with_water:,} ({with_pct:.1f}%)")
            lines.append(f"  Maps without:    {without_water:,} ({without_pct:.1f}%)")

        return "\n".join(lines)


class DatasetStats:
    """Statistics generator for preprocessed FAF map datasets.

    This class analyzes datasets created by DatasetBuilder, computing
    statistics about map sizes, terrain types, and heightmap values.

    Args:
        dataset_path: Path to the dataset directory to analyze.
        compute_heightmap_stats: Whether to compute heightmap statistics
            (requires loading all heightmaps, can be slow for large datasets).

    Example:
        >>> stats = DatasetStats(Path("/data/dataset"))
        >>> result = stats.compute()
        >>> print(result.format_human_readable())
    """

    def __init__(self, dataset_path: Path, compute_heightmap_stats: bool = True):
        self.dataset_path = Path(dataset_path)
        self.compute_heightmap_stats = compute_heightmap_stats
        self.metadata: Optional[dict] = None
        self.splits: Optional[dict] = None

    def compute(self) -> DatasetStatistics:
        """Compute statistics for the dataset.

        Returns:
            DatasetStatistics with computed values.

        Raises:
            FileNotFoundError: If the dataset directory doesn't exist.
            ValueError: If metadata.json is missing or invalid.
        """
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")

        # Load metadata
        self._load_metadata()
        self._load_splits()

        if self.metadata is None:
            raise ValueError("Failed to load metadata.json")

        samples = self.metadata.get("samples", {})
        total_samples = len(samples)

        # Compute split counts
        split_counts = self._compute_split_counts()

        # Compute map size distribution
        map_sizes = self._compute_map_sizes(samples)

        # Compute terrain type distribution
        terrain_types = self._compute_terrain_types(samples)

        # Compute water statistics
        water_counts = self._compute_water_counts(samples)

        # Compute heightmap statistics if requested
        heightmap_stats = None
        if self.compute_heightmap_stats and total_samples > 0:
            heightmap_stats = self._compute_heightmap_stats(samples)

        return DatasetStatistics(
            dataset_path=str(self.dataset_path),
            total_samples=total_samples,
            split_counts=split_counts,
            map_sizes=map_sizes,
            terrain_types=terrain_types,
            water_counts=water_counts,
            heightmap_stats=heightmap_stats,
        )

    def _load_metadata(self) -> None:
        """Load metadata.json."""
        metadata_path = self.dataset_path / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"metadata.json not found in {self.dataset_path}")

        with open(metadata_path) as f:
            self.metadata = json.load(f)

    def _load_splits(self) -> None:
        """Load splits.json."""
        splits_path = self.dataset_path / "splits.json"
        if splits_path.exists():
            with open(splits_path) as f:
                self.splits = json.load(f)

    def _compute_split_counts(self) -> dict[str, int]:
        """Compute number of samples in each split."""
        if self.splits is None:
            return {}

        return {
            "train": len(self.splits.get("train", [])),
            "val": len(self.splits.get("val", [])),
            "test": len(self.splits.get("test", [])),
        }

    def _compute_map_sizes(self, samples: dict) -> dict[int, int]:
        """Compute distribution of map sizes."""
        sizes: list[int] = []
        for sample_meta in samples.values():
            if "map_size" in sample_meta:
                sizes.append(sample_meta["map_size"])
        return dict(Counter(sizes))

    def _compute_terrain_types(self, samples: dict) -> dict[str, int]:
        """Compute distribution of terrain types."""
        types: list[str] = []
        for sample_meta in samples.values():
            terrain = sample_meta.get("terrain_type", "unknown")
            types.append(terrain)
        return dict(Counter(types))

    def _compute_water_counts(self, samples: dict) -> dict[str, int]:
        """Compute count of maps with and without water."""
        with_water = 0
        without_water = 0
        for sample_meta in samples.values():
            if sample_meta.get("has_water", False):
                with_water += 1
            else:
                without_water += 1
        return {"with_water": with_water, "without_water": without_water}

    def _compute_heightmap_stats(self, samples: dict) -> Optional[HeightmapStats]:
        """Compute statistics across all heightmaps.

        This loads each heightmap and computes aggregate statistics.
        Can be slow for large datasets.
        """
        all_means: list[float] = []
        all_stds: list[float] = []
        global_min = float("inf")
        global_max = float("-inf")

        for sample_id, sample_meta in samples.items():
            heightmap_file = sample_meta.get("heightmap_file")
            if heightmap_file is None:
                continue

            heightmap_path = self.dataset_path / heightmap_file
            if not heightmap_path.exists():
                logger.warning(f"Heightmap not found: {heightmap_path}")
                continue

            try:
                hm = np.load(heightmap_path)
                all_means.append(float(hm.mean()))
                all_stds.append(float(hm.std()))
                global_min = min(global_min, float(hm.min()))
                global_max = max(global_max, float(hm.max()))
            except Exception as e:
                logger.warning(f"Failed to load heightmap {heightmap_path}: {e}")

        if not all_means:
            return None

        return HeightmapStats(
            mean=float(np.mean(all_means)),
            std=float(np.mean(all_stds)),
            min_value=global_min,
            max_value=global_max,
        )
