"""Unit tests for dataset statistics."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from faf.preprocessing.stats import (
    DatasetStatistics,
    DatasetStats,
    HeightmapStats,
)


class TestDatasetStats:
    """Tests for DatasetStats class."""

    def test_stats_raises_on_nonexistent_path(self) -> None:
        """Should raise FileNotFoundError for nonexistent dataset."""
        stats = DatasetStats(Path("/nonexistent/dataset"))
        with pytest.raises(FileNotFoundError):
            stats.compute()

    def test_stats_raises_on_missing_metadata(self) -> None:
        """Should raise FileNotFoundError for missing metadata.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats = DatasetStats(Path(tmpdir))
            with pytest.raises(FileNotFoundError, match="metadata.json"):
                stats.compute()

    def test_stats_computes_total_samples(self) -> None:
        """Should compute total sample count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            metadata = {
                "version": "1.0",
                "total_samples": 3,
                "samples": {
                    "a": {"map_size": 256},
                    "b": {"map_size": 512},
                    "c": {"map_size": 256},
                },
            }
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            stats = DatasetStats(dataset_path, compute_heightmap_stats=False)
            result = stats.compute()

            assert result.total_samples == 3

    def test_stats_computes_split_counts(self) -> None:
        """Should compute split counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            metadata = {"version": "1.0", "total_samples": 4, "samples": {}}
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            splits = {"train": ["a", "b"], "val": ["c"], "test": ["d"]}
            (dataset_path / "splits.json").write_text(json.dumps(splits))

            stats = DatasetStats(dataset_path, compute_heightmap_stats=False)
            result = stats.compute()

            assert result.split_counts["train"] == 2
            assert result.split_counts["val"] == 1
            assert result.split_counts["test"] == 1

    def test_stats_computes_map_size_distribution(self) -> None:
        """Should compute map size distribution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            metadata = {
                "version": "1.0",
                "total_samples": 4,
                "samples": {
                    "a": {"map_size": 256},
                    "b": {"map_size": 256},
                    "c": {"map_size": 512},
                    "d": {"map_size": 1024},
                },
            }
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            stats = DatasetStats(dataset_path, compute_heightmap_stats=False)
            result = stats.compute()

            assert result.map_sizes[256] == 2
            assert result.map_sizes[512] == 1
            assert result.map_sizes[1024] == 1

    def test_stats_computes_terrain_distribution(self) -> None:
        """Should compute terrain type distribution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            metadata = {
                "version": "1.0",
                "total_samples": 4,
                "samples": {
                    "a": {"terrain_type": "temperate"},
                    "b": {"terrain_type": "temperate"},
                    "c": {"terrain_type": "desert"},
                    "d": {"terrain_type": "lava"},
                },
            }
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            stats = DatasetStats(dataset_path, compute_heightmap_stats=False)
            result = stats.compute()

            assert result.terrain_types["temperate"] == 2
            assert result.terrain_types["desert"] == 1
            assert result.terrain_types["lava"] == 1

    def test_stats_computes_water_counts(self) -> None:
        """Should compute water counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            metadata = {
                "version": "1.0",
                "total_samples": 4,
                "samples": {
                    "a": {"has_water": True},
                    "b": {"has_water": True},
                    "c": {"has_water": False},
                    "d": {"has_water": True},
                },
            }
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            stats = DatasetStats(dataset_path, compute_heightmap_stats=False)
            result = stats.compute()

            assert result.water_counts["with_water"] == 3
            assert result.water_counts["without_water"] == 1

    def test_stats_computes_heightmap_statistics(self) -> None:
        """Should compute heightmap statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            (dataset_path / "heightmaps").mkdir()

            # Create heightmaps with known values
            hm1 = np.array([[0.2, 0.4], [0.4, 0.6]], dtype=np.float32)  # mean=0.4
            hm2 = np.array([[0.3, 0.5], [0.5, 0.7]], dtype=np.float32)  # mean=0.5
            np.save(dataset_path / "heightmaps" / "a.npy", hm1)
            np.save(dataset_path / "heightmaps" / "b.npy", hm2)

            metadata = {
                "version": "1.0",
                "total_samples": 2,
                "samples": {
                    "a": {"heightmap_file": "heightmaps/a.npy"},
                    "b": {"heightmap_file": "heightmaps/b.npy"},
                },
            }
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            stats = DatasetStats(dataset_path, compute_heightmap_stats=True)
            result = stats.compute()

            assert result.heightmap_stats is not None
            assert 0.4 <= result.heightmap_stats.mean <= 0.5
            # Use tolerance for floating point comparisons
            assert abs(result.heightmap_stats.min_value - 0.2) < 0.001
            assert abs(result.heightmap_stats.max_value - 0.7) < 0.001

    def test_stats_skips_heightmap_stats_when_disabled(self) -> None:
        """Should skip heightmap stats when compute_heightmap_stats=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            metadata = {"version": "1.0", "total_samples": 0, "samples": {}}
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            stats = DatasetStats(dataset_path, compute_heightmap_stats=False)
            result = stats.compute()

            assert result.heightmap_stats is None


class TestDatasetStatistics:
    """Tests for DatasetStatistics dataclass."""

    def test_statistics_to_dict(self) -> None:
        """Should convert statistics to dictionary."""
        stats = DatasetStatistics(
            dataset_path="/data/dataset",
            total_samples=100,
            split_counts={"train": 80, "val": 10, "test": 10},
            map_sizes={256: 50, 512: 50},
            terrain_types={"temperate": 60, "desert": 40},
            water_counts={"with_water": 75, "without_water": 25},
        )

        d = stats.to_dict()
        assert d["total_samples"] == 100
        assert d["splits"]["train"] == 80
        assert d["map_sizes"]["256"] == 50

    def test_statistics_to_json(self) -> None:
        """Should convert statistics to JSON string."""
        stats = DatasetStatistics(
            dataset_path="/data/dataset",
            total_samples=10,
        )

        json_str = stats.to_json()
        parsed = json.loads(json_str)
        assert parsed["total_samples"] == 10

    def test_statistics_format_human_readable(self) -> None:
        """Should format statistics as human-readable text."""
        stats = DatasetStatistics(
            dataset_path="/data/dataset",
            total_samples=100,
            split_counts={"train": 80, "val": 10, "test": 10},
            map_sizes={256: 50, 512: 50},
            terrain_types={"temperate": 60, "desert": 40},
            water_counts={"with_water": 75, "without_water": 25},
            heightmap_stats=HeightmapStats(mean=0.4, std=0.2, min_value=0.0, max_value=1.0),
        )

        text = stats.format_human_readable()

        assert "Dataset Statistics" in text
        assert "100 total" in text
        assert "Train" in text
        assert "Map Sizes" in text
        assert "Terrain Types" in text
        assert "Heightmap Stats" in text
        assert "Water" in text

    def test_statistics_human_readable_empty_dataset(self) -> None:
        """Should handle empty dataset gracefully."""
        stats = DatasetStatistics(
            dataset_path="/data/dataset",
            total_samples=0,
        )

        text = stats.format_human_readable()
        assert "0 total" in text


class TestHeightmapStats:
    """Tests for HeightmapStats dataclass."""

    def test_heightmap_stats_to_dict(self) -> None:
        """Should convert to dictionary."""
        stats = HeightmapStats(mean=0.5, std=0.2, min_value=0.0, max_value=1.0)

        d = stats.to_dict()
        assert d["mean"] == 0.5
        assert d["std"] == 0.2
        assert d["min"] == 0.0
        assert d["max"] == 1.0
