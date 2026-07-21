"""
integration_tests/test_task_status_transitions.py

Integration tests for task status transitions through the full API stack.
-----------------------------------------------------------------------
Tests all valid status transitions and verifies the DONE → TODO
regression-detection business rule (logger.warning is triggered but
the transition is allowed).

Status machine:
  todo → in_progress → done
  done → todo  (unusual — triggers warning, but allowed)
"""

import datetime
from unittest.mock import patch
from django.utils import timezone
from rest_framework import status

from integration_tests.base import (
    IntegrationTestBase,
    PROJECTS_URL, project_tasks_url, task_detail_url,
)
from tasks.models import Task


def future_date(days=10):
    return (timezone.now() + datetime.timedelta(days=days)).date().isoformat()


class TaskStatusTransitionFlowTest(IntegrationTestBase):
    """Full end-to-end status transition flow through the real API."""

    def setUp(self):
        self.user = self.create_user("transition_user")
        self.client, _ = self.auth_client("transition_user")

        proj = self.client.post(PROJECTS_URL, {"name": "Transition Project"})
        self.proj_id = proj.data["id"]

        task_resp = self.client.post(project_tasks_url(self.proj_id), {
            "title": "Transition Task",
            "priority": "medium",
            "due_date": future_date()
        })
        self.task_id = task_resp.data["id"]

    def _update_status(self, new_status, title="Transition Task", priority="medium"):
        return self.client.put(task_detail_url(self.task_id), {
            "title": title,
            "status": new_status,
            "priority": priority,
        })

    # ------------------------------------------------------------------ #
    # Normal transitions                                                   #
    # ------------------------------------------------------------------ #

    def test_transition_todo_to_in_progress(self):
        """todo → in_progress: must return 200 and persist the new status."""
        resp = self._update_status("in_progress")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "in_progress")

        db_task = Task.objects.get(pk=self.task_id)
        self.assertEqual(db_task.status, Task.Status.IN_PROGRESS)

    def test_transition_in_progress_to_done(self):
        """in_progress → done: must return 200 and persist the new status."""
        self._update_status("in_progress")
        resp = self._update_status("done")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "done")

    def test_full_forward_transition_chain(self):
        """todo → in_progress → done: verify each step via a GET after each PUT."""
        for expected_status in ["in_progress", "done"]:
            self._update_status(expected_status)
            detail = self.client.get(task_detail_url(self.task_id))
            self.assertEqual(detail.data["status"], expected_status)

    # ------------------------------------------------------------------ #
    # Unusual transition: DONE → TODO                                      #
    # ------------------------------------------------------------------ #

    def test_done_to_todo_transition_is_allowed_end_to_end(self):
        """
        Business rule: DONE → TODO is unusual but must NOT be blocked.
        The API must return 200 and persist the TODO status.
        """
        self._update_status("in_progress")
        self._update_status("done")

        resp = self._update_status("todo")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "todo")

        db_task = Task.objects.get(pk=self.task_id)
        self.assertEqual(db_task.status, Task.Status.TODO)

    def test_done_to_todo_triggers_logger_warning_through_api(self):
        """
        When the DONE → TODO transition happens via the real API,
        logger.warning must be called exactly once.
        """
        self._update_status("in_progress")
        self._update_status("done")

        with patch("tasks.serializers.logger") as mock_logger:
            resp = self._update_status("todo")
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            self.assertIn("Transition Task", warning_msg)
            self.assertIn("transition_user", warning_msg)

    def test_normal_transitions_do_not_trigger_warning(self):
        """
        Going todo → in_progress → done must never trigger logger.warning.
        """
        with patch("tasks.serializers.logger") as mock_logger:
            self._update_status("in_progress")
            self._update_status("done")
            mock_logger.warning.assert_not_called()

    # ------------------------------------------------------------------ #
    # Invalid status values                                                #
    # ------------------------------------------------------------------ #

    def test_invalid_status_value_returns_400(self):
        """Setting status to a value not in the choices must return 400."""
        resp = self._update_status("flying")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", resp.data)

    def test_status_preserved_on_failed_update(self):
        """After a rejected status change, the original status must be unchanged."""
        self._update_status("in_progress")  # valid
        self._update_status("invalid_state")  # invalid
        detail = self.client.get(task_detail_url(self.task_id))
        self.assertEqual(detail.data["status"], "in_progress")

    # ------------------------------------------------------------------ #
    # Filter by status after transitions                                   #
    # ------------------------------------------------------------------ #

    def test_filter_reflects_updated_status_immediately(self):
        """
        After updating a task's status, the filter endpoint must
        immediately reflect the change without any caching delay.
        """
        from integration_tests.base import TASKS_URL

        self._update_status("done")

        done_resp = self.client.get(TASKS_URL, {"status": "done"})
        ids = [t["id"] for t in done_resp.data["results"]]
        self.assertIn(self.task_id, ids)

        todo_resp = self.client.get(TASKS_URL, {"status": "todo"})
        ids_todo = [t["id"] for t in todo_resp.data["results"]]
        self.assertNotIn(self.task_id, ids_todo)
