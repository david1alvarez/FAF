"""Dataset builder for preprocessing FAF maps into ML-ready format.

This module provides the DatasetBuilder class which transforms downloaded
FAF maps into a structured dataset suitable for machine learning training.
"""

import hashlib
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from faf.parser import SCMapParser
from faf.parser.scmap import SCMapParseError
from faf.preprocessing.normalize import normalize_heightmap

logger = logging.getLogger(__name__)

# Dataset format version
DATASET_VERSION = "1.0"

# Default split ratios
DEFAULT_SPLIT_RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}


@dataclass
class SampleMetadata:
    """Metadata for a single preprocessed sample.

    Attributes:
        sample_id: Unique identifier for this sample.
        original_path: Original path to the source .scmap file.
        map_size: Map size in game units.
        map_size_km: Map size in kilometers.
        terrain_type: Inferred terrain type from textures.
        has_water: Whether the map has water enabled.
        water_elevation: Water surface elevation level.
        heightmap_shape: Shape of the heightmap array (H, W).
        heightmap_file: Relative path to the heightmap .npy file.
    """

    sample_id: str
    original_path: str
    map_size: int
    map_size_km: int
    terrain_type: str
    has_water: bool
    water_elevation: float
    heightmap_shape: tuple[int, int]
    heightmap_file: str


@dataclass
class BuildProgress:
    """Progress information for dataset building.

    Attributes:
        total: Total number of maps to process.
        processed: Number of maps successfully processed.
        failed: Number of maps that failed to process.
        skipped: Number of maps skipped (e.g., wrong size).
        current_map: Name of the currently processing map.
    """

    total: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    current_map: str = ""


@dataclass
class BuildResult:
    """Result of building a dataset.

    Attributes:
        output_dir: Path to the output dataset directory.
        total_samples: Total number of samples in the dataset.
        processed: Number of maps successfully processed.
        failed: Number of maps that failed to process.
        skipped: Number of maps skipped (e.g., wrong size).
        split_counts: Number of samples in each split (train/val/test).
    """

    output_dir: Path
    total_samples: int
    processed: int
    failed: int
    skipped: int
    split_counts: dict[str, int] = field(default_factory=dict)


