"""Map download utility for FAF content server.

This module provides functionality to download and extract Supreme Commander maps
from the FAF (Forged Alliance Forever) content server.
"""

import io
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

# FAF content server base URL
FAF_CONTENT_BASE_URL = "https://content.faforever.com/maps"

# FAF API base URL for map lookup
FAF_API_BASE_URL = "https://api.faforever.com/data/map"

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF_MULTIPLIER = 2.0

# HTTP timeout in seconds
DEFAULT_TIMEOUT = 30

# Transient HTTP status codes that should trigger retry
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class MapDownloadError(Exception):
    """Raised when a map download fails.

    Attributes:
        url: The URL that was being downloaded.
        status_code: HTTP status code if available.
        message: Human-readable error message.
    """

    def __init__(
        self, message: str, url: Optional[str] = None, status_code: Optional[int] = None
    ) -> None:
        """Initialize MapDownloadError.

        Args:
            message: Human-readable error description.
            url: The URL that failed to download.
            status_code: HTTP status code if the error was HTTP-related.
        """
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.message = message


@dataclass
class MapInfo:
    """Information about a downloaded map.

    Attributes:
        name: Map display name (without version).
        version: Map version string (e.g., "v0001").
        root_dir: Path to the extracted map directory.
        scmap_path: Path to the .scmap binary terrain file.
        scenario_path: Path to the _scenario.lua metadata file.
        save_path: Path to the _save.lua markers file.
        script_path: Path to the _script.lua custom scripts file.
    """

    name: str
    version: str
    root_dir: Path
    scmap_path: Path
    scenario_path: Path
    save_path: Path
    script_path: Path


