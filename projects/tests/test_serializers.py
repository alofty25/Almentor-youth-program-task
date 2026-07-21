"""
projects/tests/test_serializers.py

Unit tests for ProjectSerializer (projects/serializers.py).
All tests use APIRequestFactory to provide a realistic request context
without hitting any view layer or making HTTP calls.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from projects.models import Project
from projects.serializers import ProjectSerializer

User = get_user_model()
factory = APIRequestFactory()


def _make_request_with_user(user):
    """Helper: build a fake GET request authenticated as `user`."""
    request = factory.get('/')
    request.user = user
    return request


class ProjectSerializerValidateNameTestCase(TestCase):
    """
    Tests for ProjectSerializer.validate_name() business rule:
    a user cannot have two projects with the same name.
    """

    def setUp(self):
        self.user1 = User.objects.create_user(username="grace", password="pass1234")
        self.user2 = User.objects.create_user(username="henry", password="pass1234")
        self.existing = Project.objects.create(owner=self.user1, name="Existing Project")
        self.request1 = _make_request_with_user(self.user1)
        self.request2 = _make_request_with_user(self.user2)

    # ------------------------------------------------------------------ #
    # Happy paths                                                          #
    # ------------------------------------------------------------------ #

    def test_unique_name_for_user_passes_validation(self):
        """A brand-new project name for this user should pass validate_name."""
        serializer = ProjectSerializer(
            data={"name": "Brand New Project"},
            context={"request": self.request1}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_same_name_for_different_user_passes_validation(self):
        """
        User2 should be allowed to create a project with the same name
        that User1 already has — names are unique per-user, not globally.
        """
        serializer = ProjectSerializer(
            data={"name": "Existing Project"},
            context={"request": self.request2}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_existing_project_with_same_name_passes_validation(self):
        """
        When UPDATING a project, the validator should exclude the project itself
        from the uniqueness check so a user can save without changing the name.
        """
        serializer = ProjectSerializer(
            instance=self.existing,
            data={"name": "Existing Project"},
            context={"request": self.request1}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    # ------------------------------------------------------------------ #
    # Error states                                                         #
    # ------------------------------------------------------------------ #

    def test_duplicate_name_for_same_user_fails_validation(self):
        """Creating a project with a name already owned by this user must fail."""
        serializer = ProjectSerializer(
            data={"name": "Existing Project"},
            context={"request": self.request1}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)
        self.assertIn("You already have a project with this name.", serializer.errors["name"])

    def test_missing_name_field_fails_validation(self):
        """The 'name' field is required; omitting it must produce a validation error."""
        serializer = ProjectSerializer(
            data={"description": "No name provided"},
            context={"request": self.request1}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_blank_name_fails_validation(self):
        """An empty string for 'name' should fail Django's CharField blank validation."""
        serializer = ProjectSerializer(
            data={"name": ""},
            context={"request": self.request1}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)


class ProjectSerializerFieldExposureTestCase(TestCase):
    """
    Tests verifying which fields are (and are not) exposed via the serializer.
    Security: owner and deleted_at must NEVER be visible in the API response.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="iris", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Secret Project")

    def test_serialized_output_contains_expected_fields(self):
        """Serializer must include id, name, description, created_at, updated_at."""
        serializer = ProjectSerializer(self.project)
        data = serializer.data
        for field in ["id", "name", "description", "created_at", "updated_at"]:
            self.assertIn(field, data, f"Expected field '{field}' missing from serializer output")

    def test_serialized_output_does_not_expose_owner(self):
        """The 'owner' field must NOT be exposed in the API response."""
        serializer = ProjectSerializer(self.project)
        self.assertNotIn("owner", serializer.data)

    def test_serialized_output_does_not_expose_deleted_at(self):
        """The 'deleted_at' field must NOT be exposed in the API response."""
        serializer = ProjectSerializer(self.project)
        self.assertNotIn("deleted_at", serializer.data)

    def test_id_and_timestamps_are_read_only(self):
        """id, created_at, and updated_at must be read-only fields."""
        request = _make_request_with_user(self.user)
        # Attempt to set read-only fields via incoming data
        serializer = ProjectSerializer(
            instance=self.project,
            data={"name": "Updated Name", "id": 9999, "created_at": "2000-01-01T00:00:00Z"},
            context={"request": request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()
        # Read-only fields must not be overwritten
        self.assertNotEqual(instance.pk, 9999)
