"""Unit tests for heightmap normalization functions."""

import numpy as np
import pytest

from faf.preprocessing.normalize import (
    UINT16_MAX,
    denormalize_heightmap,
    normalize_heightmap,
)


class TestNormalizeHeightmap:
    """Tests for normalize_heightmap function."""

    def test_normalize_heightmap_returns_float32(self) -> None:
        """Normalized heightmap should have float32 dtype."""
        raw = np.array([[0, 1000], [2000, 3000]], dtype=np.uint16)
        result = normalize_heightmap(raw)
        assert result.dtype == np.float32

    def test_normalize_heightmap_preserves_shape(self) -> None:
        """Normalized heightmap should have same shape as input."""
        raw = np.array([[0, 1000, 2000], [3000, 4000, 5000]], dtype=np.uint16)
        result = normalize_heightmap(raw)
        assert result.shape == raw.shape

    def test_normalize_heightmap_range_zero_to_one(self) -> None:
        """Normalized values should be in [0, 1] range."""
        raw = np.array([[0, 32767], [32768, 65535]], dtype=np.uint16)
        result = normalize_heightmap(raw)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_normalize_heightmap_zero_stays_zero(self) -> None:
        """Zero values should normalize to 0.0."""
        raw = np.array([[0]], dtype=np.uint16)
        result = normalize_heightmap(raw)
        assert result[0, 0] == 0.0

    def test_normalize_heightmap_max_becomes_one(self) -> None:
        """Maximum uint16 value should normalize to 1.0."""
        raw = np.array([[65535]], dtype=np.uint16)
        result = normalize_heightmap(raw)
        assert result[0, 0] == 1.0

    def test_normalize_heightmap_midpoint(self) -> None:
        """Midpoint value should normalize to approximately 0.5."""
        raw = np.array([[32767]], dtype=np.uint16)
        result = normalize_heightmap(raw)
        # Allow small floating point error
        assert abs(result[0, 0] - 0.5) < 0.0001

    def test_normalize_heightmap_raises_on_wrong_dtype(self) -> None:
        """Should raise ValueError for non-uint16 arrays."""
        raw = np.array([[0, 1000]], dtype=np.int32)
        with pytest.raises(ValueError, match="Expected uint16"):
            normalize_heightmap(raw)

    def test_normalize_heightmap_raises_on_float_input(self) -> None:
        """Should raise ValueError for float arrays."""
        raw = np.array([[0.0, 1000.0]], dtype=np.float32)
        with pytest.raises(ValueError, match="Expected uint16"):
            normalize_heightmap(raw)


class TestDenormalizeHeightmap:
    """Tests for denormalize_heightmap function."""

    def test_denormalize_heightmap_returns_uint16(self) -> None:
        """Denormalized heightmap should have uint16 dtype."""
        normalized = np.array([[0.0, 0.5], [0.75, 1.0]], dtype=np.float32)
        result = denormalize_heightmap(normalized)
        assert result.dtype == np.uint16

    def test_denormalize_heightmap_preserves_shape(self) -> None:
        """Denormalized heightmap should have same shape as input."""
        normalized = np.array([[0.0, 0.5, 1.0], [0.25, 0.75, 0.9]], dtype=np.float32)
        result = denormalize_heightmap(normalized)
        assert result.shape == normalized.shape

    def test_denormalize_heightmap_zero_stays_zero(self) -> None:
        """Zero should denormalize to 0."""
        normalized = np.array([[0.0]], dtype=np.float32)
        result = denormalize_heightmap(normalized)
        assert result[0, 0] == 0

    def test_denormalize_heightmap_one_becomes_max(self) -> None:
        """1.0 should denormalize to 65535."""
        normalized = np.array([[1.0]], dtype=np.float32)
        result = denormalize_heightmap(normalized)
        assert result[0, 0] == UINT16_MAX

    def test_denormalize_heightmap_raises_on_wrong_dtype(self) -> None:
        """Should raise ValueError for non-float32 arrays."""
        normalized = np.array([[0.0, 0.5]], dtype=np.float64)
        with pytest.raises(ValueError, match="Expected float32"):
            denormalize_heightmap(normalized)

    def test_denormalize_heightmap_clips_negative(self) -> None:
        """Values below 0 should be clipped to 0."""
        normalized = np.array([[-0.1]], dtype=np.float32)
        result = denormalize_heightmap(normalized)
        assert result[0, 0] == 0

    def test_denormalize_heightmap_clips_above_one(self) -> None:
        """Values above 1 should be clipped to 65535."""
        normalized = np.array([[1.1]], dtype=np.float32)
        result = denormalize_heightmap(normalized)
        assert result[0, 0] == UINT16_MAX


class TestRoundTrip:
    """Tests for normalize/denormalize round-trip behavior."""

    def test_roundtrip_preserves_values(self) -> None:
        """Normalizing and denormalizing should preserve original values."""
        original = np.array([[0, 1000, 32767, 50000, 65535]], dtype=np.uint16)
        normalized = normalize_heightmap(original)
        recovered = denormalize_heightmap(normalized)
        np.testing.assert_array_equal(original, recovered)

    def test_roundtrip_large_array(self) -> None:
        """Round-trip should work for large arrays."""
        # Simulate a typical heightmap size (257x257)
        original = np.random.randint(0, 65536, size=(257, 257), dtype=np.uint16)
        normalized = normalize_heightmap(original)
        recovered = denormalize_heightmap(normalized)
        np.testing.assert_array_equal(original, recovered)
