"""
integration_tests/base.py

Shared base class and utilities for all integration tests.

Key differences from unit tests:
  - Uses REAL JWT token flow (obtain → use → refresh) instead of force_authenticate()
  - No mocking — tests the full request/response/database cycle
  - Tests multi-step API flows that span multiple endpoints
"""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

User = get_user_model()

# ------------------------------------------------------------------ #
# URL constants                                                        #
# ------------------------------------------------------------------ #
TOKEN_URL         = "/api/token/"
TOKEN_REFRESH_URL = "/api/token/refresh/"
PROJECTS_URL      = "/api/projects/"
TASKS_URL         = "/api/tasks/"


def project_detail_url(pk):
    return f"/api/projects/{pk}/"


def project_tasks_url(project_id):
    return f"/api/projects/{project_id}/tasks/"


def task_detail_url(pk):
    return f"/api/tasks/{pk}/"


class IntegrationTestBase(APITestCase):
    """
    Base class for all integration tests.

    Provides helpers for:
      - Creating users
      - Obtaining real JWT access tokens
      - Building an authenticated API client
    """

    def create_user(self, username, password="StrongPass123!"):
        """Create and return a test user."""
        return User.objects.create_user(username=username, password=password)

    def get_tokens(self, username, password="StrongPass123!"):
        """
        Perform the real JWT token-obtain flow and return the token pair dict.
        Raises AssertionError if auth fails (bad credentials).
        """
        client = APIClient()
        response = client.post(TOKEN_URL, {"username": username, "password": password})
        self.assertEqual(
            response.status_code, status.HTTP_200_OK,
            f"Token obtain failed for '{username}': {response.data}"
        )
        return response.data  # {'access': '...', 'refresh': '...'}

    def auth_client(self, username, password="StrongPass123!"):
        """
        Return an APIClient pre-loaded with a real JWT Bearer token
        for the given user.
        """
        tokens = self.get_tokens(username, password)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        return client, tokens
