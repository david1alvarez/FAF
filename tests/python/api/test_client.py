"""Unit tests for FAF API client with mocked responses."""

from unittest import mock

import pytest
import requests

from faf.api.client import (
    FAFApiClient,
    FAFApiError,
    MapListResult,
    MapMetadata,
)


def create_mock_response(
    maps: list[dict],
    total_records: int = 100,
    total_pages: int = 10,
    status_code: int = 200,
) -> dict:
    """Create a mock API response.

    Args:
        maps: List of map data dictionaries.
        total_records: Total records in the response metadata.
        total_pages: Total pages in the response metadata.
        status_code: HTTP status code (not used in response body).

    Returns:
        Dictionary matching the FAF API response structure.
    """
    return {
        "data": [
            {
                "type": "map",
                "id": m.get("id", "1"),
                "attributes": {
                    "displayName": m.get("displayName", "Test Map"),
                    "mapSize": m.get("mapSize", 512),
                    "maxPlayers": m.get("maxPlayers", 8),
                    "ranked": m.get("ranked", False),
                    "downloadUrl": m.get("downloadUrl", "https://example.com/map.zip"),
                    "version": m.get("version"),
                },
            }
            for m in maps
        ],
        "meta": {
            "page": {
                "totalRecords": total_records,
                "totalPages": total_pages,
            }
        },
    }


