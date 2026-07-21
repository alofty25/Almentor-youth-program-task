"""
tasks/tests/test_models.py

Unit tests for the Task model and its validate_due_date validator
(tasks/models.py).
"""

import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from tasks.models import Task, validate_due_date
from projects.models import Project

User = get_user_model()


class ValidateDueDateTestCase(TestCase):
    """
    Tests for the validate_due_date() validator function.
    This is a pure function — no DB access required.
    """

    def test_future_date_passes_validation(self):
        """A date in the future must not raise a ValidationError."""
        future = timezone.now().date() + datetime.timedelta(days=30)
        try:
            validate_due_date(future)
        except ValidationError:
            self.fail("validate_due_date raised ValidationError for a future date")

    def test_today_passes_validation(self):
        """
        Boundary condition: today's date is valid (due today is still acceptable).
        The validator uses strict less-than (< today), so today is allowed.
        """
        today = timezone.now().date()
        try:
            validate_due_date(today)
        except ValidationError:
            self.fail("validate_due_date raised ValidationError for today's date")

    def test_yesterday_fails_validation(self):
        """Boundary condition: yesterday must raise ValidationError."""
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        with self.assertRaises(ValidationError) as cm:
            validate_due_date(yesterday)
        self.assertIn("Due date cannot be in the past.", cm.exception.messages)

    def test_far_past_date_fails_validation(self):
        """A date far in the past must raise ValidationError."""
        old_date = datetime.date(2000, 1, 1)
        with self.assertRaises(ValidationError):
            validate_due_date(old_date)


class TaskStrTestCase(TestCase):
    """Tests for Task.__str__()"""

    def setUp(self):
        self.user = User.objects.create_user(username="noah", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Noah's Project")

    def test_str_returns_title_and_status_display(self):
        """
        __str__ should return 'TaskTitle (StatusDisplay)' format.
        Status.TODO display value is 'To Do'.
        """
        future = timezone.now().date() + datetime.timedelta(days=5)
        task = Task.objects.create(
            project=self.project, title="Write Tests", due_date=future
        )
        self.assertEqual(str(task), "Write Tests (To Do)")

    def test_str_with_done_status(self):
        """__str__ with DONE status must show 'Done' as the display value."""
        future = timezone.now().date() + datetime.timedelta(days=5)
        task = Task.objects.create(
            project=self.project, title="Deploy App", status=Task.Status.DONE,
            due_date=future
        )
        self.assertEqual(str(task), "Deploy App (Done)")


class TaskDefaultValuesTestCase(TestCase):
    """Tests for Task model default field values."""

    def setUp(self):
        self.user = User.objects.create_user(username="olivia", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Olivia's Project")

    def test_default_status_is_todo(self):
        """A newly created task must default to status='todo'."""
        future = timezone.now().date() + datetime.timedelta(days=5)
        task = Task.objects.create(project=self.project, title="New Task", due_date=future)
        self.assertEqual(task.status, Task.Status.TODO)

    def test_default_priority_is_medium(self):
        """A newly created task must default to priority='medium'."""
        future = timezone.now().date() + datetime.timedelta(days=5)
        task = Task.objects.create(project=self.project, title="New Task", due_date=future)
        self.assertEqual(task.priority, Task.Priority.MEDIUM)

    def test_due_date_is_optional(self):
        """Task can be created without a due_date (it's nullable)."""
        try:
            Task.objects.create(project=self.project, title="No Due Date Task")
        except Exception as e:
            self.fail(f"Creating a task without due_date raised: {e}")
