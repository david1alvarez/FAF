"""Unit tests for dataset validation."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from faf.preprocessing.validate import (
    DatasetValidator,
    SampleError,
    ValidationReport,
    validate_heightmap,
    validate_splits,
)


class TestValidateHeightmap:
    """Tests for heightmap validation."""

    def test_validate_heightmap_valid(self) -> None:
        """Valid heightmap should return no errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hm_path = Path(tmpdir) / "heightmaps" / "test.npy"
            hm_path.parent.mkdir()
            hm = np.array([[0.0, 0.5], [0.5, 1.0]], dtype=np.float32)
            np.save(hm_path, hm)

            errors = validate_heightmap(hm_path, (2, 2))
            assert errors == []

    def test_validate_heightmap_wrong_dtype(self) -> None:
        """Should detect wrong dtype."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hm_path = Path(tmpdir) / "heightmaps" / "test.npy"
            hm_path.parent.mkdir()
            # Use values in [0, 1] range to only trigger dtype error
            hm = np.array([[0, 1], [0, 1]], dtype=np.int32)
            np.save(hm_path, hm)

            errors = validate_heightmap(hm_path, (2, 2))
            assert len(errors) >= 1
            assert any("Wrong dtype" in e for e in errors)

    def test_validate_heightmap_wrong_shape(self) -> None:
        """Should detect wrong shape."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hm_path = Path(tmpdir) / "heightmaps" / "test.npy"
            hm_path.parent.mkdir()
            hm = np.array([[0.0, 0.5, 1.0]], dtype=np.float32)
            np.save(hm_path, hm)

            errors = validate_heightmap(hm_path, (2, 2))
            assert len(errors) == 1
            assert "Wrong shape" in errors[0]

    def test_validate_heightmap_values_below_zero(self) -> None:
        """Should detect values below 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hm_path = Path(tmpdir) / "heightmaps" / "test.npy"
            hm_path.parent.mkdir()
            hm = np.array([[-0.1, 0.5]], dtype=np.float32)
            np.save(hm_path, hm)

            errors = validate_heightmap(hm_path, (1, 2))
            assert len(errors) == 1
            assert "below 0" in errors[0]

    def test_validate_heightmap_values_above_one(self) -> None:
        """Should detect values above 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hm_path = Path(tmpdir) / "heightmaps" / "test.npy"
            hm_path.parent.mkdir()
            hm = np.array([[0.5, 1.1]], dtype=np.float32)
            np.save(hm_path, hm)

            errors = validate_heightmap(hm_path, (1, 2))
            assert len(errors) == 1
            assert "above 1" in errors[0]

    def test_validate_heightmap_file_not_found(self) -> None:
        """Should report missing file."""
        errors = validate_heightmap(Path("/nonexistent/file.npy"), (2, 2))
        assert len(errors) == 1
        assert "not found" in errors[0]


class TestValidateSplits:
    """Tests for split validation."""

    def test_validate_splits_valid(self) -> None:
        """Valid splits should return no errors."""
        splits = {"train": ["a", "b"], "val": ["c"], "test": ["d"]}
        all_samples = {"a", "b", "c", "d"}
        errors = validate_splits(splits, all_samples)
        assert errors == []

    def test_validate_splits_train_val_overlap(self) -> None:
        """Should detect train/val overlap."""
        splits = {"train": ["a", "b"], "val": ["b", "c"], "test": ["d"]}
        all_samples = {"a", "b", "c", "d"}
        errors = validate_splits(splits, all_samples)
        assert len(errors) == 1
        assert "Train/val overlap" in errors[0]

    def test_validate_splits_train_test_overlap(self) -> None:
        """Should detect train/test overlap."""
        splits = {"train": ["a", "b"], "val": ["c"], "test": ["a", "d"]}
        all_samples = {"a", "b", "c", "d"}
        errors = validate_splits(splits, all_samples)
        assert len(errors) == 1
        assert "Train/test overlap" in errors[0]

    def test_validate_splits_val_test_overlap(self) -> None:
        """Should detect val/test overlap."""
        splits = {"train": ["a", "b"], "val": ["c", "d"], "test": ["d"]}
        all_samples = {"a", "b", "c", "d"}
        errors = validate_splits(splits, all_samples)
        assert len(errors) == 1
        assert "Val/test overlap" in errors[0]

    def test_validate_splits_missing_samples(self) -> None:
        """Should detect samples not in any split."""
        splits = {"train": ["a"], "val": ["b"], "test": ["c"]}
        all_samples = {"a", "b", "c", "d"}
        errors = validate_splits(splits, all_samples)
        assert len(errors) == 1
        assert "not in any split" in errors[0]

    def test_validate_splits_unknown_samples(self) -> None:
        """Should detect unknown samples in splits."""
        splits = {"train": ["a", "x"], "val": ["b"], "test": ["c"]}
        all_samples = {"a", "b", "c"}
        errors = validate_splits(splits, all_samples)
        assert len(errors) == 1
        assert "Unknown samples" in errors[0]


