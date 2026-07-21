"""
integration_tests/test_authentication_flow.py

Integration tests for the full JWT authentication lifecycle:
  - Obtain token pair with valid credentials
  - Use access token to call protected endpoints
  - Refresh access token using the refresh token
  - Reject invalid credentials
  - Reject requests with no/bad/expired tokens
"""

from rest_framework import status
from rest_framework.test import APIClient

from integration_tests.base import (
    IntegrationTestBase,
    TOKEN_URL, TOKEN_REFRESH_URL, PROJECTS_URL,
)


class JWTTokenObtainFlowTest(IntegrationTestBase):
    """Tests for POST /api/token/ — obtaining a JWT token pair."""

    def setUp(self):
        self.user = self.create_user("auth_user", "SecurePass99!")

    def test_valid_credentials_return_access_and_refresh_tokens(self):
        """Correct username+password must return both access and refresh tokens."""
        client = APIClient()
        resp = client.post(TOKEN_URL, {"username": "auth_user", "password": "SecurePass99!"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertIsNotNone(resp.data["access"])
        self.assertIsNotNone(resp.data["refresh"])

    def test_access_token_is_a_non_empty_string(self):
        """The access token must be a non-empty string."""
        client = APIClient()
        resp = client.post(TOKEN_URL, {"username": "auth_user", "password": "SecurePass99!"})
        self.assertIsInstance(resp.data["access"], str)
        self.assertGreater(len(resp.data["access"]), 0)

    def test_wrong_password_returns_401(self):
        """Wrong password must return 401 Unauthorized."""
        client = APIClient()
        resp = client.post(TOKEN_URL, {"username": "auth_user", "password": "WrongPass!"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_user_returns_401(self):
        """Attempting to authenticate a user that doesn't exist must return 401."""
        client = APIClient()
        resp = client.post(TOKEN_URL, {"username": "ghost_user", "password": "anything"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_password_returns_400(self):
        """Omitting the password field must return 400 Bad Request."""
        client = APIClient()
        resp = client.post(TOKEN_URL, {"username": "auth_user"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_username_returns_400(self):
        """Omitting the username field must return 400 Bad Request."""
        client = APIClient()
        resp = client.post(TOKEN_URL, {"password": "SecurePass99!"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_body_returns_400(self):
        """An empty POST body must return 400."""
        client = APIClient()
        resp = client.post(TOKEN_URL, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class JWTProtectedEndpointAccessTest(IntegrationTestBase):
    """Tests for using JWT tokens to access protected endpoints."""

    def setUp(self):
        self.user = self.create_user("protected_user", "SecurePass99!")

    def test_access_token_allows_reaching_protected_endpoint(self):
        """A valid Bearer token must grant access to /api/projects/."""
        client, _ = self.auth_client("protected_user", "SecurePass99!")
        resp = client.get(PROJECTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_no_token_returns_401(self):
        """A request with no Authorization header must return 401."""
        client = APIClient()
        resp = client.get(PROJECTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_token_returns_401(self):
        """A malformed Bearer token must return 401."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer this.is.not.a.valid.jwt")
        resp = client.get(PROJECTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_scheme_returns_401(self):
        """Using 'Token' scheme instead of 'Bearer' must return 401."""
        tokens = self.get_tokens("protected_user", "SecurePass99!")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {tokens['access']}")
        resp = client.get(PROJECTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class JWTTokenRefreshFlowTest(IntegrationTestBase):
    """Tests for POST /api/token/refresh/ — refreshing an access token."""

    def setUp(self):
        self.user = self.create_user("refresh_user", "SecurePass99!")
        tokens = self.get_tokens("refresh_user", "SecurePass99!")
        self.refresh_token = tokens["refresh"]

    def test_valid_refresh_token_returns_new_access_token(self):
        """A valid refresh token must return a new access token."""
        client = APIClient()
        resp = client.post(TOKEN_REFRESH_URL, {"refresh": self.refresh_token})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIsNotNone(resp.data["access"])

    def test_new_access_token_from_refresh_grants_api_access(self):
        """
        The new access token obtained via refresh must actually work
        to authenticate subsequent API requests.
        """
        client = APIClient()
        refresh_resp = client.post(TOKEN_REFRESH_URL, {"refresh": self.refresh_token})
        new_access = refresh_resp.data["access"]

        auth_client = APIClient()
        auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        resp = auth_client.get(PROJECTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_invalid_refresh_token_returns_401(self):
        """Attempting to refresh with a tampered/invalid token must return 401."""
        client = APIClient()
        resp = client.post(TOKEN_REFRESH_URL, {"refresh": "invalid.refresh.token"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_refresh_token_returns_400(self):
        """POST to refresh endpoint with empty body must return 400."""
        client = APIClient()
        resp = client.post(TOKEN_REFRESH_URL, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
