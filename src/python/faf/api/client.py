"""FAF API client for map discovery.

This module provides a client for querying the FAF (Forged Alliance Forever) API
to discover and list maps available in the vault.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import requests

if TYPE_CHECKING:
    from faf.api.auth import FAFAuthClient

# FAF API base URL
FAF_API_BASE_URL = "https://api.faforever.com"

# Rate limiting configuration
DEFAULT_MIN_REQUEST_DELAY = 0.1  # 100ms minimum between requests
DEFAULT_MAX_RETRIES = 5
DEFAULT_INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0

# HTTP timeout in seconds
DEFAULT_TIMEOUT = 30

# Default User-Agent for API requests
DEFAULT_USER_AGENT = "FAF-Map-AI/0.1"

# Required headers for JSON:API
DEFAULT_HEADERS = {
    "Accept": "application/vnd.api+json",
    "User-Agent": DEFAULT_USER_AGENT,
}

# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class FAFApiError(Exception):
    """Raised when a FAF API request fails.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code if available.
        url: The URL that was being requested.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
    ) -> None:
        """Initialize FAFApiError.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code if the error was HTTP-related.
            url: The URL that failed.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.url = url


@dataclass
class MapMetadata:
    """Metadata for a single map from the FAF vault.

    Attributes:
        id: Unique map identifier in the FAF database.
        display_name: Human-readable map name.
        map_size: Map size in game units (256=5km, 512=10km, 1024=20km).
        player_count: Maximum number of players supported.
        ranked: Whether the map is approved for ranked play.
        download_url: URL to download the map zip file.
        version: Map version string if available.
    """

    id: str
    display_name: str
    map_size: int
    player_count: int
    ranked: bool
    download_url: str
    version: Optional[str] = None


@dataclass
class MapListResult:
    """Result of a map list query.

    Attributes:
        maps: List of map metadata objects.
        total_records: Total number of maps matching the query.
        total_pages: Total number of pages available.
        current_page: Current page number (1-indexed).
    """

    maps: list[MapMetadata]
    total_records: int
    total_pages: int
    current_page: int


class FAFApiClient:
    """Client for the FAF API map discovery endpoints.

    This client handles pagination, rate limiting, and error handling for
    querying the FAF map vault. Supports optional OAuth2 authentication.

    Example:
        >>> # Without authentication (may get 403 on some endpoints)
        >>> client = FAFApiClient()
        >>> result = client.list_maps(page_size=10, page=1)

        >>> # With authentication
        >>> from faf.api.auth import FAFAuthClient
        >>> auth = FAFAuthClient.from_environment()
        >>> client = FAFApiClient(auth_client=auth)
        >>> result = client.list_maps(page_size=10, page=1)
        >>> print(f"Total maps: {result.total_records}")
    """

    def __init__(
        self,
        base_url: str = FAF_API_BASE_URL,
        min_request_delay: float = DEFAULT_MIN_REQUEST_DELAY,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        timeout: int = DEFAULT_TIMEOUT,
        auth_client: Optional[FAFAuthClient] = None,
    ) -> None:
        """Initialize the FAF API client.

        Args:
            base_url: Base URL for the FAF API.
            min_request_delay: Minimum delay in seconds between requests.
            max_retries: Maximum number of retry attempts for transient failures.
            initial_backoff: Initial backoff delay in seconds for retries.
            timeout: HTTP request timeout in seconds.
            auth_client: Optional FAFAuthClient for authenticated requests.
        """
        self.base_url = base_url.rstrip("/")
        self.min_request_delay = min_request_delay
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.timeout = timeout
        self.auth_client = auth_client
        self._last_request_time: Optional[float] = None

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests, including auth if available.

        Returns:
            Dictionary of HTTP headers.
        """
        headers = {**DEFAULT_HEADERS}
        if self.auth_client:
            token = self.auth_client.get_valid_token()
            headers["Authorization"] = token.authorization_header
        return headers

    def list_maps(
        self,
        page_size: int = 100,
        page: int = 1,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        player_count: Optional[int] = None,
        ranked: Optional[bool] = None,
    ) -> MapListResult:
        """List maps from the FAF vault with optional filtering.

        Args:
            page_size: Number of maps per page (max 100).
            page: Page number (1-indexed).
            min_size: Minimum map size in game units (e.g., 512 for 10km+).
            max_size: Maximum map size in game units.
            player_count: Filter to maps with exactly this player count.
            ranked: Filter to ranked (True) or unranked (False) maps.

        Returns:
            MapListResult containing the maps and pagination info.

        Raises:
            FAFApiError: If the API request fails.
            ValueError: If invalid parameters are provided.
        """
        if page_size < 1 or page_size > 100:
            raise ValueError(f"page_size must be between 1 and 100, got {page_size}")
        if page < 1:
            raise ValueError(f"page must be >= 1, got {page}")

        params: dict[str, str] = {
            "page[size]": str(page_size),
            "page[number]": str(page),
        }

        filters = self._build_filters(min_size, max_size, player_count, ranked)
        params.update(filters)

        url = f"{self.base_url}/data/map"
        response_data = self._make_request(url, params)

        return self._parse_map_list_response(response_data, page)

    def _build_filters(
        self,
        min_size: Optional[int],
        max_size: Optional[int],
        player_count: Optional[int],
        ranked: Optional[bool],
    ) -> dict[str, str]:
        """Build filter parameters for the API request.

        Args:
            min_size: Minimum map size filter.
            max_size: Maximum map size filter.
            player_count: Exact player count filter.
            ranked: Ranked status filter.

        Returns:
            Dictionary of filter parameters.
        """
        filters: dict[str, str] = {}

        if min_size is not None:
            filters["filter[mapSize]"] = f"=ge={min_size}"

        if max_size is not None:
            if min_size is not None:
                filters["filter[mapSize]"] = f"=ge={min_size};=le={max_size}"
            else:
                filters["filter[mapSize]"] = f"=le={max_size}"

        if player_count is not None:
            filters["filter[maxPlayers]"] = f"=={player_count}"

        if ranked is not None:
            filters["filter[ranked]"] = "true" if ranked else "false"

        return filters

    def _make_request(self, url: str, params: dict[str, str]) -> dict:
        """Make an HTTP request with rate limiting and retry logic.

        Args:
            url: The URL to request.
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            FAFApiError: If the request fails after all retries.
        """
        self._enforce_rate_limit()

        last_exception: Optional[Exception] = None
        backoff = self.initial_backoff

        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url, params=params, headers=self._get_headers(), timeout=self.timeout
                )
                self._last_request_time = time.time()

                if response.status_code == 200:
                    return response.json()

                if response.status_code in RETRYABLE_STATUS_CODES:
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            backoff = float(retry_after)
                    raise requests.exceptions.RequestException(
                        f"Retryable error: HTTP {response.status_code}"
                    )

                raise FAFApiError(
                    f"API request failed: HTTP {response.status_code}",
                    status_code=response.status_code,
                    url=url,
                )

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER

            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER

        raise FAFApiError(
            f"API request failed after {self.max_retries} attempts: {last_exception}",
            url=url,
        ) from last_exception

    def _enforce_rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.min_request_delay:
                time.sleep(self.min_request_delay - elapsed)

    def _parse_map_list_response(self, data: dict, current_page: int) -> MapListResult:
        """Parse the API response into a MapListResult.

        Args:
            data: Raw JSON response from the API.
            current_page: The page number that was requested.

        Returns:
            Parsed MapListResult.

        Raises:
            FAFApiError: If the response structure is invalid.
        """
        try:
            maps_data = data.get("data", [])
            meta = data.get("meta", {}).get("page", {})

            maps = []
            for item in maps_data:
                attrs = item.get("attributes", {})
                map_metadata = MapMetadata(
                    id=str(item.get("id", "")),
                    display_name=attrs.get("displayName", "Unknown"),
                    map_size=attrs.get("mapSize", 0),
                    player_count=attrs.get("maxPlayers", 0),
                    ranked=attrs.get("ranked", False),
                    download_url=attrs.get("downloadUrl", ""),
                    version=attrs.get("version"),
                )
                maps.append(map_metadata)

            return MapListResult(
                maps=maps,
                total_records=meta.get("totalRecords", len(maps)),
                total_pages=meta.get("totalPages", 1),
                current_page=current_page,
            )

        except (KeyError, TypeError, ValueError) as e:
            raise FAFApiError(f"Failed to parse API response: {e}") from e

    def iter_all_maps(
        self,
        page_size: int = 100,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        player_count: Optional[int] = None,
        ranked: Optional[bool] = None,
        max_pages: Optional[int] = None,
    ):
        """Iterate through all maps matching the given filters.

        This is a generator that automatically handles pagination.

        Args:
            page_size: Number of maps per page (max 100).
            min_size: Minimum map size filter.
            max_size: Maximum map size filter.
            player_count: Exact player count filter.
            ranked: Ranked status filter.
            max_pages: Maximum number of pages to fetch (None for all).

        Yields:
            MapMetadata objects for each map.

        Raises:
            FAFApiError: If an API request fails.
        """
        page = 1
        pages_fetched = 0

        while True:
            result = self.list_maps(
                page_size=page_size,
                page=page,
                min_size=min_size,
                max_size=max_size,
                player_count=player_count,
                ranked=ranked,
            )

            for map_meta in result.maps:
                yield map_meta

            pages_fetched += 1
            if max_pages is not None and pages_fetched >= max_pages:
                break

            if page >= result.total_pages:
                break

            page += 1