class DatasetBuilder:
    """Builder for preprocessing FAF maps into ML-ready datasets.

    This class handles the complete preprocessing pipeline:
    1. Discovers .scmap files in the input directory
    2. Parses each map and extracts heightmap data
    3. Normalizes heightmaps to float32 [0, 1] range
    4. Saves heightmaps as .npy files
    5. Generates metadata.json with sample information
    6. Creates train/val/test splits in splits.json

    Args:
        output_dir: Directory to write the dataset to.
        min_size: Minimum map size in game units (filter smaller maps).
        max_size: Maximum map size in game units (filter larger maps).
        split_ratios: Dictionary with train/val/test ratios (must sum to 1.0).
        seed: Random seed for reproducible splits.
        progress_callback: Optional callback for progress updates.

    Example:
        >>> builder = DatasetBuilder(
        ...     output_dir=Path("/data/dataset"),
        ...     min_size=256,
        ...     seed=42
        ... )
        >>> result = builder.build(input_dir=Path("/data/maps"))
        >>> print(f"Built dataset with {result.total_samples} samples")
    """

    def __init__(
        self,
        output_dir: Path,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        split_ratios: Optional[dict[str, float]] = None,
        seed: int = 42,
        progress_callback: Optional[Callable[[BuildProgress], None]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.min_size = min_size
        self.max_size = max_size
        self.split_ratios = split_ratios or DEFAULT_SPLIT_RATIOS.copy()
        self.seed = seed
        self.progress_callback = progress_callback

        # Validate split ratios
        total_ratio = sum(self.split_ratios.values())
        if abs(total_ratio - 1.0) > 0.0001:
            raise ValueError(f"Split ratios must sum to 1.0, got {total_ratio}")

    def build(self, input_dir: Path) -> BuildResult:
        """Build dataset from maps in the input directory.

        Args:
            input_dir: Directory containing downloaded map directories.
                Each subdirectory should contain a .scmap file.

        Returns:
            BuildResult with statistics about the build process.

        Raises:
            FileNotFoundError: If input_dir doesn't exist.
            OSError: If output directory cannot be created.
        """
        input_dir = Path(input_dir)
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        # Create output structure
        self.output_dir.mkdir(parents=True, exist_ok=True)
        heightmaps_dir = self.output_dir / "heightmaps"
        heightmaps_dir.mkdir(exist_ok=True)

        # Find all .scmap files
        scmap_files = list(input_dir.glob("**/*.scmap"))
        logger.info(f"Found {len(scmap_files)} .scmap files in {input_dir}")

        # Process each map
        progress = BuildProgress(total=len(scmap_files))
        samples: dict[str, SampleMetadata] = {}
        errors: list[dict[str, str]] = []

        for scmap_path in scmap_files:
            progress.current_map = scmap_path.parent.name
            self._update_progress(progress)

            try:
                metadata = self._process_map(scmap_path, heightmaps_dir)
                if metadata:
                    samples[metadata.sample_id] = metadata
                    progress.processed += 1
                else:
                    progress.skipped += 1
            except (SCMapParseError, OSError) as e:
                logger.warning(f"Failed to process {scmap_path}: {e}")
                errors.append({"path": str(scmap_path), "error": str(e)})
                progress.failed += 1

            self._update_progress(progress)

        # Create splits
        split_counts = self._create_splits(list(samples.keys()))

        # Write metadata.json
        self._write_metadata(samples)

        # Write errors.json if there were failures
        if errors:
            self._write_errors(errors)

        return BuildResult(
            output_dir=self.output_dir,
            total_samples=len(samples),
            processed=progress.processed,
            failed=progress.failed,
            skipped=progress.skipped,
            split_counts=split_counts,
        )

    def _process_map(self, scmap_path: Path, heightmaps_dir: Path) -> Optional[SampleMetadata]:
        """Process a single map file.

        Args:
            scmap_path: Path to the .scmap file.
            heightmaps_dir: Directory to save heightmap .npy files.

        Returns:
            SampleMetadata if successful, None if skipped due to size filter.

        Raises:
            SCMapParseError: If the map cannot be parsed.
            OSError: If the heightmap cannot be saved.
        """
        # Parse the map
        map_data = SCMapParser.parse(scmap_path)

        # Apply size filters
        map_size = int(map_data.width)
        if self.min_size and map_size < self.min_size:
            logger.debug(f"Skipping {scmap_path}: size {map_size} < {self.min_size}")
            return None
        if self.max_size and map_size > self.max_size:
            logger.debug(f"Skipping {scmap_path}: size {map_size} > {self.max_size}")
            return None

        # Generate sample ID from directory name
        sample_id = self._generate_sample_id(scmap_path)

        # Normalize and save heightmap
        normalized = normalize_heightmap(map_data.heightmap)
        heightmap_file = f"heightmaps/{sample_id}.npy"
        np.save(heightmaps_dir / f"{sample_id}.npy", normalized)

        # Determine water info
        has_water = False
        water_elevation = 0.0
        if map_data.water:
            has_water = map_data.water.has_water
            water_elevation = map_data.water.elevation
        else:
            water_elevation = map_data.water_elevation

        return SampleMetadata(
            sample_id=sample_id,
            original_path=str(scmap_path),
            map_size=map_size,
            map_size_km=map_data.map_size_km,
            terrain_type=map_data.terrain_type,
            has_water=has_water,
            water_elevation=water_elevation,
            heightmap_shape=(map_data.heightmap.shape[0], map_data.heightmap.shape[1]),
            heightmap_file=heightmap_file,
        )

    def _generate_sample_id(self, scmap_path: Path) -> str:
        """Generate a unique sample ID from the scmap path.

        Uses the parent directory name (e.g., "map_name.v0001") and converts
        it to a safe filename format.

        Args:
            scmap_path: Path to the .scmap file.

        Returns:
            A unique sample ID string.
        """
        dir_name = scmap_path.parent.name
        # Replace dots and spaces with underscores for filesystem safety
        safe_name = dir_name.replace(".", "_").replace(" ", "_").lower()
        # If the directory has a generic name, include a hash of the full path
        if safe_name in ("maps", "map", ""):
            path_hash = hashlib.md5(str(scmap_path).encode()).hexdigest()[:8]
            safe_name = f"map_{path_hash}"
        return safe_name

    def _create_splits(self, sample_ids: list[str]) -> dict[str, int]:
        """Create train/val/test splits and write splits.json.

        Args:
            sample_ids: List of all sample IDs.

        Returns:
            Dictionary with counts for each split.
        """
        # Shuffle deterministically
        rng = random.Random(self.seed)
        shuffled = sample_ids.copy()
        rng.shuffle(shuffled)

        # Calculate split boundaries
        n = len(shuffled)
        train_end = int(n * self.split_ratios["train"])
        val_end = train_end + int(n * self.split_ratios["val"])

        splits = {
            "train": shuffled[:train_end],
            "val": shuffled[train_end:val_end],
            "test": shuffled[val_end:],
        }

        # Write splits.json
        splits_data = {
            "version": DATASET_VERSION,
            "seed": self.seed,
            "ratios": self.split_ratios,
            "train": splits["train"],
            "val": splits["val"],
            "test": splits["test"],
        }

        with open(self.output_dir / "splits.json", "w") as f:
            json.dump(splits_data, f, indent=2)

        return {k: len(v) for k, v in splits.items()}

    def _write_metadata(self, samples: dict[str, SampleMetadata]) -> None:
        """Write metadata.json file.

        Args:
            samples: Dictionary mapping sample IDs to their metadata.
        """
        metadata = {
            "version": DATASET_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_samples": len(samples),
            "samples": {},
        }

        for sample_id, sample in samples.items():
            metadata["samples"][sample_id] = {
                "original_path": sample.original_path,
                "map_size": sample.map_size,
                "map_size_km": sample.map_size_km,
                "terrain_type": sample.terrain_type,
                "has_water": sample.has_water,
                "water_elevation": sample.water_elevation,
                "heightmap_shape": list(sample.heightmap_shape),
                "heightmap_file": sample.heightmap_file,
            }

        with open(self.output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def _write_errors(self, errors: list[dict[str, str]]) -> None:
        """Write errors.json file for failed maps.

        Args:
            errors: List of error dictionaries with path and error message.
        """
        with open(self.output_dir / "errors.json", "w") as f:
            json.dump({"errors": errors}, f, indent=2)

    def _update_progress(self, progress: BuildProgress) -> None:
        """Call the progress callback if set.

        Args:
            progress: Current build progress.
        """
        if self.progress_callback:
            self.progress_callback(progress)
