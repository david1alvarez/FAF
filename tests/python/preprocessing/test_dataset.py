"""Unit tests for DatasetBuilder class."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from faf.preprocessing.dataset import (
    BuildProgress,
    BuildResult,
    DatasetBuilder,
    SampleMetadata,
)

# Path to test fixture
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "test_5km_minimal.scmap"


class TestDatasetBuilderInit:
    """Tests for DatasetBuilder initialization."""

    def test_init_with_default_ratios(self) -> None:
        """Builder should use default split ratios."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DatasetBuilder(output_dir=Path(tmpdir))
            assert builder.split_ratios["train"] == 0.8
            assert builder.split_ratios["val"] == 0.1
            assert builder.split_ratios["test"] == 0.1

    def test_init_with_custom_ratios(self) -> None:
        """Builder should accept custom split ratios."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ratios = {"train": 0.7, "val": 0.15, "test": 0.15}
            builder = DatasetBuilder(output_dir=Path(tmpdir), split_ratios=ratios)
            assert builder.split_ratios == ratios

    def test_init_raises_on_invalid_ratios(self) -> None:
        """Builder should raise ValueError if ratios don't sum to 1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ratios = {"train": 0.5, "val": 0.2, "test": 0.2}
            with pytest.raises(ValueError, match="must sum to 1.0"):
                DatasetBuilder(output_dir=Path(tmpdir), split_ratios=ratios)

    def test_init_with_size_filters(self) -> None:
        """Builder should accept size filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DatasetBuilder(output_dir=Path(tmpdir), min_size=256, max_size=1024)
            assert builder.min_size == 256
            assert builder.max_size == 1024

    def test_init_with_seed(self) -> None:
        """Builder should accept random seed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DatasetBuilder(output_dir=Path(tmpdir), seed=123)
            assert builder.seed == 123


class TestDatasetBuilderBuild:
    """Tests for DatasetBuilder.build method."""

    def test_build_creates_output_directory(self) -> None:
        """Build should create output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new_dataset"
            builder = DatasetBuilder(output_dir=output_dir)
            # Use empty input dir
            input_dir = Path(tmpdir) / "input"
            input_dir.mkdir()
            builder.build(input_dir)
            assert output_dir.exists()

    def test_build_creates_heightmaps_directory(self) -> None:
        """Build should create heightmaps subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            input_dir.mkdir()
            builder = DatasetBuilder(output_dir=output_dir)
            builder.build(input_dir)
            assert (output_dir / "heightmaps").exists()

    def test_build_raises_on_nonexistent_input(self) -> None:
        """Build should raise FileNotFoundError for missing input dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = DatasetBuilder(output_dir=Path(tmpdir) / "out")
            with pytest.raises(FileNotFoundError, match="Input directory not found"):
                builder.build(Path("/nonexistent/path"))

    def test_build_returns_build_result(self) -> None:
        """Build should return a BuildResult instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            input_dir.mkdir()
            builder = DatasetBuilder(output_dir=output_dir)
            result = builder.build(input_dir)
            assert isinstance(result, BuildResult)

    def test_build_with_fixture_creates_npy(self) -> None:
        """Build should create .npy file for valid scmap."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "test_map.v0001"
            map_dir.mkdir(parents=True)

            # Copy fixture to input directory
            import shutil

            shutil.copy(FIXTURE_PATH, map_dir / "test_map.scmap")

            builder = DatasetBuilder(output_dir=output_dir)
            result = builder.build(input_dir)

            assert result.processed == 1
            npy_files = list((output_dir / "heightmaps").glob("*.npy"))
            assert len(npy_files) == 1

    def test_build_with_fixture_creates_metadata_json(self) -> None:
        """Build should create metadata.json file."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "test_map.v0001"
            map_dir.mkdir(parents=True)

            import shutil

            shutil.copy(FIXTURE_PATH, map_dir / "test_map.scmap")

            builder = DatasetBuilder(output_dir=output_dir)
            builder.build(input_dir)

            metadata_path = output_dir / "metadata.json"
            assert metadata_path.exists()

            with open(metadata_path) as f:
                metadata = json.load(f)

            assert "version" in metadata
            assert "total_samples" in metadata
            assert "samples" in metadata
            assert metadata["total_samples"] == 1

    def test_build_with_fixture_creates_splits_json(self) -> None:
        """Build should create splits.json file."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "test_map.v0001"
            map_dir.mkdir(parents=True)

            import shutil

            shutil.copy(FIXTURE_PATH, map_dir / "test_map.scmap")

            builder = DatasetBuilder(output_dir=output_dir)
            builder.build(input_dir)

            splits_path = output_dir / "splits.json"
            assert splits_path.exists()

            with open(splits_path) as f:
                splits = json.load(f)

            assert "version" in splits
            assert "seed" in splits
            assert "train" in splits
            assert "val" in splits
            assert "test" in splits

    def test_build_heightmap_is_normalized(self) -> None:
        """Built heightmaps should be normalized float32 in [0, 1]."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "test_map.v0001"
            map_dir.mkdir(parents=True)

            import shutil

            shutil.copy(FIXTURE_PATH, map_dir / "test_map.scmap")

            builder = DatasetBuilder(output_dir=output_dir)
            builder.build(input_dir)

            npy_files = list((output_dir / "heightmaps").glob("*.npy"))
            heightmap = np.load(npy_files[0])

            assert heightmap.dtype == np.float32
            assert heightmap.min() >= 0.0
            assert heightmap.max() <= 1.0


