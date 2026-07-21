"""
integration_tests/test_project_lifecycle.py

Critical Flow 1: Full Project Lifecycle
----------------------------------------
Create project → Add tasks → Mark task as done → Delete project
→ Verify soft-delete cascade

This is the primary end-to-end happy path that exercises the entire
project + task stack through real HTTP calls with real JWT tokens.
"""

import datetime
from django.utils import timezone
from rest_framework import status

from integration_tests.base import (
    IntegrationTestBase,
    PROJECTS_URL, project_detail_url, project_tasks_url, task_detail_url,
)
from projects.models import Project
from tasks.models import Task


def future_date(days=10):
    return (timezone.now() + datetime.timedelta(days=days)).date().isoformat()


class ProjectLifecycleFlowTest(IntegrationTestBase):
    """
    FLOW: Create project → Add tasks → Update task to DONE → Delete project
    Tests the complete happy path from project creation through deletion.
    """

    def setUp(self):
        self.user = self.create_user("lifecycle_user")
        self.client, self.tokens = self.auth_client("lifecycle_user")

    # ------------------------------------------------------------------ #
    # STEP 1: Create a project                                            #
    # ------------------------------------------------------------------ #

    def test_full_project_lifecycle(self):
        """
        End-to-end test of the complete project lifecycle:
          1. Create a project
          2. Add two tasks to it
          3. Mark one task as DONE
          4. Delete the project (triggers cascade soft-delete)
          5. Verify project and tasks are soft-deleted (not hard-deleted)
        """
        # --- Step 1: Create the project ---
        create_resp = self.client.post(PROJECTS_URL, {
            "name": "Lifecycle Project",
            "description": "Full lifecycle test"
        })
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        project_id = create_resp.data["id"]
        self.assertEqual(create_resp.data["name"], "Lifecycle Project")

        # Verify it appears in the list
        list_resp = self.client.get(PROJECTS_URL)
        self.assertEqual(list_resp.data["count"], 1)

        # --- Step 2: Add tasks ---
        task1_resp = self.client.post(project_tasks_url(project_id), {
            "title": "Write unit tests",
            "priority": "high",
            "due_date": future_date(5)
        })
        self.assertEqual(task1_resp.status_code, status.HTTP_201_CREATED)
        task1_id = task1_resp.data["id"]
        self.assertEqual(task1_resp.data["project_id"], project_id)
        self.assertEqual(task1_resp.data["status"], "todo")         # default
        self.assertEqual(task1_resp.data["priority"], "high")

        task2_resp = self.client.post(project_tasks_url(project_id), {
            "title": "Deploy to production",
            "priority": "medium",
            "due_date": future_date(10)
        })
        self.assertEqual(task2_resp.status_code, status.HTTP_201_CREATED)
        task2_id = task2_resp.data["id"]

        # Verify both tasks appear in the project task list
        tasks_list_resp = self.client.get(project_tasks_url(project_id))
        self.assertEqual(tasks_list_resp.data["count"], 2)

        # --- Step 3: Mark task 1 as DONE (transition: todo → done) ---
        done_resp = self.client.put(task_detail_url(task1_id), {
            "title": "Write unit tests",
            "status": "done",
            "priority": "high",
        })
        self.assertEqual(done_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(done_resp.data["status"], "done")

        # Verify the status is persisted
        detail_resp = self.client.get(task_detail_url(task1_id))
        self.assertEqual(detail_resp.data["status"], "done")

        # --- Step 4: Delete the project (soft-delete + cascade) ---
        delete_resp = self.client.delete(project_detail_url(project_id))
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

        # --- Step 5: Verify soft-delete (not hard delete) ---
        # Project hidden from list
        list_after = self.client.get(PROJECTS_URL)
        self.assertEqual(list_after.data["count"], 0)

        # Project still exists in DB
        self.assertTrue(Project.all_objects.filter(pk=project_id).exists())
        project_obj = Project.all_objects.get(pk=project_id)
        self.assertIsNotNone(project_obj.deleted_at)

        # Both tasks are soft-deleted and hidden
        self.assertEqual(Task.objects.filter(project_id=project_id).count(), 0)
        self.assertEqual(Task.all_objects.filter(project_id=project_id).count(), 2)

        # Both tasks have deleted_at set
        for task in Task.all_objects.filter(project_id=project_id):
            self.assertIsNotNone(task.deleted_at)

        # Accessing deleted tasks returns 404
        self.assertEqual(
            self.client.get(task_detail_url(task1_id)).status_code,
            status.HTTP_404_NOT_FOUND
        )
        self.assertEqual(
            self.client.get(task_detail_url(task2_id)).status_code,
            status.HTTP_404_NOT_FOUND
        )


class ProjectCRUDIntegrationTest(IntegrationTestBase):
    """
    Additional project CRUD integration scenarios not covered by the lifecycle flow.
    """

    def setUp(self):
        self.user = self.create_user("crud_user")
        self.client, _ = self.auth_client("crud_user")

    def test_create_project_and_update_description(self):
        """Create a project then update its name and description."""
        resp = self.client.post(PROJECTS_URL, {"name": "Original Name"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pk = resp.data["id"]

        update_resp = self.client.put(project_detail_url(pk), {
            "name": "Updated Name",
            "description": "Now has a description"
        })
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(update_resp.data["name"], "Updated Name")
        self.assertEqual(update_resp.data["description"], "Now has a description")

    def test_create_duplicate_project_name_rejected_end_to_end(self):
        """
        End-to-end: creating two projects with the same name via the API
        must fail on the second attempt with 400.
        """
        self.client.post(PROJECTS_URL, {"name": "Duplicate"})
        resp = self.client.post(PROJECTS_URL, {"name": "Duplicate"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", resp.data)

    def test_project_task_count_is_accurate_after_operations(self):
        """
        Add 3 tasks to a project, soft-delete 1, verify the active count is 2.
        """
        proj = self.client.post(PROJECTS_URL, {"name": "Count Project"})
        pid = proj.data["id"]

        t1 = self.client.post(project_tasks_url(pid), {"title": "T1", "due_date": future_date()})
        t2 = self.client.post(project_tasks_url(pid), {"title": "T2", "due_date": future_date()})
        self.client.post(project_tasks_url(pid), {"title": "T3", "due_date": future_date()})

        self.client.delete(task_detail_url(t1.data["id"]))

        resp = self.client.get(project_tasks_url(pid))
        self.assertEqual(resp.data["count"], 2)
        returned_ids = [t["id"] for t in resp.data["results"]]
        self.assertNotIn(t1.data["id"], returned_ids)
        self.assertIn(t2.data["id"], returned_ids)
