"""
integration_tests/test_data_isolation.py

Integration tests for cross-user data isolation.
-----------------------------------------------------------------------
Ensures that User A can NEVER read, modify, or delete User B's data
through any API endpoint — projects or tasks.

This is a critical security concern for a multi-tenant API.
"""

import datetime
from django.utils import timezone
from rest_framework import status

from integration_tests.base import (
    IntegrationTestBase,
    PROJECTS_URL, TASKS_URL,
    project_detail_url, project_tasks_url, task_detail_url,
)


def future_date(days=10):
    return (timezone.now() + datetime.timedelta(days=days)).date().isoformat()


class CrossUserProjectIsolationTest(IntegrationTestBase):
    """User A must never see or touch User B's projects."""

    def setUp(self):
        # Two independent users with their own authenticated clients
        self.user_a = self.create_user("isolation_user_a")
        self.user_b = self.create_user("isolation_user_b")
        self.client_a, _ = self.auth_client("isolation_user_a")
        self.client_b, _ = self.auth_client("isolation_user_b")

        # Each user creates their own project
        resp_a = self.client_a.post(PROJECTS_URL, {"name": "User A Project"})
        resp_b = self.client_b.post(PROJECTS_URL, {"name": "User B Project"})
        self.project_a_id = resp_a.data["id"]
        self.project_b_id = resp_b.data["id"]

    def test_user_a_list_does_not_contain_user_b_projects(self):
        """User A's project list must only show their own projects."""
        resp = self.client_a.get(PROJECTS_URL)
        ids = [p["id"] for p in resp.data["results"]]
        self.assertIn(self.project_a_id, ids)
        self.assertNotIn(self.project_b_id, ids)

    def test_user_b_list_does_not_contain_user_a_projects(self):
        """User B's project list must only show their own projects."""
        resp = self.client_b.get(PROJECTS_URL)
        ids = [p["id"] for p in resp.data["results"]]
        self.assertIn(self.project_b_id, ids)
        self.assertNotIn(self.project_a_id, ids)

    def test_user_a_cannot_read_user_b_project(self):
        """GET /api/projects/:id/ with User B's ID must return 404 to User A."""
        resp = self.client_a.get(project_detail_url(self.project_b_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_a_cannot_update_user_b_project(self):
        """PUT on User B's project by User A must return 404."""
        resp = self.client_a.put(
            project_detail_url(self.project_b_id),
            {"name": "Hijacked"}
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # Confirm User B's project name is unchanged
        resp_b = self.client_b.get(project_detail_url(self.project_b_id))
        self.assertEqual(resp_b.data["name"], "User B Project")

    def test_user_a_cannot_delete_user_b_project(self):
        """DELETE on User B's project by User A must return 404."""
        resp = self.client_a.delete(project_detail_url(self.project_b_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # Confirm User B's project still exists
        resp_b = self.client_b.get(project_detail_url(self.project_b_id))
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)


class CrossUserTaskIsolationTest(IntegrationTestBase):
    """User A must never see or touch User B's tasks."""

    def setUp(self):
        self.user_a = self.create_user("task_isolation_a")
        self.user_b = self.create_user("task_isolation_b")
        self.client_a, _ = self.auth_client("task_isolation_a")
        self.client_b, _ = self.auth_client("task_isolation_b")

        # Each user has a project with a task
        proj_a = self.client_a.post(PROJECTS_URL, {"name": "A's Project"})
        proj_b = self.client_b.post(PROJECTS_URL, {"name": "B's Project"})
        self.proj_a_id = proj_a.data["id"]
        self.proj_b_id = proj_b.data["id"]

        task_a = self.client_a.post(project_tasks_url(self.proj_a_id), {
            "title": "A's Task", "due_date": future_date()
        })
        task_b = self.client_b.post(project_tasks_url(self.proj_b_id), {
            "title": "B's Task", "due_date": future_date()
        })
        self.task_a_id = task_a.data["id"]
        self.task_b_id = task_b.data["id"]

    def test_global_task_list_shows_only_own_tasks(self):
        """GET /api/tasks/ must return only the authenticated user's tasks."""
        resp_a = self.client_a.get(TASKS_URL)
        ids_a = [t["id"] for t in resp_a.data["results"]]
        self.assertIn(self.task_a_id, ids_a)
        self.assertNotIn(self.task_b_id, ids_a)

        resp_b = self.client_b.get(TASKS_URL)
        ids_b = [t["id"] for t in resp_b.data["results"]]
        self.assertIn(self.task_b_id, ids_b)
        self.assertNotIn(self.task_a_id, ids_b)

    def test_user_a_cannot_read_user_b_task(self):
        """GET /api/tasks/:id/ on User B's task by User A must return 404."""
        resp = self.client_a.get(task_detail_url(self.task_b_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_a_cannot_update_user_b_task(self):
        """PUT on User B's task by User A must return 404 and leave task unchanged."""
        resp = self.client_a.put(
            task_detail_url(self.task_b_id),
            {"title": "Hacked", "status": "done", "priority": "high"}
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # User B's task must be untouched
        original = self.client_b.get(task_detail_url(self.task_b_id))
        self.assertEqual(original.data["title"], "B's Task")

    def test_user_a_cannot_delete_user_b_task(self):
        """DELETE on User B's task by User A must return 404."""
        resp = self.client_a.delete(task_detail_url(self.task_b_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # Task B still accessible to User B
        resp_b = self.client_b.get(task_detail_url(self.task_b_id))
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)

    def test_user_a_cannot_list_tasks_in_user_b_project(self):
        """GET /api/projects/:id/tasks/ for User B's project ID returns 404 to User A."""
        resp = self.client_a.get(project_tasks_url(self.proj_b_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_a_cannot_create_task_in_user_b_project(self):
        """POST to User B's project's task list by User A must return 404."""
        resp = self.client_a.post(
            project_tasks_url(self.proj_b_id),
            {"title": "Sneaky Task", "due_date": future_date()}
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # Confirm no new task was created in User B's project
        tasks = self.client_b.get(project_tasks_url(self.proj_b_id))
        self.assertEqual(tasks.data["count"], 1)  # only B's original task

    def test_same_project_name_allowed_for_different_users(self):
        """
        Both users are allowed to create a project named 'My App' —
        uniqueness is enforced per-user, not globally.
        """
        resp_a = self.client_a.post(PROJECTS_URL, {"name": "My App"})
        resp_b = self.client_b.post(PROJECTS_URL, {"name": "My App"})
        self.assertEqual(resp_a.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_b.status_code, status.HTTP_201_CREATED)
        # They get different IDs
        self.assertNotEqual(resp_a.data["id"], resp_b.data["id"])
