"""Dataset validation for preprocessed FAF map datasets.

This module provides functionality to validate the integrity and correctness
of preprocessed datasets, checking heightmap values, dimensions, and splits.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SampleError:
    """Error information for a single sample.

    Attributes:
        sample_id: The ID of the sample with errors.
        errors: List of error messages for this sample.
    """

    sample_id: str
    errors: list[str]


@dataclass
class ValidationReport:
    """Report from validating a dataset.

    Attributes:
        valid: Whether the dataset passed all validation checks.
        timestamp: When the validation was performed.
        dataset_path: Path to the validated dataset.
        total_samples: Total number of samples in the dataset.
        valid_samples: Number of samples that passed validation.
        invalid_samples: Number of samples with errors.
        sample_errors: List of errors for each invalid sample.
        split_errors: List of errors related to data splits.
        metadata_errors: List of errors related to metadata.json.
    """

    valid: bool
    timestamp: str
    dataset_path: str
    total_samples: int
    valid_samples: int
    invalid_samples: int
    sample_errors: list[SampleError] = field(default_factory=list)
    split_errors: list[str] = field(default_factory=list)
    metadata_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "valid": self.valid,
            "timestamp": self.timestamp,
            "dataset_path": self.dataset_path,
            "total_samples": self.total_samples,
            "valid_samples": self.valid_samples,
            "invalid_samples": self.invalid_samples,
            "errors": [{"sample_id": e.sample_id, "errors": e.errors} for e in self.sample_errors],
            "split_errors": self.split_errors,
            "metadata_errors": self.metadata_errors,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class DatasetValidator:
    """Validator for preprocessed FAF map datasets.

    This class validates the integrity of datasets created by DatasetBuilder,
    checking that heightmaps are correctly formatted, values are in range,
    and splits are properly constructed.

    Args:
        dataset_path: Path to the dataset directory to validate.

    Example:
        >>> validator = DatasetValidator(Path("/data/dataset"))
        >>> report = validator.validate()
        >>> if report.valid:
        ...     print("Dataset is valid!")
        ... else:
        ...     print(f"Found {report.invalid_samples} invalid samples")
    """

    def __init__(self, dataset_path: Path):
        self.dataset_path = Path(dataset_path)
        self.metadata: Optional[dict] = None
        self.splits: Optional[dict] = None

    def validate(self) -> ValidationReport:
        """Validate the entire dataset.

        Returns:
            ValidationReport with validation results.

        Raises:
            FileNotFoundError: If the dataset directory doesn't exist.
        """
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")

        timestamp = datetime.now(timezone.utc).isoformat()
        sample_errors: list[SampleError] = []
        split_errors: list[str] = []
        metadata_errors: list[str] = []

        # Load and validate metadata
        metadata_errors.extend(self._load_and_validate_metadata())
        if self.metadata is None:
            return ValidationReport(
                valid=False,
                timestamp=timestamp,
                dataset_path=str(self.dataset_path),
                total_samples=0,
                valid_samples=0,
                invalid_samples=0,
                sample_errors=[],
                split_errors=[],
                metadata_errors=metadata_errors,
            )

        # Load and validate splits
        split_errors.extend(self._load_and_validate_splits())

        # Validate each sample
        samples = self.metadata.get("samples", {})
        for sample_id, sample_meta in samples.items():
            errors = self._validate_sample(sample_id, sample_meta)
            if errors:
                sample_errors.append(SampleError(sample_id=sample_id, errors=errors))

        total_samples = len(samples)
        invalid_samples = len(sample_errors)
        valid_samples = total_samples - invalid_samples

        is_valid = len(metadata_errors) == 0 and len(split_errors) == 0 and invalid_samples == 0

        return ValidationReport(
            valid=is_valid,
            timestamp=timestamp,
            dataset_path=str(self.dataset_path),
            total_samples=total_samples,
            valid_samples=valid_samples,
            invalid_samples=invalid_samples,
            sample_errors=sample_errors,
            split_errors=split_errors,
            metadata_errors=metadata_errors,
        )

    def _load_and_validate_metadata(self) -> list[str]:
        """Load and validate metadata.json.

        Returns:
            List of error messages, empty if valid.
        """
        errors: list[str] = []
        metadata_path = self.dataset_path / "metadata.json"

        if not metadata_path.exists():
            errors.append("metadata.json not found")
            return errors

        try:
            with open(metadata_path) as f:
                self.metadata = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"metadata.json is not valid JSON: {e}")
            return errors

        # Validate required fields
        required_fields = ["version", "total_samples", "samples"]
        for field_name in required_fields:
            if field_name not in self.metadata:
                errors.append(f"metadata.json missing required field: {field_name}")

        if "samples" in self.metadata:
            if not isinstance(self.metadata["samples"], dict):
                errors.append("metadata.json 'samples' should be a dictionary")

        return errors

    def _load_and_validate_splits(self) -> list[str]:
        """Load and validate splits.json.

        Returns:
            List of error messages, empty if valid.
        """
        errors: list[str] = []
        splits_path = self.dataset_path / "splits.json"

        if not splits_path.exists():
            errors.append("splits.json not found")
            return errors

        try:
            with open(splits_path) as f:
                self.splits = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"splits.json is not valid JSON: {e}")
            return errors

        # Validate required fields
        required_fields = ["train", "val", "test"]
        for field_name in required_fields:
            if field_name not in self.splits:
                errors.append(f"splits.json missing required field: {field_name}")
                return errors

        # Validate splits
        if self.metadata and "samples" in self.metadata:
            all_samples = set(self.metadata["samples"].keys())
            errors.extend(self._validate_splits(self.splits, all_samples))

        return errors

    def _validate_splits(self, splits: dict, all_samples: set[str]) -> list[str]:
        """Validate train/val/test splits.

        Args:
            splits: Dictionary with train/val/test lists.
            all_samples: Set of all sample IDs from metadata.

        Returns:
            List of error messages, empty if valid.
        """
        errors: list[str] = []

        train = set(splits.get("train", []))
        val = set(splits.get("val", []))
        test = set(splits.get("test", []))

        # Check disjoint
        train_val_overlap = train & val
        if train_val_overlap:
            errors.append(f"Train/val overlap: {sorted(train_val_overlap)}")

        train_test_overlap = train & test
        if train_test_overlap:
            errors.append(f"Train/test overlap: {sorted(train_test_overlap)}")

        val_test_overlap = val & test
        if val_test_overlap:
            errors.append(f"Val/test overlap: {sorted(val_test_overlap)}")

        # Check coverage
        split_union = train | val | test
        missing = all_samples - split_union
        if missing:
            errors.append(f"Samples not in any split: {sorted(missing)}")

        extra = split_union - all_samples
        if extra:
            errors.append(f"Unknown samples in splits: {sorted(extra)}")

        return errors

    def _validate_sample(self, sample_id: str, sample_meta: dict) -> list[str]:
        """Validate a single sample.

        Args:
            sample_id: The sample ID.
            sample_meta: Metadata dictionary for this sample.

        Returns:
            List of error messages, empty if valid.
        """
        errors: list[str] = []

        # Get expected shape from metadata
        heightmap_shape = sample_meta.get("heightmap_shape")
        if heightmap_shape is None:
            errors.append("Missing heightmap_shape in metadata")
            return errors

        expected_shape = tuple(heightmap_shape)

        # Get heightmap path
        heightmap_file = sample_meta.get("heightmap_file")
        if heightmap_file is None:
            errors.append("Missing heightmap_file in metadata")
            return errors

        heightmap_path = self.dataset_path / heightmap_file

        # Validate heightmap
        errors.extend(self._validate_heightmap(heightmap_path, expected_shape))

        return errors

    def _validate_heightmap(self, path: Path, expected_shape: tuple[int, int]) -> list[str]:
        """Validate a heightmap file.

        Args:
            path: Path to the .npy heightmap file.
            expected_shape: Expected shape from metadata.

        Returns:
            List of error messages, empty if valid.
        """
        errors: list[str] = []

        if not path.exists():
            errors.append(f"Heightmap file not found: {path}")
            return errors

        try:
            hm = np.load(path)

            if hm.dtype != np.float32:
                errors.append(f"Wrong dtype: {hm.dtype}, expected float32")

            if hm.shape != expected_shape:
                errors.append(f"Wrong shape: {hm.shape}, expected {expected_shape}")

            if hm.size > 0:
                if hm.min() < 0:
                    errors.append(f"Values below 0: min={hm.min():.6f}")
                if hm.max() > 1:
                    errors.append(f"Values above 1: max={hm.max():.6f}")

        except Exception as e:
            errors.append(f"Failed to load heightmap: {e}")

        return errors


def validate_heightmap(path: Path, expected_shape: tuple[int, int]) -> list[str]:
    """Validate a heightmap file.

    Convenience function for validating a single heightmap.

    Args:
        path: Path to the .npy heightmap file.
        expected_shape: Expected (height, width) shape.

    Returns:
        List of error messages, empty if valid.
    """
    validator = DatasetValidator(path.parent.parent)
    return validator._validate_heightmap(path, expected_shape)


def validate_splits(splits: dict, all_samples: set[str]) -> list[str]:
    """Validate train/val/test splits.

    Convenience function for validating splits.

    Args:
        splits: Dictionary with train/val/test lists.
        all_samples: Set of all sample IDs.

    Returns:
        List of error messages, empty if valid.
    """
    validator = DatasetValidator(Path("."))
    return validator._validate_splits(splits, all_samples)