class TestFAFApiClientListMaps:
    """Tests for list_maps method."""

    def test_list_maps_returns_maplistresult(self) -> None:
        """Should return a MapListResult with correct structure."""
        client = FAFApiClient(min_request_delay=0)
        mock_data = create_mock_response(
            maps=[
                {"id": "1", "displayName": "Map One", "mapSize": 512, "maxPlayers": 4},
                {"id": "2", "displayName": "Map Two", "mapSize": 1024, "maxPlayers": 8},
            ],
            total_records=50,
            total_pages=5,
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with mock.patch("requests.get", return_value=mock_response):
            result = client.list_maps(page_size=10, page=1)

        assert isinstance(result, MapListResult)
        assert len(result.maps) == 2
        assert result.total_records == 50
        assert result.total_pages == 5
        assert result.current_page == 1

    def test_list_maps_parses_map_metadata(self) -> None:
        """Should correctly parse map metadata from response."""
        client = FAFApiClient(min_request_delay=0)
        mock_data = create_mock_response(
            maps=[
                {
                    "id": "12345",
                    "displayName": "Seton's Clutch",
                    "mapSize": 1024,
                    "maxPlayers": 8,
                    "ranked": True,
                    "downloadUrl": "https://content.faforever.com/maps/setons.zip",
                    "version": "v0001",
                }
            ]
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with mock.patch("requests.get", return_value=mock_response):
            result = client.list_maps()

        assert len(result.maps) == 1
        map_meta = result.maps[0]
        assert isinstance(map_meta, MapMetadata)
        assert map_meta.id == "12345"
        assert map_meta.display_name == "Seton's Clutch"
        assert map_meta.map_size == 1024
        assert map_meta.player_count == 8
        assert map_meta.ranked is True
        assert map_meta.download_url == "https://content.faforever.com/maps/setons.zip"
        assert map_meta.version == "v0001"

    def test_list_maps_paginates_correctly(self) -> None:
        """Should pass correct pagination parameters to API."""
        client = FAFApiClient(min_request_delay=0)
        mock_data = create_mock_response(maps=[], total_records=0, total_pages=0)

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with mock.patch("requests.get", return_value=mock_response) as mock_get:
            client.list_maps(page_size=50, page=3)

        call_args = mock_get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params["page[size]"] == "50"
        assert params["page[number]"] == "3"

    def test_list_maps_applies_size_filter(self) -> None:
        """Should apply min_size filter to API request."""
        client = FAFApiClient(min_request_delay=0)
        mock_data = create_mock_response(maps=[])

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with mock.patch("requests.get", return_value=mock_response) as mock_get:
            client.list_maps(min_size=512)

        call_args = mock_get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert "filter[mapSize]" in params
        assert "512" in params["filter[mapSize]"]

    def test_list_maps_applies_player_filter(self) -> None:
        """Should apply player_count filter to API request."""
        client = FAFApiClient(min_request_delay=0)
        mock_data = create_mock_response(maps=[])

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with mock.patch("requests.get", return_value=mock_response) as mock_get:
            client.list_maps(player_count=8)

        call_args = mock_get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params.get("filter[maxPlayers]") == "==8"

    def test_list_maps_applies_ranked_filter(self) -> None:
        """Should apply ranked filter to API request."""
        client = FAFApiClient(min_request_delay=0)
        mock_data = create_mock_response(maps=[])

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with mock.patch("requests.get", return_value=mock_response) as mock_get:
            client.list_maps(ranked=True)

        call_args = mock_get.call_args
        params = call_args.kwargs.get("params", call_args[1].get("params", {}))
        assert params.get("filter[ranked]") == "true"

    def test_list_maps_validates_page_size(self) -> None:
        """Should raise ValueError for invalid page_size."""
        client = FAFApiClient(min_request_delay=0)

        with pytest.raises(ValueError) as exc_info:
            client.list_maps(page_size=0)
        assert "page_size" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            client.list_maps(page_size=101)
        assert "page_size" in str(exc_info.value)

    def test_list_maps_validates_page_number(self) -> None:
        """Should raise ValueError for invalid page number."""
        client = FAFApiClient(min_request_delay=0)

        with pytest.raises(ValueError) as exc_info:
            client.list_maps(page=0)
        assert "page" in str(exc_info.value)


class TestFAFApiClientRetryLogic:
    """Tests for retry and rate limiting behavior."""

    def test_list_maps_handles_429_with_backoff(self) -> None:
        """Should retry with backoff on 429 rate limit response."""
        client = FAFApiClient(min_request_delay=0, max_retries=3, initial_backoff=0.01)
        mock_data = create_mock_response(maps=[{"id": "1", "displayName": "Test"}])

        rate_limit_response = mock.Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {}

        success_response = mock.Mock()
        success_response.status_code = 200
        success_response.json.return_value = mock_data

        with mock.patch(
            "requests.get",
            side_effect=[rate_limit_response, rate_limit_response, success_response],
        ):
            result = client.list_maps()

        assert len(result.maps) == 1

    def test_list_maps_fails_after_max_retries(self) -> None:
        """Should raise FAFApiError after exhausting retries."""
        client = FAFApiClient(min_request_delay=0, max_retries=3, initial_backoff=0.01)

        error_response = mock.Mock()
        error_response.status_code = 503
        error_response.headers = {}

        with mock.patch("requests.get", return_value=error_response):
            with pytest.raises(FAFApiError) as exc_info:
                client.list_maps()

        assert "3 attempts" in str(exc_info.value)

    def test_list_maps_retries_on_timeout(self) -> None:
        """Should retry on request timeout."""
        client = FAFApiClient(min_request_delay=0, max_retries=2, initial_backoff=0.01)
        mock_data = create_mock_response(maps=[{"id": "1"}])

        success_response = mock.Mock()
        success_response.status_code = 200
        success_response.json.return_value = mock_data

        with mock.patch(
            "requests.get",
            side_effect=[requests.exceptions.Timeout(), success_response],
        ):
            result = client.list_maps()

        assert len(result.maps) == 1

    def test_list_maps_raises_on_api_error(self) -> None:
        """Should raise FAFApiError for non-retryable errors."""
        client = FAFApiClient(min_request_delay=0)

        error_response = mock.Mock()
        error_response.status_code = 400

        with mock.patch("requests.get", return_value=error_response):
            with pytest.raises(FAFApiError) as exc_info:
                client.list_maps()

        assert exc_info.value.status_code == 400


class TestFAFApiClientIterAllMaps:
    """Tests for iter_all_maps generator."""

    def test_iter_all_maps_yields_all_pages(self) -> None:
        """Should iterate through all pages of results."""
        client = FAFApiClient(min_request_delay=0)

        page1_data = create_mock_response(
            maps=[{"id": "1"}, {"id": "2"}],
            total_records=4,
            total_pages=2,
        )
        page2_data = create_mock_response(
            maps=[{"id": "3"}, {"id": "4"}],
            total_records=4,
            total_pages=2,
        )

        mock_response1 = mock.Mock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = page1_data

        mock_response2 = mock.Mock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = page2_data

        with mock.patch("requests.get", side_effect=[mock_response1, mock_response2]):
            maps = list(client.iter_all_maps(page_size=2))

        assert len(maps) == 4
        assert [m.id for m in maps] == ["1", "2", "3", "4"]

    def test_iter_all_maps_respects_max_pages(self) -> None:
        """Should stop after max_pages even if more are available."""
        client = FAFApiClient(min_request_delay=0)

        page_data = create_mock_response(
            maps=[{"id": "1"}],
            total_records=100,
            total_pages=10,
        )

        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = page_data

        with mock.patch("requests.get", return_value=mock_response):
            maps = list(client.iter_all_maps(page_size=10, max_pages=2))

        assert len(maps) == 2


class TestMapMetadata:
    """Tests for MapMetadata dataclass."""

    def test_mapmetadata_stores_all_fields(self) -> None:
        """MapMetadata should store all provided fields."""
        meta = MapMetadata(
            id="12345",
            display_name="Test Map",
            map_size=512,
            player_count=4,
            ranked=True,
            download_url="https://example.com/map.zip",
            version="v0002",
        )

        assert meta.id == "12345"
        assert meta.display_name == "Test Map"
        assert meta.map_size == 512
        assert meta.player_count == 4
        assert meta.ranked is True
        assert meta.download_url == "https://example.com/map.zip"
        assert meta.version == "v0002"

    def test_mapmetadata_version_optional(self) -> None:
        """MapMetadata should allow None version."""
        meta = MapMetadata(
            id="1",
            display_name="Test",
            map_size=256,
            player_count=2,
            ranked=False,
            download_url="https://example.com/map.zip",
        )

        assert meta.version is None


class TestMapListResult:
    """Tests for MapListResult dataclass."""

    def test_maplistresult_stores_all_fields(self) -> None:
        """MapListResult should store all provided fields."""
        maps = [
            MapMetadata("1", "Map 1", 256, 2, False, "url1"),
            MapMetadata("2", "Map 2", 512, 4, True, "url2"),
        ]
        result = MapListResult(
            maps=maps,
            total_records=100,
            total_pages=10,
            current_page=1,
        )

        assert len(result.maps) == 2
        assert result.total_records == 100
        assert result.total_pages == 10
        assert result.current_page == 1
