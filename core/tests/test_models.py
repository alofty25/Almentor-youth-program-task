"""
core/tests/test_models.py

Unit tests for the abstract BaseModel and ActiveManager defined in core/models.py.

Because BaseModel is abstract, we use a concrete proxy/concrete model approach:
we use the Project model (which inherits from BaseModel) as a vehicle to test
the shared behaviour, keeping these tests tightly scoped to BaseModel logic.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from projects.models import Project

User = get_user_model()


class ActiveManagerTestCase(TestCase):
    """
    Tests for core.models.ActiveManager — the default manager that hides
    soft-deleted records from normal queries.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Active Project")

    # ------------------------------------------------------------------ #
    # Happy paths                                                          #
    # ------------------------------------------------------------------ #

    def test_active_manager_returns_non_deleted_records(self):
        """Default queryset should include records where deleted_at is NULL."""
        qs = Project.objects.filter(owner=self.user)
        self.assertIn(self.project, qs)

    def test_all_objects_manager_returns_everything(self):
        """all_objects manager should return ALL records, including soft-deleted ones."""
        self.project.delete()
        qs = Project.all_objects.filter(owner=self.user)
        self.assertIn(self.project, qs)

    # ------------------------------------------------------------------ #
    # Soft-delete visibility                                               #
    # ------------------------------------------------------------------ #

    def test_soft_deleted_record_hidden_from_default_manager(self):
        """After soft-delete, the record must NOT appear in Project.objects queryset."""
        self.project.delete()
        qs = Project.objects.filter(owner=self.user)
        self.assertNotIn(self.project, qs)

    def test_soft_deleted_record_still_in_all_objects(self):
        """After soft-delete, the record MUST still appear in Project.all_objects queryset."""
        self.project.delete()
        qs = Project.all_objects.filter(owner=self.user)
        self.assertIn(self.project, qs)


class BaseModelSoftDeleteTestCase(TestCase):
    """
    Tests for BaseModel.delete(), restore(), and hard_delete() methods.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Test Project")

    # ------------------------------------------------------------------ #
    # delete() — soft delete                                               #
    # ------------------------------------------------------------------ #

    def test_soft_delete_sets_deleted_at_timestamp(self):
        """Calling delete() should populate deleted_at with the current timestamp."""
        self.assertIsNone(self.project.deleted_at)
        self.project.delete()
        self.project.refresh_from_db()  # reload from DB via all_objects implicitly
        # We have to use all_objects because default manager hides it
        refreshed = Project.all_objects.get(pk=self.project.pk)
        self.assertIsNotNone(refreshed.deleted_at)

    def test_soft_delete_does_not_remove_row_from_database(self):
        """Soft delete must NOT actually delete the database row."""
        pk = self.project.pk
        self.project.delete()
        # Row must still exist in all_objects
        self.assertTrue(Project.all_objects.filter(pk=pk).exists())

    def test_soft_delete_timestamp_is_close_to_now(self):
        """The deleted_at timestamp should be very close to the current time."""
        before = timezone.now()
        self.project.delete()
        after = timezone.now()
        refreshed = Project.all_objects.get(pk=self.project.pk)
        self.assertGreaterEqual(refreshed.deleted_at, before)
        self.assertLessEqual(refreshed.deleted_at, after)

    # ------------------------------------------------------------------ #
    # restore()                                                            #
    # ------------------------------------------------------------------ #

    def test_restore_clears_deleted_at(self):
        """restore() should set deleted_at back to None."""
        self.project.delete()
        refreshed = Project.all_objects.get(pk=self.project.pk)
        refreshed.restore()
        refreshed.refresh_from_db()
        self.assertIsNone(refreshed.deleted_at)

    def test_restore_makes_record_visible_in_default_manager(self):
        """After restore(), the record should re-appear via Project.objects."""
        self.project.delete()
        refreshed = Project.all_objects.get(pk=self.project.pk)
        refreshed.restore()
        self.assertIn(refreshed, Project.objects.filter(owner=self.user))

    # ------------------------------------------------------------------ #
    # hard_delete()                                                        #
    # ------------------------------------------------------------------ #

    def test_hard_delete_removes_row_from_database(self):
        """hard_delete() must permanently remove the database row."""
        pk = self.project.pk
        self.project.hard_delete()
        self.assertFalse(Project.all_objects.filter(pk=pk).exists())

    def test_hard_delete_on_soft_deleted_record_also_removes_row(self):
        """hard_delete() should work even if the record was already soft-deleted."""
        pk = self.project.pk
        self.project.delete()  # soft delete first
        refreshed = Project.all_objects.get(pk=pk)
        refreshed.hard_delete()
        self.assertFalse(Project.all_objects.filter(pk=pk).exists())
