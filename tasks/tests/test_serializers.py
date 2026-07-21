"""
tasks/tests/test_serializers.py

Unit tests for TaskSerializer (tasks/serializers.py).
Covers: field exposure, read-only enforcement, and the status-transition
logging logic in TaskSerializer.update().
"""

import datetime
import logging
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from tasks.models import Task
from tasks.serializers import TaskSerializer
from projects.models import Project

User = get_user_model()
factory = APIRequestFactory()


def _make_request(user):
    """Helper: build a fake request authenticated as `user`."""
    request = factory.get('/')
    request.user = user
    return request


def _future_date(days=10):
    return (timezone.now() + datetime.timedelta(days=days)).date()


class TaskSerializerFieldExposureTestCase(TestCase):
    """Tests verifying which fields are exposed and which are read-only."""

    def setUp(self):
        self.user = User.objects.create_user(username="peter", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Peter's Project")
        self.task = Task.objects.create(
            project=self.project,
            title="Test Task",
            due_date=_future_date()
        )

    def test_project_name_is_included_in_output(self):
        """'project_name' should be derived from project.name and present in output."""
        serializer = TaskSerializer(self.task)
        self.assertIn("project_name", serializer.data)
        self.assertEqual(serializer.data["project_name"], "Peter's Project")

    def test_project_name_is_read_only(self):
        """
        'project_name' is a read-only field. Passing it in input data should
        not cause a validation error, but it also must not modify anything.
        """
        request = _make_request(self.user)
        serializer = TaskSerializer(
            instance=self.task,
            data={
                "title": "Updated Task",
                "project_name": "Hacked Name",
                "status": Task.Status.TODO,
                "priority": Task.Priority.MEDIUM,
            },
            context={"request": request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_project_id_is_read_only(self):
        """
        'project_id' is set via the URL/view, not the request body.
        Passing a different project_id in the payload must not change the task's project.
        """
        other_project = Project.objects.create(owner=self.user, name="Other Project")
        request = _make_request(self.user)
        serializer = TaskSerializer(
            instance=self.task,
            data={
                "title": "Same Task",
                "project_id": other_project.pk,   # attempt to hijack
                "status": Task.Status.TODO,
                "priority": Task.Priority.MEDIUM,
            },
            context={"request": request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        # project must remain unchanged
        self.assertEqual(updated.project_id, self.project.pk)

    def test_serializer_output_contains_all_expected_fields(self):
        """All declared fields must be present in the serialized output."""
        serializer = TaskSerializer(self.task)
        expected_fields = [
            "id", "project_id", "project_name", "title", "description",
            "status", "priority", "due_date", "created_at", "updated_at"
        ]
        for field in expected_fields:
            self.assertIn(field, serializer.data, f"Field '{field}' missing from output")


class TaskSerializerUpdateStatusTransitionTestCase(TestCase):
    """
    Tests for TaskSerializer.update() and the DONE → TODO business rule logging.
    We mock the logger to verify warning calls without side effects.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="quinn", password="pass1234")
        self.project = Project.objects.create(owner=self.user, name="Quinn's Project")
        self.request = _make_request(self.user)

    def _make_task(self, status=Task.Status.TODO):
        return Task.objects.create(
            project=self.project,
            title="Status Task",
            status=status,
            due_date=_future_date()
        )

    # ------------------------------------------------------------------ #
    # Happy paths — normal transitions                                     #
    # ------------------------------------------------------------------ #

    def test_normal_transition_todo_to_in_progress_does_not_log_warning(self):
        """TODO → IN_PROGRESS is a normal transition and must not trigger a warning."""
        task = self._make_task(Task.Status.TODO)
        serializer = TaskSerializer(
            instance=task,
            data={"title": "Status Task", "status": Task.Status.IN_PROGRESS,
                  "priority": Task.Priority.MEDIUM},
            context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch("tasks.serializers.logger") as mock_logger:
            serializer.save()
            mock_logger.warning.assert_not_called()

    def test_normal_transition_in_progress_to_done_does_not_log_warning(self):
        """IN_PROGRESS → DONE is a normal transition and must not trigger a warning."""
        task = self._make_task(Task.Status.IN_PROGRESS)
        serializer = TaskSerializer(
            instance=task,
            data={"title": "Status Task", "status": Task.Status.DONE,
                  "priority": Task.Priority.MEDIUM},
            context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch("tasks.serializers.logger") as mock_logger:
            serializer.save()
            mock_logger.warning.assert_not_called()

    # ------------------------------------------------------------------ #
    # Edge case — DONE → TODO triggers logger.warning                     #
    # ------------------------------------------------------------------ #

    def test_done_to_todo_transition_triggers_logger_warning(self):
        """
        Business rule: moving a task from DONE back to TODO is unusual and must
        trigger a logger.warning call with the task title and username.
        """
        task = self._make_task(Task.Status.DONE)
        serializer = TaskSerializer(
            instance=task,
            data={"title": "Status Task", "status": Task.Status.TODO,
                  "priority": Task.Priority.MEDIUM},
            context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch("tasks.serializers.logger") as mock_logger:
            serializer.save()
            mock_logger.warning.assert_called_once()
            # Verify the warning contains the task title and username
            warning_message = mock_logger.warning.call_args[0][0]
            self.assertIn("Status Task", warning_message)
            self.assertIn("quinn", warning_message)

    def test_done_to_todo_transition_still_saves_new_status(self):
        """
        Even though DONE → TODO is unusual, it IS allowed.
        The status must actually be updated to TODO in the database.
        """
        task = self._make_task(Task.Status.DONE)
        serializer = TaskSerializer(
            instance=task,
            data={"title": "Status Task", "status": Task.Status.TODO,
                  "priority": Task.Priority.MEDIUM},
            context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch("tasks.serializers.logger"):
            updated = serializer.save()

        self.assertEqual(updated.status, Task.Status.TODO)

    def test_update_without_status_change_does_not_log_warning(self):
        """Updating a DONE task's title (no status change) must not trigger a warning."""
        task = self._make_task(Task.Status.DONE)
        serializer = TaskSerializer(
            instance=task,
            data={"title": "Renamed Done Task", "status": Task.Status.DONE,
                  "priority": Task.Priority.MEDIUM},
            context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with patch("tasks.serializers.logger") as mock_logger:
            serializer.save()
            mock_logger.warning.assert_not_called()
