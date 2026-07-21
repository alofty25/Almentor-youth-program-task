"""
projects/tests/test_views.py

Unit tests for ProjectViewSet (projects/views.py).
Tests data isolation, CRUD operations, authentication enforcement,
and soft-delete behaviour at the API level.

We use APIClient with force_authenticate() to bypass JWT — this keeps these
tests focused on view logic, not authentication plumbing.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project

User = get_user_model()

# Endpoint base URL
PROJECTS_URL = "/api/projects/"


def detail_url(pk):
    return f"{PROJECTS_URL}{pk}/"


class ProjectViewAuthenticationTestCase(TestCase):
    """Tests that all endpoints require authentication."""

    def setUp(self):
        self.client = APIClient()

    def test_list_projects_unauthenticated_returns_401(self):
        """Un-authenticated GET /api/projects/ must return 401."""
        response = self.client.get(PROJECTS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_project_unauthenticated_returns_401(self):
        """Un-authenticated POST /api/projects/ must return 401."""
        response = self.client.post(PROJECTS_URL, {"name": "Sneaky"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProjectListCreateViewTestCase(TestCase):
    """Tests for GET and POST /api/projects/"""

    def setUp(self):
        self.user1 = User.objects.create_user(username="jack", password="pass1234")
        self.user2 = User.objects.create_user(username="kate", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

        # user1 has 2 projects, user2 has 1 project
        self.p1 = Project.objects.create(owner=self.user1, name="User1 Project A")
        self.p2 = Project.objects.create(owner=self.user1, name="User1 Project B")
        self.p3 = Project.objects.create(owner=self.user2, name="User2 Project")

    # ------------------------------------------------------------------ #
    # GET — list                                                           #
    # ------------------------------------------------------------------ #

    def test_list_returns_only_authenticated_users_projects(self):
        """Data isolation: user1 must only see their own projects, not user2's."""
        response = self.client.get(PROJECTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = [p["id"] for p in response.data["results"]]
        self.assertIn(self.p1.pk, returned_ids)
        self.assertIn(self.p2.pk, returned_ids)
        self.assertNotIn(self.p3.pk, returned_ids)

    def test_list_returns_correct_count(self):
        """user1 should see exactly 2 projects."""
        response = self.client.get(PROJECTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_does_not_return_soft_deleted_projects(self):
        """Soft-deleted projects must be hidden from the list view."""
        self.p1.delete()
        response = self.client.get(PROJECTS_URL)
        returned_ids = [p["id"] for p in response.data["results"]]
        self.assertNotIn(self.p1.pk, returned_ids)

    def test_list_response_contains_expected_fields(self):
        """Each project in the list must contain the required fields."""
        response = self.client.get(PROJECTS_URL)
        first = response.data["results"][0]
        for field in ["id", "name", "description", "created_at", "updated_at"]:
            self.assertIn(field, first)
        self.assertNotIn("owner", first)
        self.assertNotIn("deleted_at", first)

    # ------------------------------------------------------------------ #
    # POST — create                                                        #
    # ------------------------------------------------------------------ #

    def test_create_project_returns_201_with_valid_data(self):
        """POST with valid data must return 201 Created."""
        response = self.client.post(PROJECTS_URL, {"name": "New Project"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_project_sets_owner_to_authenticated_user(self):
        """The owner of a newly created project must be the authenticated user."""
        response = self.client.post(PROJECTS_URL, {"name": "Owned Project"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.owner, self.user1)

    def test_create_project_response_payload_is_correct(self):
        """The response body for a newly created project must include all expected fields."""
        response = self.client.post(
            PROJECTS_URL, {"name": "Payload Check", "description": "A description"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Payload Check")
        self.assertEqual(response.data["description"], "A description")
        self.assertIn("id", response.data)
        self.assertIn("created_at", response.data)

    def test_create_project_with_duplicate_name_returns_400(self):
        """Creating a project with a name already used by this user must return 400."""
        response = self.client.post(PROJECTS_URL, {"name": "User1 Project A"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)

    def test_create_project_missing_name_returns_400(self):
        """POST without the required 'name' field must return 400."""
        response = self.client.post(PROJECTS_URL, {"description": "Only a description"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)


class ProjectDetailViewTestCase(TestCase):
    """Tests for GET, PUT, PATCH, DELETE /api/projects/:id/"""

    def setUp(self):
        self.user1 = User.objects.create_user(username="leo", password="pass1234")
        self.user2 = User.objects.create_user(username="mia", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

        self.project = Project.objects.create(owner=self.user1, name="My Project")
        self.other_project = Project.objects.create(owner=self.user2, name="Mia Project")

    # ------------------------------------------------------------------ #
    # GET — retrieve                                                       #
    # ------------------------------------------------------------------ #

    def test_retrieve_own_project_returns_200(self):
        """GET on own project must return 200 OK."""
        response = self.client.get(detail_url(self.project.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "My Project")

    def test_retrieve_other_users_project_returns_404(self):
        """
        Data isolation: attempting to GET another user's project must return 404,
        not 403, to avoid leaking the existence of other users' resources.
        """
        response = self.client.get(detail_url(self.other_project.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_nonexistent_project_returns_404(self):
        """GET on a non-existent project ID must return 404."""
        response = self.client.get(detail_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------ #
    # PUT — full update                                                    #
    # ------------------------------------------------------------------ #

    def test_update_project_name_returns_200_and_new_name(self):
        """PUT with a new valid name must return 200 and reflect the change."""
        response = self.client.put(detail_url(self.project.pk), {"name": "Renamed Project"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Renamed Project")

    def test_update_persists_changes_to_database(self):
        """After a successful PUT, the change must be persisted in the database."""
        self.client.put(detail_url(self.project.pk), {"name": "DB Check"})
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "DB Check")

    def test_update_other_users_project_returns_404(self):
        """Data isolation: PUT on another user's project must return 404."""
        response = self.client.put(
            detail_url(self.other_project.pk), {"name": "Hacked"}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------ #
    # DELETE — soft delete                                                 #
    # ------------------------------------------------------------------ #

    def test_delete_project_returns_204(self):
        """DELETE on own project must return 204 No Content."""
        response = self.client.delete(detail_url(self.project.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_soft_deletes_project(self):
        """After DELETE, the project must still exist in DB (soft-delete, not hard)."""
        self.client.delete(detail_url(self.project.pk))
        self.assertTrue(Project.all_objects.filter(pk=self.project.pk).exists())

    def test_delete_hides_project_from_list(self):
        """After DELETE, the project must not appear in the list view."""
        self.client.delete(detail_url(self.project.pk))
        response = self.client.get(PROJECTS_URL)
        returned_ids = [p["id"] for p in response.data["results"]]
        self.assertNotIn(self.project.pk, returned_ids)

    def test_delete_other_users_project_returns_404(self):
        """Data isolation: DELETE on another user's project must return 404."""
        response = self.client.delete(detail_url(self.other_project.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
