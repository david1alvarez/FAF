"""Integration tests for FAF API client (requires network access).

These tests query the real FAF API.
Run with: pytest tests/python/api/test_client_integration.py -v -m integration

Note: The FAF API may require OAuth authentication. If tests fail with 403 errors,
authentication tokens may be needed. See FAF documentation for details.
"""

import pytest

from faf.api.client import FAFApiClient, FAFApiError, MapListResult, MapMetadata

pytestmark = pytest.mark.integration


def api_accessible() -> bool:
    """Check if the FAF API is accessible without authentication."""
    try:
        client = FAFApiClient(max_retries=1)
        client.list_maps(page_size=1, page=1)
        return True
    except FAFApiError as e:
        if e.status_code == 403:
            return False
        raise


# Skip all tests if API requires authentication
requires_api = pytest.mark.skipif(
    not api_accessible(),
    reason="FAF API requires authentication (HTTP 403)",
)


@requires_api
class TestFAFApiClientIntegration:
    """Integration tests that query the real FAF API."""

    def test_list_maps_returns_real_data(self) -> None:
        """Should successfully query the FAF API and return maps."""
        client = FAFApiClient()
        result = client.list_maps(page_size=10, page=1)

        assert isinstance(result, MapListResult)
        assert result.total_records > 0
        assert len(result.maps) > 0
        assert len(result.maps) <= 10

    def test_list_maps_returns_valid_metadata(self) -> None:
        """Should return maps with valid metadata fields."""
        client = FAFApiClient()
        result = client.list_maps(page_size=5, page=1)

        assert len(result.maps) > 0
        for map_meta in result.maps:
            assert isinstance(map_meta, MapMetadata)
            assert map_meta.id
            assert map_meta.display_name
            assert map_meta.map_size > 0
            assert map_meta.player_count > 0
            assert map_meta.download_url

    def test_list_maps_pagination_works(self) -> None:
        """Should return different results for different pages."""
        client = FAFApiClient()

        page1 = client.list_maps(page_size=5, page=1)
        page2 = client.list_maps(page_size=5, page=2)

        assert len(page1.maps) > 0
        assert len(page2.maps) > 0

        page1_ids = {m.id for m in page1.maps}
        page2_ids = {m.id for m in page2.maps}
        assert page1_ids.isdisjoint(page2_ids), "Pages should have different maps"

    def test_list_maps_player_filter_works(self) -> None:
        """Should filter maps by player count."""
        client = FAFApiClient()
        result = client.list_maps(page_size=20, player_count=8)

        assert len(result.maps) > 0
        for map_meta in result.maps:
            assert map_meta.player_count == 8

    def test_iter_all_maps_limited(self) -> None:
        """Should iterate through maps with max_pages limit."""
        client = FAFApiClient()
        maps = list(client.iter_all_maps(page_size=5, max_pages=2))

        assert len(maps) == 10
        assert all(isinstance(m, MapMetadata) for m in maps)