class TestDatasetBuilderSizeFilters:
    """Tests for size filtering in DatasetBuilder."""

    def test_build_skips_maps_below_min_size(self) -> None:
        """Build should skip maps smaller than min_size."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "test_map.v0001"
            map_dir.mkdir(parents=True)

            import shutil

            shutil.copy(FIXTURE_PATH, map_dir / "test_map.scmap")

            # Fixture is 256 units (5km), filter for 512+ (10km+)
            builder = DatasetBuilder(output_dir=output_dir, min_size=512)
            result = builder.build(input_dir)

            assert result.skipped == 1
            assert result.processed == 0

    def test_build_skips_maps_above_max_size(self) -> None:
        """Build should skip maps larger than max_size."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "test_map.v0001"
            map_dir.mkdir(parents=True)

            import shutil

            shutil.copy(FIXTURE_PATH, map_dir / "test_map.scmap")

            # Fixture is 256 units (5km), filter for 128 max (2.5km)
            builder = DatasetBuilder(output_dir=output_dir, max_size=128)
            result = builder.build(input_dir)

            assert result.skipped == 1
            assert result.processed == 0


class TestDatasetBuilderSplits:
    """Tests for split creation in DatasetBuilder."""

    def test_splits_are_disjoint(self) -> None:
        """Train, val, and test splits should have no overlap."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"

            # Create multiple maps for meaningful splits
            import shutil

            for i in range(10):
                map_dir = input_dir / f"test_map_{i}.v0001"
                map_dir.mkdir(parents=True)
                shutil.copy(FIXTURE_PATH, map_dir / f"test_map_{i}.scmap")

            builder = DatasetBuilder(output_dir=output_dir, seed=42)
            builder.build(input_dir)

            with open(output_dir / "splits.json") as f:
                splits = json.load(f)

            train_set = set(splits["train"])
            val_set = set(splits["val"])
            test_set = set(splits["test"])

            assert train_set.isdisjoint(val_set)
            assert train_set.isdisjoint(test_set)
            assert val_set.isdisjoint(test_set)

    def test_splits_are_reproducible_with_seed(self) -> None:
        """Splits should be identical with the same seed."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"

            import shutil

            for i in range(10):
                map_dir = input_dir / f"test_map_{i}.v0001"
                map_dir.mkdir(parents=True)
                shutil.copy(FIXTURE_PATH, map_dir / f"test_map_{i}.scmap")

            # Build twice with same seed
            output_dir1 = Path(tmpdir) / "dataset1"
            builder1 = DatasetBuilder(output_dir=output_dir1, seed=42)
            builder1.build(input_dir)

            output_dir2 = Path(tmpdir) / "dataset2"
            builder2 = DatasetBuilder(output_dir=output_dir2, seed=42)
            builder2.build(input_dir)

            with open(output_dir1 / "splits.json") as f:
                splits1 = json.load(f)
            with open(output_dir2 / "splits.json") as f:
                splits2 = json.load(f)

            assert splits1["train"] == splits2["train"]
            assert splits1["val"] == splits2["val"]
            assert splits1["test"] == splits2["test"]

    def test_splits_differ_with_different_seeds(self) -> None:
        """Splits should differ with different seeds."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir = Path(tmpdir) / "input"

            import shutil

            for i in range(10):
                map_dir = input_dir / f"test_map_{i}.v0001"
                map_dir.mkdir(parents=True)
                shutil.copy(FIXTURE_PATH, map_dir / f"test_map_{i}.scmap")

            # Build with different seeds
            output_dir1 = Path(tmpdir) / "dataset1"
            builder1 = DatasetBuilder(output_dir=output_dir1, seed=42)
            builder1.build(input_dir)

            output_dir2 = Path(tmpdir) / "dataset2"
            builder2 = DatasetBuilder(output_dir=output_dir2, seed=123)
            builder2.build(input_dir)

            with open(output_dir1 / "splits.json") as f:
                splits1 = json.load(f)
            with open(output_dir2 / "splits.json") as f:
                splits2 = json.load(f)

            # At least one split should differ
            assert (
                splits1["train"] != splits2["train"]
                or splits1["val"] != splits2["val"]
                or splits1["test"] != splits2["test"]
            )


class TestDatasetBuilderErrorHandling:
    """Tests for error handling in DatasetBuilder."""

    def test_build_handles_corrupted_map(self) -> None:
        """Build should skip corrupted maps and continue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "corrupted_map.v0001"
            map_dir.mkdir(parents=True)

            # Create an invalid scmap file
            (map_dir / "corrupted_map.scmap").write_bytes(b"not a valid scmap")

            builder = DatasetBuilder(output_dir=output_dir)
            result = builder.build(input_dir)

            assert result.failed == 1
            assert result.processed == 0

    def test_build_creates_errors_json_on_failures(self) -> None:
        """Build should create errors.json when maps fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "corrupted_map.v0001"
            map_dir.mkdir(parents=True)

            (map_dir / "corrupted_map.scmap").write_bytes(b"not a valid scmap")

            builder = DatasetBuilder(output_dir=output_dir)
            builder.build(input_dir)

            errors_path = output_dir / "errors.json"
            assert errors_path.exists()

            with open(errors_path) as f:
                errors = json.load(f)

            assert "errors" in errors
            assert len(errors["errors"]) == 1


class TestDatasetBuilderProgress:
    """Tests for progress callback in DatasetBuilder."""

    def test_build_calls_progress_callback(self) -> None:
        """Build should call progress callback during processing."""
        if not FIXTURE_PATH.exists():
            pytest.skip("Test fixture not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "dataset"
            input_dir = Path(tmpdir) / "input"
            map_dir = input_dir / "test_map.v0001"
            map_dir.mkdir(parents=True)

            import shutil

            shutil.copy(FIXTURE_PATH, map_dir / "test_map.scmap")

            callback_calls: list[BuildProgress] = []

            def progress_callback(progress: BuildProgress) -> None:
                callback_calls.append(
                    BuildProgress(
                        total=progress.total,
                        processed=progress.processed,
                        failed=progress.failed,
                        skipped=progress.skipped,
                        current_map=progress.current_map,
                    )
                )

            builder = DatasetBuilder(output_dir=output_dir, progress_callback=progress_callback)
            builder.build(input_dir)

            assert len(callback_calls) > 0


class TestSampleMetadata:
    """Tests for SampleMetadata dataclass."""

    def test_sample_metadata_fields(self) -> None:
        """SampleMetadata should have all expected fields."""
        metadata = SampleMetadata(
            sample_id="test_map_v0001",
            original_path="/path/to/test_map.scmap",
            map_size=256,
            map_size_km=5,
            terrain_type="temperate",
            has_water=True,
            water_elevation=25.0,
            heightmap_shape=(257, 257),
            heightmap_file="heightmaps/test_map_v0001.npy",
        )

        assert metadata.sample_id == "test_map_v0001"
        assert metadata.map_size == 256
        assert metadata.terrain_type == "temperate"
        assert metadata.heightmap_shape == (257, 257)


class TestBuildResult:
    """Tests for BuildResult dataclass."""

    def test_build_result_fields(self) -> None:
        """BuildResult should have all expected fields."""
        result = BuildResult(
            output_dir=Path("/data/dataset"),
            total_samples=100,
            processed=95,
            failed=3,
            skipped=2,
            split_counts={"train": 76, "val": 10, "test": 9},
        )

        assert result.total_samples == 100
        assert result.processed == 95
        assert result.failed == 3
        assert result.skipped == 2
        assert result.split_counts["train"] == 76