class TestDatasetValidator:
    """Tests for DatasetValidator class."""

    def test_validator_raises_on_nonexistent_path(self) -> None:
        """Should raise FileNotFoundError for nonexistent dataset."""
        validator = DatasetValidator(Path("/nonexistent/dataset"))
        with pytest.raises(FileNotFoundError):
            validator.validate()

    def test_validator_reports_missing_metadata(self) -> None:
        """Should report missing metadata.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = DatasetValidator(Path(tmpdir))
            report = validator.validate()

            assert not report.valid
            assert any("metadata.json not found" in e for e in report.metadata_errors)

    def test_validator_reports_invalid_metadata_json(self) -> None:
        """Should report invalid JSON in metadata.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "metadata.json").write_text("not valid json")
            validator = DatasetValidator(Path(tmpdir))
            report = validator.validate()

            assert not report.valid
            assert any("not valid JSON" in e for e in report.metadata_errors)

    def test_validator_reports_missing_splits(self) -> None:
        """Should report missing splits.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = {"version": "1.0", "total_samples": 0, "samples": {}}
            (Path(tmpdir) / "metadata.json").write_text(json.dumps(metadata))
            validator = DatasetValidator(Path(tmpdir))
            report = validator.validate()

            assert not report.valid
            assert any("splits.json not found" in e for e in report.split_errors)

    def test_validator_validates_full_dataset(self) -> None:
        """Should validate a complete dataset structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)

            # Create valid dataset structure
            (dataset_path / "heightmaps").mkdir()
            hm = np.array([[0.3, 0.5], [0.5, 0.7]], dtype=np.float32)
            np.save(dataset_path / "heightmaps" / "sample_a.npy", hm)

            metadata = {
                "version": "1.0",
                "total_samples": 1,
                "samples": {
                    "sample_a": {
                        "heightmap_shape": [2, 2],
                        "heightmap_file": "heightmaps/sample_a.npy",
                    }
                },
            }
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            splits = {"train": ["sample_a"], "val": [], "test": []}
            (dataset_path / "splits.json").write_text(json.dumps(splits))

            validator = DatasetValidator(dataset_path)
            report = validator.validate()

            assert report.valid
            assert report.total_samples == 1
            assert report.valid_samples == 1
            assert report.invalid_samples == 0

    def test_validator_detects_invalid_heightmap(self) -> None:
        """Should detect invalid heightmap in dataset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)

            # Create dataset with invalid heightmap
            (dataset_path / "heightmaps").mkdir()
            hm = np.array([[1.5, 0.5]], dtype=np.float32)  # Value > 1
            np.save(dataset_path / "heightmaps" / "bad_sample.npy", hm)

            metadata = {
                "version": "1.0",
                "total_samples": 1,
                "samples": {
                    "bad_sample": {
                        "heightmap_shape": [1, 2],
                        "heightmap_file": "heightmaps/bad_sample.npy",
                    }
                },
            }
            (dataset_path / "metadata.json").write_text(json.dumps(metadata))

            splits = {"train": ["bad_sample"], "val": [], "test": []}
            (dataset_path / "splits.json").write_text(json.dumps(splits))

            validator = DatasetValidator(dataset_path)
            report = validator.validate()

            assert not report.valid
            assert report.invalid_samples == 1
            assert len(report.sample_errors) == 1
            assert report.sample_errors[0].sample_id == "bad_sample"


class TestValidationReport:
    """Tests for ValidationReport class."""

    def test_validation_report_to_dict(self) -> None:
        """Should convert report to dictionary."""
        report = ValidationReport(
            valid=True,
            timestamp="2025-01-22T10:00:00Z",
            dataset_path="/data/dataset",
            total_samples=10,
            valid_samples=10,
            invalid_samples=0,
        )

        d = report.to_dict()
        assert d["valid"] is True
        assert d["total_samples"] == 10

    def test_validation_report_to_json(self) -> None:
        """Should convert report to JSON string."""
        report = ValidationReport(
            valid=False,
            timestamp="2025-01-22T10:00:00Z",
            dataset_path="/data/dataset",
            total_samples=10,
            valid_samples=9,
            invalid_samples=1,
            sample_errors=[SampleError("bad", ["error1"])],
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["valid"] is False
        assert len(parsed["errors"]) == 1


class TestSampleError:
    """Tests for SampleError dataclass."""

    def test_sample_error_fields(self) -> None:
        """Should store sample ID and errors."""
        err = SampleError(sample_id="test_sample", errors=["error1", "error2"])
        assert err.sample_id == "test_sample"
        assert len(err.errors) == 2
