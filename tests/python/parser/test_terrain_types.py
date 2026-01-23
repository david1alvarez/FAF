"""Unit tests for terrain type inference."""

from faf.parser.terrain_types import (
    DEFAULT_TERRAIN_TYPE,
    TERRAIN_PATTERNS,
    get_all_terrain_types,
    get_terrain_keywords,
    infer_terrain_type,
)


class TestInferTerrainType:
    """Tests for infer_terrain_type function."""

    def test_infer_terrain_type_desert(self) -> None:
        """Should detect desert terrain from sand-related textures."""
        paths = [
            "/textures/terrain/sand_albedo.dds",
            "/textures/terrain/desert_rock.dds",
            "/textures/terrain/dune_normal.dds",
        ]
        assert infer_terrain_type(paths) == "desert"

    def test_infer_terrain_type_lava(self) -> None:
        """Should detect lava terrain from volcanic textures."""
        paths = [
            "/textures/terrain/lava_flow.dds",
            "/textures/terrain/volcanic_rock.dds",
            "/textures/terrain/magma_crust.dds",
        ]
        assert infer_terrain_type(paths) == "lava"

    def test_infer_terrain_type_tundra(self) -> None:
        """Should detect tundra terrain from ice/snow textures."""
        paths = [
            "/textures/terrain/snow_albedo.dds",
            "/textures/terrain/ice_normal.dds",
            "/textures/terrain/frozen_ground.dds",
        ]
        assert infer_terrain_type(paths) == "tundra"

    def test_infer_terrain_type_tropical(self) -> None:
        """Should detect tropical terrain from jungle textures."""
        paths = [
            "/textures/terrain/tropical_grass.dds",
            "/textures/terrain/jungle_floor.dds",
            "/textures/terrain/palm_dirt.dds",
        ]
        assert infer_terrain_type(paths) == "tropical"

    def test_infer_terrain_type_temperate(self) -> None:
        """Should detect temperate terrain from grass/rock textures."""
        paths = [
            "/textures/terrain/grass_albedo.dds",
            "/textures/terrain/dirt_path.dds",
            "/textures/terrain/rock_cliff.dds",
        ]
        assert infer_terrain_type(paths) == "temperate"

    def test_infer_terrain_type_seabed(self) -> None:
        """Should detect seabed terrain from underwater textures."""
        paths = [
            "/textures/terrain/seabed_sand.dds",
            "/textures/terrain/underwater_rock.dds",
            "/textures/terrain/coral_reef.dds",
        ]
        assert infer_terrain_type(paths) == "seabed"

    def test_infer_terrain_type_unknown(self) -> None:
        """Should return unknown for unrecognized texture paths."""
        paths = [
            "/textures/terrain/xyz_albedo.dds",
            "/textures/terrain/abc_normal.dds",
        ]
        assert infer_terrain_type(paths) == DEFAULT_TERRAIN_TYPE

    def test_infer_terrain_type_empty_list(self) -> None:
        """Should return unknown for empty path list."""
        assert infer_terrain_type([]) == DEFAULT_TERRAIN_TYPE

    def test_infer_terrain_type_case_insensitive(self) -> None:
        """Should match patterns regardless of case."""
        paths = [
            "/textures/terrain/SAND_ALBEDO.DDS",
            "/textures/terrain/Desert_Rock.dds",
        ]
        assert infer_terrain_type(paths) == "desert"

    def test_infer_terrain_type_highest_score_wins(self) -> None:
        """Should return terrain type with most keyword matches."""
        # More desert keywords than temperate
        paths = [
            "/textures/terrain/sand_albedo.dds",
            "/textures/terrain/desert_dune.dds",
            "/textures/terrain/grass_albedo.dds",
        ]
        assert infer_terrain_type(paths) == "desert"

    def test_infer_terrain_type_handles_none_paths(self) -> None:
        """Should handle None or empty strings in path list."""
        paths = [
            "",
            "/textures/terrain/sand_albedo.dds",
            "",
        ]
        assert infer_terrain_type(paths) == "desert"


class TestGetTerrainKeywords:
    """Tests for get_terrain_keywords function."""

    def test_get_terrain_keywords_valid_type(self) -> None:
        """Should return keywords for valid terrain type."""
        keywords = get_terrain_keywords("desert")
        assert keywords is not None
        assert "sand" in keywords
        assert "desert" in keywords

    def test_get_terrain_keywords_invalid_type(self) -> None:
        """Should return None for invalid terrain type."""
        assert get_terrain_keywords("nonexistent") is None


class TestGetAllTerrainTypes:
    """Tests for get_all_terrain_types function."""

    def test_get_all_terrain_types_returns_list(self) -> None:
        """Should return a list of terrain types."""
        types = get_all_terrain_types()
        assert isinstance(types, list)
        assert len(types) > 0

    def test_get_all_terrain_types_contains_expected(self) -> None:
        """Should contain expected terrain types."""
        types = get_all_terrain_types()
        assert "desert" in types
        assert "lava" in types
        assert "tundra" in types
        assert "temperate" in types


class TestTerrainPatterns:
    """Tests for TERRAIN_PATTERNS constant."""

    def test_terrain_patterns_is_dict(self) -> None:
        """TERRAIN_PATTERNS should be a dictionary."""
        assert isinstance(TERRAIN_PATTERNS, dict)

    def test_terrain_patterns_values_are_lists(self) -> None:
        """Each terrain type should have a list of keywords."""
        for terrain_type, keywords in TERRAIN_PATTERNS.items():
            assert isinstance(keywords, list), f"{terrain_type} should have list of keywords"
            assert len(keywords) > 0, f"{terrain_type} should have at least one keyword"
