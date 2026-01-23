"""Unit tests for FAF OAuth2 authentication."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from faf.api.auth import (
    FAFAuthClient,
    FAFAuthError,
    FAFCredentials,
    FAFToken,
    get_credentials_from_environment,
    has_credentials_in_environment,
)


class TestFAFCredentials:
    """Tests for FAFCredentials dataclass."""

    def test_credentials_stores_values(self) -> None:
        """Should store client ID and secret."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        assert creds.client_id == "test_id"
        assert creds.client_secret == "test_secret"


class TestFAFToken:
    """Tests for FAFToken dataclass."""

    def test_token_stores_values(self) -> None:
        """Should store token values."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        token = FAFToken(
            access_token="abc123",
            token_type="Bearer",
            expires_at=expires_at,
            scope="public_profile",
        )
        assert token.access_token == "abc123"
        assert token.token_type == "Bearer"
        assert token.scope == "public_profile"

    def test_token_is_expired_false_when_valid(self) -> None:
        """Token should not be expired when expiry is in future."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        token = FAFToken(
            access_token="abc123",
            token_type="Bearer",
            expires_at=expires_at,
            scope="public_profile",
        )
        assert token.is_expired is False

    def test_token_is_expired_true_when_past(self) -> None:
        """Token should be expired when expiry is in past."""
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        token = FAFToken(
            access_token="abc123",
            token_type="Bearer",
            expires_at=expires_at,
            scope="public_profile",
        )
        assert token.is_expired is True

    def test_token_is_expired_true_within_buffer(self) -> None:
        """Token should be expired when within 5-minute buffer."""
        # Expires in 3 minutes (within the 5-minute buffer)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)
        token = FAFToken(
            access_token="abc123",
            token_type="Bearer",
            expires_at=expires_at,
            scope="public_profile",
        )
        assert token.is_expired is True

    def test_token_authorization_header(self) -> None:
        """Should generate correct Authorization header."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        token = FAFToken(
            access_token="abc123",
            token_type="Bearer",
            expires_at=expires_at,
            scope="public_profile",
        )
        assert token.authorization_header == "Bearer abc123"


class TestFAFAuthClientInit:
    """Tests for FAFAuthClient initialization."""

    def test_init_with_credentials(self) -> None:
        """Should initialize with credentials."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        client = FAFAuthClient(credentials=creds)
        assert client.credentials == creds

    def test_init_with_custom_token_url(self) -> None:
        """Should accept custom token URL."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        client = FAFAuthClient(credentials=creds, token_url="https://custom.url/token")
        assert client.token_url == "https://custom.url/token"


class TestFAFAuthClientFromEnvironment:
    """Tests for FAFAuthClient.from_environment."""

    def test_from_environment_reads_credentials(self) -> None:
        """Should read credentials from environment variables."""
        with mock.patch.dict(
            os.environ,
            {"FAF_CLIENT_ID": "env_id", "FAF_CLIENT_SECRET": "env_secret"},
        ):
            client = FAFAuthClient.from_environment()
            assert client.credentials.client_id == "env_id"
            assert client.credentials.client_secret == "env_secret"

    def test_from_environment_raises_on_missing_id(self) -> None:
        """Should raise error when client ID is missing."""
        with mock.patch.dict(os.environ, {"FAF_CLIENT_SECRET": "secret"}, clear=True):
            # Clear FAF_CLIENT_ID if it exists
            os.environ.pop("FAF_CLIENT_ID", None)
            with pytest.raises(FAFAuthError, match="FAF_CLIENT_ID"):
                FAFAuthClient.from_environment()

    def test_from_environment_raises_on_missing_secret(self) -> None:
        """Should raise error when client secret is missing."""
        with mock.patch.dict(os.environ, {"FAF_CLIENT_ID": "id"}, clear=True):
            os.environ.pop("FAF_CLIENT_SECRET", None)
            with pytest.raises(FAFAuthError, match="FAF_CLIENT_SECRET"):
                FAFAuthClient.from_environment()

    def test_from_environment_custom_var_names(self) -> None:
        """Should support custom environment variable names."""
        with mock.patch.dict(
            os.environ,
            {"CUSTOM_ID": "custom_id_val", "CUSTOM_SECRET": "custom_secret_val"},
        ):
            client = FAFAuthClient.from_environment(
                client_id_var="CUSTOM_ID",
                client_secret_var="CUSTOM_SECRET",
            )
            assert client.credentials.client_id == "custom_id_val"
            assert client.credentials.client_secret == "custom_secret_val"


class TestFAFAuthClientFromConfigFile:
    """Tests for FAFAuthClient.from_config_file."""

    def test_from_config_file_reads_yaml(self) -> None:
        """Should read credentials from YAML config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("client_id: file_id\nclient_secret: file_secret\n")
            config_path = Path(f.name)

        try:
            client = FAFAuthClient.from_config_file(config_path)
            assert client.credentials.client_id == "file_id"
            assert client.credentials.client_secret == "file_secret"
        finally:
            config_path.unlink()

    def test_from_config_file_raises_on_missing_file(self) -> None:
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            FAFAuthClient.from_config_file(Path("/nonexistent/config.yaml"))

    def test_from_config_file_raises_on_missing_client_id(self) -> None:
        """Should raise error when client_id is missing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("client_secret: secret\n")
            config_path = Path(f.name)

        try:
            with pytest.raises(FAFAuthError, match="client_id"):
                FAFAuthClient.from_config_file(config_path)
        finally:
            config_path.unlink()

    def test_from_config_file_raises_on_missing_client_secret(self) -> None:
        """Should raise error when client_secret is missing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("client_id: id\n")
            config_path = Path(f.name)

        try:
            with pytest.raises(FAFAuthError, match="client_secret"):
                FAFAuthClient.from_config_file(config_path)
        finally:
            config_path.unlink()


