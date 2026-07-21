"""
tasks/tests/test_views.py

Unit tests for the task API views (tasks/views.py):
  - GlobalTaskListView   : GET /api/tasks/
  - ProjectTaskListCreateView : GET+POST /api/projects/:id/tasks/
  - TaskDetailView        : GET, PUT, DELETE /api/tasks/:id/

Tests enforce: authentication, data isolation, correct status codes,
and soft-delete behaviour.
"""

import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project
from tasks.models import Task

User = get_user_model()

GLOBAL_TASKS_URL = "/api/tasks/"
TASK_DETAIL_URL = lambda pk: f"/api/tasks/{pk}/"
PROJECT_TASKS_URL = lambda pid: f"/api/projects/{pid}/tasks/"


def _future_date(days=10):
    return (timezone.now() + datetime.timedelta(days=days)).date().isoformat()


class TaskViewAuthenticationTestCase(TestCase):
    """All task endpoints require authentication."""

    def setUp(self):
        self.client = APIClient()

    def test_global_task_list_unauthenticated_returns_401(self):
        response = self.client.get(GLOBAL_TASKS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_project_task_list_unauthenticated_returns_401(self):
        response = self.client.get(PROJECT_TASKS_URL(1))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_task_detail_unauthenticated_returns_401(self):
        response = self.client.get(TASK_DETAIL_URL(1))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class GlobalTaskListViewTestCase(TestCase):
    """Tests for GET /api/tasks/ — GlobalTaskListView."""

    def setUp(self):
        self.user1 = User.objects.create_user(username="rachel", password="pass1234")
        self.user2 = User.objects.create_user(username="sam", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

        self.project1 = Project.objects.create(owner=self.user1, name="R Project")
        self.project2 = Project.objects.create(owner=self.user2, name="S Project")

        self.task1 = Task.objects.create(project=self.project1, title="R Task 1", due_date=_future_date())
        self.task2 = Task.objects.create(project=self.project1, title="R Task 2", due_date=_future_date())
        self.task3 = Task.objects.create(project=self.project2, title="S Task 1", due_date=_future_date())

    def test_global_list_returns_only_authenticated_users_tasks(self):
        """Data isolation: user1 must only see tasks in their own projects."""
        response = self.client.get(GLOBAL_TASKS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = [t["id"] for t in response.data["results"]]
        self.assertIn(self.task1.pk, returned_ids)
        self.assertIn(self.task2.pk, returned_ids)
        self.assertNotIn(self.task3.pk, returned_ids)

    def test_global_list_response_count_is_correct(self):
        """Global list should return exactly the number of tasks owned by user1."""
        response = self.client.get(GLOBAL_TASKS_URL)
        self.assertEqual(response.data["count"], 2)

    def test_global_list_each_task_has_project_name(self):
        """Each task in the global list must include 'project_name'."""
        response = self.client.get(GLOBAL_TASKS_URL)
        for task in response.data["results"]:
            self.assertIn("project_name", task)
            self.assertIsNotNone(task["project_name"])

    def test_global_list_hides_soft_deleted_tasks(self):
        """Soft-deleted tasks must not appear in the global list."""
        self.task1.delete()
        response = self.client.get(GLOBAL_TASKS_URL)
        returned_ids = [t["id"] for t in response.data["results"]]
        self.assertNotIn(self.task1.pk, returned_ids)


class ProjectTaskListCreateViewTestCase(TestCase):
    """Tests for GET and POST /api/projects/:id/tasks/."""

    def setUp(self):
        self.user1 = User.objects.create_user(username="tina", password="pass1234")
        self.user2 = User.objects.create_user(username="ugo", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

        self.project = Project.objects.create(owner=self.user1, name="Tina's Project")
        self.other_project = Project.objects.create(owner=self.user2, name="Ugo's Project")

        self.task = Task.objects.create(
            project=self.project, title="Tina Task", due_date=_future_date()
        )

    # ------------------------------------------------------------------ #
    # GET — project task list                                              #
    # ------------------------------------------------------------------ #

    def test_list_tasks_for_own_project_returns_200(self):
        response = self.client.get(PROJECT_TASKS_URL(self.project.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_tasks_for_nonexistent_project_returns_404(self):
        response = self.client.get(PROJECT_TASKS_URL(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_tasks_for_other_users_project_returns_404(self):
        """Data isolation: user1 cannot list tasks under user2's project."""
        response = self.client.get(PROJECT_TASKS_URL(self.other_project.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_returns_only_tasks_for_that_project(self):
        """Tasks from other projects must not bleed into this project's list."""
        other_task = Task.objects.create(
            project=Project.objects.create(owner=self.user1, name="Another Project"),
            title="Another Task", due_date=_future_date()
        )
        response = self.client.get(PROJECT_TASKS_URL(self.project.pk))
        returned_ids = [t["id"] for t in response.data["results"]]
        self.assertIn(self.task.pk, returned_ids)
        self.assertNotIn(other_task.pk, returned_ids)

    # ------------------------------------------------------------------ #
    # POST — create task in project                                        #
    # ------------------------------------------------------------------ #

    def test_create_task_returns_201_with_valid_data(self):
        payload = {"title": "New Task", "due_date": _future_date()}
        response = self.client.post(PROJECT_TASKS_URL(self.project.pk), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_task_response_payload_has_expected_fields(self):
        payload = {"title": "Payload Task", "due_date": _future_date(), "priority": "high"}
        response = self.client.post(PROJECT_TASKS_URL(self.project.pk), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Payload Task")
        self.assertEqual(response.data["priority"], "high")
        self.assertEqual(response.data["project_id"], self.project.pk)
        self.assertIn("id", response.data)

    def test_create_task_sets_correct_project(self):
        """The created task must be associated with the project in the URL."""
        payload = {"title": "Linked Task", "due_date": _future_date()}
        response = self.client.post(PROJECT_TASKS_URL(self.project.pk), payload)
        task = Task.objects.get(pk=response.data["id"])
        self.assertEqual(task.project_id, self.project.pk)

    def test_create_task_missing_title_returns_400(self):
        """Title is required; omitting it must return 400."""
        response = self.client.post(PROJECT_TASKS_URL(self.project.pk), {"due_date": _future_date()})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_task_with_past_due_date_returns_400(self):
        """A due date in the past must fail model validation and return 400."""
        past_date = (timezone.now() - datetime.timedelta(days=1)).date().isoformat()
        response = self.client.post(
            PROJECT_TASKS_URL(self.project.pk),
            {"title": "Past Task", "due_date": past_date}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_task_in_other_users_project_returns_404(self):
        """Data isolation: user1 cannot create a task in user2's project."""
        response = self.client.post(
            PROJECT_TASKS_URL(self.other_project.pk),
            {"title": "Sneaky Task", "due_date": _future_date()}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_task_with_invalid_status_returns_400(self):
        """An invalid status value must return 400."""
        response = self.client.post(
            PROJECT_TASKS_URL(self.project.pk),
            {"title": "Bad Status", "status": "flying", "due_date": _future_date()}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TaskDetailViewTestCase(TestCase):
    """Tests for GET, PUT, DELETE /api/tasks/:id/ — TaskDetailView."""

    def setUp(self):
        self.user1 = User.objects.create_user(username="victor", password="pass1234")
        self.user2 = User.objects.create_user(username="wendy", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)

        self.project = Project.objects.create(owner=self.user1, name="Victor's Project")
        self.other_project = Project.objects.create(owner=self.user2, name="Wendy's Project")
        self.task = Task.objects.create(
            project=self.project, title="Victor's Task", due_date=_future_date()
        )
        self.other_task = Task.objects.create(
            project=self.other_project, title="Wendy's Task", due_date=_future_date()
        )

    # ------------------------------------------------------------------ #
    # GET — retrieve                                                       #
    # ------------------------------------------------------------------ #

    def test_retrieve_own_task_returns_200(self):
        response = self.client.get(TASK_DETAIL_URL(self.task.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Victor's Task")

    def test_retrieve_task_response_contains_project_name(self):
        """Detail view must include 'project_name' for context."""
        response = self.client.get(TASK_DETAIL_URL(self.task.pk))
        self.assertEqual(response.data["project_name"], "Victor's Project")

    def test_retrieve_other_users_task_returns_404(self):
        """Data isolation: user1 cannot access user2's task."""
        response = self.client.get(TASK_DETAIL_URL(self.other_task.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_nonexistent_task_returns_404(self):
        response = self.client.get(TASK_DETAIL_URL(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------ #
    # PUT — full update                                                    #
    # ------------------------------------------------------------------ #

    def test_update_task_returns_200_with_new_data(self):
        payload = {
            "title": "Updated Task",
            "status": "in_progress",
            "priority": "high",
            "due_date": _future_date(days=15),
        }
        response = self.client.put(TASK_DETAIL_URL(self.task.pk), payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Task")
        self.assertEqual(response.data["status"], "in_progress")
        self.assertEqual(response.data["priority"], "high")

    def test_update_persists_changes_to_database(self):
        """Updated values must be reflected in the database."""
        self.client.put(
            TASK_DETAIL_URL(self.task.pk),
            {"title": "DB Persisted", "status": "done", "priority": "low"}
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "DB Persisted")
        self.assertEqual(self.task.status, Task.Status.DONE)

    def test_update_other_users_task_returns_404(self):
        """Data isolation: user1 cannot update user2's task."""
        response = self.client.put(
            TASK_DETAIL_URL(self.other_task.pk),
            {"title": "Hacked", "status": "done", "priority": "high"}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------ #
    # DELETE — soft delete                                                 #
    # ------------------------------------------------------------------ #

    def test_delete_task_returns_204(self):
        response = self.client.delete(TASK_DETAIL_URL(self.task.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_soft_deletes_task_not_hard_delete(self):
        """After DELETE, the task row must still exist in all_objects."""
        self.client.delete(TASK_DETAIL_URL(self.task.pk))
        self.assertTrue(Task.all_objects.filter(pk=self.task.pk).exists())

    def test_delete_hides_task_from_global_list(self):
        """After DELETE, the task must not appear in GET /api/tasks/."""
        self.client.delete(TASK_DETAIL_URL(self.task.pk))
        response = self.client.get(GLOBAL_TASKS_URL)
        returned_ids = [t["id"] for t in response.data["results"]]
        self.assertNotIn(self.task.pk, returned_ids)

    def test_delete_other_users_task_returns_404(self):
        """Data isolation: user1 cannot delete user2's task."""
        response = self.client.delete(TASK_DETAIL_URL(self.other_task.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleted_task_returns_404_on_subsequent_get(self):
        """After soft-delete, a GET on the same task ID must return 404."""
        self.client.delete(TASK_DETAIL_URL(self.task.pk))
        response = self.client.get(TASK_DETAIL_URL(self.task.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
