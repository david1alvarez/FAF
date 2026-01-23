"""OAuth2 authentication for the FAF API.

This module provides OAuth2 client credentials flow authentication
for accessing the FAF API endpoints that require authentication.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# FAF OAuth2 endpoints
FAF_TOKEN_URL = "https://hydra.faforever.com/oauth2/token"

# Default scope for API access
DEFAULT_SCOPE = "public_profile"

# Buffer time before token expiry to trigger refresh (5 minutes)
TOKEN_EXPIRY_BUFFER_SECONDS = 300

# HTTP timeout for auth requests
AUTH_TIMEOUT = 30


class FAFAuthError(Exception):
    """Raised when authentication fails.

    Attributes:
        message: Human-readable error description.
        status_code: HTTP status code if available.
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class FAFCredentials:
    """OAuth2 client credentials for FAF API.

    Attributes:
        client_id: The OAuth2 client ID.
        client_secret: The OAuth2 client secret.
    """

    client_id: str
    client_secret: str


@dataclass
class FAFToken:
    """OAuth2 access token for FAF API.

    Attributes:
        access_token: The bearer token for API requests.
        token_type: Token type (typically "Bearer").
        expires_at: When the token expires (UTC).
        scope: The granted scope.
    """

    access_token: str
    token_type: str
    expires_at: datetime
    scope: str

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired or about to expire.

        Returns True if the token expires within the next 5 minutes.
        """
        buffer = timedelta(seconds=TOKEN_EXPIRY_BUFFER_SECONDS)
        return datetime.now(timezone.utc) >= self.expires_at - buffer

    @property
    def authorization_header(self) -> str:
        """Get the Authorization header value."""
        return f"{self.token_type} {self.access_token}"


class FAFAuthClient:
    """OAuth2 authentication client for the FAF API.

    This client handles the OAuth2 client credentials flow, including
    token acquisition and automatic refresh when tokens expire.

    Example:
        >>> # From environment variables
        >>> auth = FAFAuthClient.from_environment()
        >>> token = auth.get_valid_token()
        >>> headers = {"Authorization": token.authorization_header}

        >>> # From explicit credentials
        >>> creds = FAFCredentials(client_id="xxx", client_secret="yyy")
        >>> auth = FAFAuthClient(credentials=creds)
    """

    def __init__(
        self,
        credentials: FAFCredentials,
        token_url: str = FAF_TOKEN_URL,
        scope: str = DEFAULT_SCOPE,
        timeout: int = AUTH_TIMEOUT,
    ) -> None:
        """Initialize the auth client.

        Args:
            credentials: OAuth2 client credentials.
            token_url: URL for the OAuth2 token endpoint.
            scope: OAuth2 scope to request.
            timeout: HTTP request timeout in seconds.
        """
        self.credentials = credentials
        self.token_url = token_url
        self.scope = scope
        self.timeout = timeout
        self._token: Optional[FAFToken] = None

    @classmethod
    def from_environment(
        cls,
        client_id_var: str = "FAF_CLIENT_ID",
        client_secret_var: str = "FAF_CLIENT_SECRET",
        **kwargs,
    ) -> "FAFAuthClient":
        """Create an auth client from environment variables.

        Args:
            client_id_var: Environment variable name for client ID.
            client_secret_var: Environment variable name for client secret.
            **kwargs: Additional arguments passed to __init__.

        Returns:
            Configured FAFAuthClient instance.

        Raises:
            FAFAuthError: If required environment variables are not set.
        """
        client_id = os.environ.get(client_id_var)
        client_secret = os.environ.get(client_secret_var)

        if not client_id:
            raise FAFAuthError(f"Environment variable {client_id_var} is not set")
        if not client_secret:
            raise FAFAuthError(f"Environment variable {client_secret_var} is not set")

        credentials = FAFCredentials(client_id=client_id, client_secret=client_secret)
        return cls(credentials=credentials, **kwargs)

    @classmethod
    def from_config_file(cls, config_path: Path, **kwargs) -> "FAFAuthClient":
        """Create an auth client from a YAML config file.

        The config file should have the following format:
        ```yaml
        client_id: "your_client_id"
        client_secret: "your_client_secret"
        ```

        Args:
            config_path: Path to the YAML config file.
            **kwargs: Additional arguments passed to __init__.

        Returns:
            Configured FAFAuthClient instance.

        Raises:
            FAFAuthError: If the config file is missing or invalid.
            FileNotFoundError: If the config file doesn't exist.
        """
        import yaml

        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise FAFAuthError(f"Invalid YAML in config file: {e}") from e

        if not isinstance(config, dict):
            raise FAFAuthError("Config file must contain a YAML dictionary")

        client_id = config.get("client_id")
        client_secret = config.get("client_secret")

        if not client_id:
            raise FAFAuthError("Config file missing 'client_id'")
        if not client_secret:
            raise FAFAuthError("Config file missing 'client_secret'")

        credentials = FAFCredentials(client_id=client_id, client_secret=client_secret)
        return cls(credentials=credentials, **kwargs)

    def get_valid_token(self) -> FAFToken:
        """Get a valid access token, refreshing if necessary.

        Returns:
            A valid FAFToken that can be used for API requests.

        Raises:
            FAFAuthError: If token acquisition fails.
        """
        if self._token is None or self._token.is_expired:
            self._token = self._request_token()
        return self._token

    def _request_token(self) -> FAFToken:
        """Request a new access token from the OAuth2 server.

        Returns:
            A new FAFToken.

        Raises:
            FAFAuthError: If the token request fails.
        """
        logger.debug(f"Requesting OAuth2 token from {self.token_url}")

        data = {
            "grant_type": "client_credentials",
            "client_id": self.credentials.client_id,
            "client_secret": self.credentials.client_secret,
            "scope": self.scope,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = requests.post(
                self.token_url,
                data=data,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 401:
                raise FAFAuthError(
                    "Invalid client credentials",
                    status_code=response.status_code,
                )

            if response.status_code != 200:
                error_msg = response.text[:200] if response.text else "Unknown error"
                raise FAFAuthError(
                    f"Token request failed: HTTP {response.status_code} - {error_msg}",
                    status_code=response.status_code,
                )

            return self._parse_token_response(response.json())

        except requests.exceptions.Timeout:
            raise FAFAuthError("Token request timed out")
        except requests.exceptions.RequestException as e:
            raise FAFAuthError(f"Token request failed: {e}")

    def _parse_token_response(self, data: dict) -> FAFToken:
        """Parse the OAuth2 token response.

        Args:
            data: JSON response from the token endpoint.

        Returns:
            Parsed FAFToken.

        Raises:
            FAFAuthError: If the response is invalid.
        """
        try:
            access_token = data["access_token"]
            token_type = data.get("token_type", "Bearer")
            expires_in = data.get("expires_in", 3600)  # Default 1 hour
            scope = data.get("scope", self.scope)

            # Calculate expiry time
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return FAFToken(
                access_token=access_token,
                token_type=token_type,
                expires_at=expires_at,
                scope=scope,
            )

        except KeyError as e:
            raise FAFAuthError(f"Invalid token response: missing {e}") from e

    def clear_token(self) -> None:
        """Clear the cached token, forcing a refresh on next request."""
        self._token = None


def get_credentials_from_environment() -> Optional[FAFCredentials]:
    """Get credentials from environment variables if available.

    Returns:
        FAFCredentials if both FAF_CLIENT_ID and FAF_CLIENT_SECRET are set,
        None otherwise.
    """
    client_id = os.environ.get("FAF_CLIENT_ID")
    client_secret = os.environ.get("FAF_CLIENT_SECRET")

    if client_id and client_secret:
        return FAFCredentials(client_id=client_id, client_secret=client_secret)
    return None


def has_credentials_in_environment() -> bool:
    """Check if OAuth credentials are available in environment variables.

    Returns:
        True if both FAF_CLIENT_ID and FAF_CLIENT_SECRET are set.
    """
    return bool(os.environ.get("FAF_CLIENT_ID") and os.environ.get("FAF_CLIENT_SECRET"))