class MapDownloader:
    """Downloads and extracts maps from the FAF content server.

    This class handles downloading map zip archives from the FAF content server,
    extracting them to a specified directory, and validating the map structure.

    Example:
        >>> downloader = MapDownloader()
        >>> info = downloader.download(
        ...     "https://content.faforever.com/maps/theta_passage_5.v0001.zip",
        ...     output_dir=Path("/tmp/maps")
        ... )
        >>> print(info.scmap_path)
        /tmp/maps/theta_passage_5.v0001/theta_passage_5.scmap
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the MapDownloader.

        Args:
            max_retries: Maximum number of retry attempts for transient failures.
            retry_delay: Initial delay in seconds between retries.
            timeout: HTTP request timeout in seconds.
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    def download(
        self,
        source: str,
        output_dir: Path,
        by_name: bool = False,
    ) -> MapInfo:
        """Download and extract a map from the FAF content server.

        Args:
            source: Either a direct URL to the map zip file, or a map name
                if by_name is True.
            output_dir: Directory where the map will be extracted.
            by_name: If True, treat source as a map name and look up the
                download URL via the FAF API.

        Returns:
            MapInfo containing paths to all extracted map files.

        Raises:
            MapDownloadError: If the download fails, the zip is invalid,
                or the map structure is invalid.
            FileNotFoundError: If the output directory doesn't exist.
        """
        if not output_dir.exists():
            raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

        if by_name:
            url = self._resolve_map_url(source)
        else:
            url = source

        zip_content = self._download_with_retry(url)
        return self._extract_and_validate(zip_content, output_dir, url)

    def download_by_name(self, map_name: str, output_dir: Path) -> MapInfo:
        """Download a map by looking up its name via the FAF API.

        This is a convenience method that calls download() with by_name=True.

        Args:
            map_name: The display name of the map to download.
            output_dir: Directory where the map will be extracted.

        Returns:
            MapInfo containing paths to all extracted map files.

        Raises:
            MapDownloadError: If the map is not found or download fails.
            FileNotFoundError: If the output directory doesn't exist.
        """
        return self.download(map_name, output_dir, by_name=True)

    def _resolve_map_url(self, map_name: str) -> str:
        """Look up a map's download URL via the FAF API.

        Args:
            map_name: The display name of the map.

        Returns:
            The download URL for the map.

        Raises:
            MapDownloadError: If the map is not found or the API request fails.
        """
        encoded_name = quote(map_name, safe="")
        api_url = f"{FAF_API_BASE_URL}?filter[displayName]=={encoded_name}"

        try:
            response = requests.get(api_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            raise MapDownloadError(
                f"API request timed out while looking up map '{map_name}'", url=api_url
            ) from e
        except requests.exceptions.RequestException as e:
            raise MapDownloadError(
                f"API request failed while looking up map '{map_name}': {e}", url=api_url
            ) from e

        try:
            data = response.json()
        except ValueError as e:
            raise MapDownloadError(
                f"Invalid JSON response from API while looking up map '{map_name}'", url=api_url
            ) from e

        maps = data.get("data", [])
        if not maps:
            raise MapDownloadError(f"Map not found: '{map_name}'", url=api_url, status_code=404)

        map_data = maps[0]
        attributes = map_data.get("attributes", {})
        download_url = attributes.get("downloadUrl")

        if not download_url:
            raise MapDownloadError(f"Map '{map_name}' found but has no download URL", url=api_url)

        return download_url

    def _download_with_retry(self, url: str) -> bytes:
        """Download content from URL with retry logic.

        Args:
            url: The URL to download from.

        Returns:
            The downloaded content as bytes.

        Raises:
            MapDownloadError: If all retry attempts fail.
        """
        last_exception: Optional[Exception] = None
        delay = self.retry_delay

        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, timeout=self.timeout)

                if response.status_code == 404:
                    raise MapDownloadError(f"Map not found at URL: {url}", url=url, status_code=404)

                if response.status_code in TRANSIENT_STATUS_CODES:
                    raise requests.exceptions.RequestException(
                        f"Transient error: HTTP {response.status_code}"
                    )

                response.raise_for_status()
                return response.content

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER

            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    delay *= RETRY_BACKOFF_MULTIPLIER

        raise MapDownloadError(
            f"Download failed after {self.max_retries} attempts: {last_exception}",
            url=url,
        ) from last_exception

    def _extract_and_validate(
        self, zip_content: bytes, output_dir: Path, source_url: str
    ) -> MapInfo:
        """Extract zip content and validate map structure.

        Args:
            zip_content: The downloaded zip file content.
            output_dir: Directory to extract to.
            source_url: Original URL for error messages.

        Returns:
            MapInfo with paths to extracted files.

        Raises:
            MapDownloadError: If the zip is invalid or map structure is wrong.
        """
        try:
            zip_buffer = io.BytesIO(zip_content)
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                if zf.testzip() is not None:
                    raise MapDownloadError("Downloaded zip file is corrupted", url=source_url)

                root_dir_name = self._find_root_directory(zf)
                if root_dir_name is None:
                    raise MapDownloadError(
                        "Invalid map structure: no root directory found in zip",
                        url=source_url,
                    )

                zf.extractall(output_dir)

        except zipfile.BadZipFile as e:
            raise MapDownloadError(
                "Downloaded file is not a valid zip archive", url=source_url
            ) from e

        root_dir = output_dir / root_dir_name
        return self._build_map_info(root_dir, source_url)

    def _find_root_directory(self, zf: zipfile.ZipFile) -> Optional[str]:
        """Find the root directory name in a map zip file.

        Args:
            zf: Open ZipFile object.

        Returns:
            The root directory name, or None if not found.
        """
        for name in zf.namelist():
            parts = name.split("/")
            if len(parts) >= 1 and parts[0]:
                return parts[0]
        return None

    def _build_map_info(self, root_dir: Path, source_url: str) -> MapInfo:
        """Build MapInfo from extracted directory.

        Args:
            root_dir: Path to the extracted map root directory.
            source_url: Original URL for error messages.

        Returns:
            MapInfo with all paths populated.

        Raises:
            MapDownloadError: If required files are missing.
        """
        name, version = self._parse_map_name(root_dir.name)

        scmap_files = list(root_dir.glob("*.scmap"))
        if not scmap_files:
            raise MapDownloadError(
                f"Invalid map structure: no .scmap file found in {root_dir.name}",
                url=source_url,
            )
        scmap_path = scmap_files[0]

        base_name = scmap_path.stem

        scenario_path = root_dir / f"{base_name}_scenario.lua"
        save_path = root_dir / f"{base_name}_save.lua"
        script_path = root_dir / f"{base_name}_script.lua"

        if not scenario_path.exists():
            raise MapDownloadError(
                f"Invalid map structure: missing {scenario_path.name}",
                url=source_url,
            )

        return MapInfo(
            name=name,
            version=version,
            root_dir=root_dir,
            scmap_path=scmap_path,
            scenario_path=scenario_path,
            save_path=save_path,
            script_path=script_path,
        )

    def _parse_map_name(self, dir_name: str) -> tuple[str, str]:
        """Parse map name and version from directory name.

        Args:
            dir_name: Directory name like "mapname.v0001" or "mapname_v0001".

        Returns:
            Tuple of (name, version). Version defaults to "v0001" if not found.
        """
        version_match = re.search(r"[._](v\d+)$", dir_name, re.IGNORECASE)
        if version_match:
            version = version_match.group(1).lower()
            name = dir_name[: version_match.start()]
            name = name.replace("_", " ").replace(".", " ").strip()
        else:
            name = dir_name.replace("_", " ").replace(".", " ").strip()
            version = "v0001"

        return name, version