class TestFAFAuthClientGetValidToken:
    """Tests for FAFAuthClient.get_valid_token."""

    def test_get_valid_token_requests_new_token(self) -> None:
        """Should request new token when none exists."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        client = FAFAuthClient(credentials=creds)

        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "public_profile",
        }

        with mock.patch("faf.api.auth.requests.post", return_value=mock_response):
            token = client.get_valid_token()

        assert token.access_token == "new_token"

    def test_get_valid_token_returns_cached_token(self) -> None:
        """Should return cached token if still valid."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        client = FAFAuthClient(credentials=creds)

        # Set a valid cached token
        client._token = FAFToken(
            access_token="cached_token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="public_profile",
        )

        with mock.patch("faf.api.auth.requests.post") as mock_post:
            token = client.get_valid_token()

        # Should not make a request
        mock_post.assert_not_called()
        assert token.access_token == "cached_token"

    def test_get_valid_token_refreshes_expired_token(self) -> None:
        """Should request new token when cached token is expired."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        client = FAFAuthClient(credentials=creds)

        # Set an expired cached token
        client._token = FAFToken(
            access_token="expired_token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            scope="public_profile",
        )

        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with mock.patch("faf.api.auth.requests.post", return_value=mock_response):
            token = client.get_valid_token()

        assert token.access_token == "refreshed_token"

    def test_get_valid_token_raises_on_invalid_credentials(self) -> None:
        """Should raise error on 401 response."""
        creds = FAFCredentials(client_id="bad_id", client_secret="bad_secret")
        client = FAFAuthClient(credentials=creds)

        mock_response = mock.MagicMock()
        mock_response.status_code = 401

        with mock.patch("faf.api.auth.requests.post", return_value=mock_response):
            with pytest.raises(FAFAuthError, match="Invalid client credentials"):
                client.get_valid_token()

    def test_get_valid_token_raises_on_server_error(self) -> None:
        """Should raise error on non-200 response."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        client = FAFAuthClient(credentials=creds)

        mock_response = mock.MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with mock.patch("faf.api.auth.requests.post", return_value=mock_response):
            with pytest.raises(FAFAuthError, match="HTTP 500"):
                client.get_valid_token()


class TestFAFAuthClientClearToken:
    """Tests for FAFAuthClient.clear_token."""

    def test_clear_token_removes_cached_token(self) -> None:
        """Should clear the cached token."""
        creds = FAFCredentials(client_id="test_id", client_secret="test_secret")
        client = FAFAuthClient(credentials=creds)

        client._token = FAFToken(
            access_token="cached_token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="public_profile",
        )

        client.clear_token()
        assert client._token is None


class TestGetCredentialsFromEnvironment:
    """Tests for get_credentials_from_environment helper."""

    def test_returns_credentials_when_set(self) -> None:
        """Should return credentials when env vars are set."""
        with mock.patch.dict(
            os.environ,
            {"FAF_CLIENT_ID": "id", "FAF_CLIENT_SECRET": "secret"},
        ):
            creds = get_credentials_from_environment()
            assert creds is not None
            assert creds.client_id == "id"
            assert creds.client_secret == "secret"

    def test_returns_none_when_missing(self) -> None:
        """Should return None when env vars are not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("FAF_CLIENT_ID", None)
            os.environ.pop("FAF_CLIENT_SECRET", None)
            creds = get_credentials_from_environment()
            assert creds is None


class TestHasCredentialsInEnvironment:
    """Tests for has_credentials_in_environment helper."""

    def test_returns_true_when_set(self) -> None:
        """Should return True when both env vars are set."""
        with mock.patch.dict(
            os.environ,
            {"FAF_CLIENT_ID": "id", "FAF_CLIENT_SECRET": "secret"},
        ):
            assert has_credentials_in_environment() is True

    def test_returns_false_when_missing_id(self) -> None:
        """Should return False when client ID is missing."""
        with mock.patch.dict(os.environ, {"FAF_CLIENT_SECRET": "secret"}, clear=True):
            os.environ.pop("FAF_CLIENT_ID", None)
            assert has_credentials_in_environment() is False

    def test_returns_false_when_missing_secret(self) -> None:
        """Should return False when client secret is missing."""
        with mock.patch.dict(os.environ, {"FAF_CLIENT_ID": "id"}, clear=True):
            os.environ.pop("FAF_CLIENT_SECRET", None)
            assert has_credentials_in_environment() is False
