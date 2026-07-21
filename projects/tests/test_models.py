"""
projects/tests/test_models.py

Unit tests for the Project model defined in projects/models.py.
Covers: __str__, soft-delete cascade to tasks, and unique constraint behaviour.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from projects.models import Project
from tasks.models import Task

User = get_user_model()


class ProjectStrTestCase(TestCase):
    """Tests for Project.__str__()"""

    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="pass1234")

    def test_str_returns_name_and_owner_username(self):
        """__str__ should return 'ProjectName (username)' format."""
        project = Project.objects.create(owner=self.user, name="My App")
        self.assertEqual(str(project), "My App (carol)")


class ProjectSoftDeleteCascadeTestCase(TestCase):
    """
    Tests for Project.delete() — the overridden soft-delete that cascades
    soft-deletion down to the project's tasks.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="dave", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Cascade Project")
        import datetime
        from django.utils import timezone
        future_date = (timezone.now() + datetime.timedelta(days=10)).date()
        self.task1 = Task.objects.create(
            project=self.project, title="Task One", due_date=future_date
        )
        self.task2 = Task.objects.create(
            project=self.project, title="Task Two", due_date=future_date
        )

    def test_soft_deleting_project_hides_tasks_from_default_manager(self):
        """
        When a project is soft-deleted, its tasks should also be soft-deleted
        and therefore hidden from Task.objects (the active manager).
        """
        self.project.delete()
        active_tasks = Task.objects.filter(project=self.project)
        self.assertEqual(active_tasks.count(), 0)

    def test_soft_deleting_project_keeps_tasks_in_all_objects(self):
        """
        Cascaded soft-delete must NOT hard-delete tasks.
        They should still exist in Task.all_objects.
        """
        self.project.delete()
        all_tasks = Task.all_objects.filter(project=self.project)
        self.assertEqual(all_tasks.count(), 2)

    def test_all_cascade_deleted_tasks_have_deleted_at_set(self):
        """Every task belonging to the soft-deleted project must have deleted_at populated."""
        self.project.delete()
        for task in Task.all_objects.filter(project=self.project):
            self.assertIsNotNone(task.deleted_at, f"Task '{task.title}' missing deleted_at")

    def test_soft_delete_does_not_affect_tasks_of_other_projects(self):
        """Soft-deleting one project must not touch tasks belonging to a different project."""
        import datetime
        from django.utils import timezone
        future_date = (timezone.now() + datetime.timedelta(days=10)).date()
        other_project = Project.objects.create(owner=self.user, name="Other Project")
        other_task = Task.objects.create(
            project=other_project, title="Other Task", due_date=future_date
        )

        self.project.delete()  # only delete the first project

        # Other project's task should still be active
        self.assertIsNone(Task.objects.get(pk=other_task.pk).deleted_at)


class ProjectUniqueConstraintTestCase(TestCase):
    """
    Tests for the unique_together/UniqueConstraint on (owner, name).
    Note: We test this at the serializer level primarily, but also verify
    the DB-level constraint raises IntegrityError on raw model creation.
    """

    def setUp(self):
        self.user1 = User.objects.create_user(username="eve", password="pass1234")
        self.user2 = User.objects.create_user(username="frank", password="pass1234")

    def test_same_user_cannot_have_duplicate_project_names_at_db_level(self):
        """Creating two projects with the same name for the same user must fail."""
        Project.objects.create(owner=self.user1, name="Website")
        with self.assertRaises(IntegrityError):
            Project.objects.create(owner=self.user1, name="Website")

    def test_different_users_can_share_project_names(self):
        """Two different users are allowed to have projects with the same name."""
        Project.objects.create(owner=self.user1, name="Website")
        # This must NOT raise — different owner
        try:
            Project.objects.create(owner=self.user2, name="Website")
        except IntegrityError:
            self.fail("Different users should be allowed to share project names.")
