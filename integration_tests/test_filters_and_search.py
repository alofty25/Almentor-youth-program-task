"""
integration_tests/test_filters_and_search.py

Critical Flows 2 & 3: Filter by Status/Priority + Search + Pagination
-----------------------------------------------------------------------
Flow 2: Filter tasks by status and priority
Flow 3: Search tasks and verify pagination

These tests create realistic datasets and exercise the apply_task_filters()
function through the full HTTP stack — verifying the entire chain from
query param → filter logic → serializer → paginated response.
"""

import datetime
from django.utils import timezone
from rest_framework import status

from integration_tests.base import (
    IntegrationTestBase,
    PROJECTS_URL, TASKS_URL, project_tasks_url, project_detail_url, task_detail_url,
)
from tasks.models import Task


def future_date(days=10):
    return (timezone.now() + datetime.timedelta(days=days)).date().isoformat()


class TaskFilterByStatusAndPriorityTest(IntegrationTestBase):
    """
    FLOW 2: Create a varied set of tasks, then verify all filter combinations
    return precisely the correct subset.
    """

    def setUp(self):
        self.user = self.create_user("filter_integration_user")
        self.client, _ = self.auth_client("filter_integration_user")

        # Create a project
        proj = self.client.post(PROJECTS_URL, {"name": "Filter Project"})
        self.project_id = proj.data["id"]
        url = project_tasks_url(self.project_id)

        # Seed 6 tasks with distinct status/priority combinations
        self.t_todo_high = self.client.post(url, {
            "title": "Todo High Task",
            "status": "todo", "priority": "high", "due_date": future_date(5)
        }).data["id"]
        self.t_todo_low = self.client.post(url, {
            "title": "Todo Low Task",
            "status": "todo", "priority": "low", "due_date": future_date(8)
        }).data["id"]
        self.t_inprog_high = self.client.post(url, {
            "title": "In Progress High Task",
            "status": "in_progress", "priority": "high", "due_date": future_date(10)
        }).data["id"]
        self.t_inprog_med = self.client.post(url, {
            "title": "In Progress Medium Task",
            "status": "in_progress", "priority": "medium", "due_date": future_date(15)
        }).data["id"]
        self.t_done_med = self.client.post(url, {
            "title": "Done Medium Task",
            "status": "done", "priority": "medium", "due_date": future_date(20)
        }).data["id"]
        self.t_done_low = self.client.post(url, {
            "title": "Done Low Task",
            "status": "done", "priority": "low", "due_date": future_date(25)
        }).data["id"]

    def _ids(self, response):
        return [t["id"] for t in response.data["results"]]

    # ------------------------------------------------------------------ #
    # Status filters                                                       #
    # ------------------------------------------------------------------ #

    def test_filter_status_todo_returns_only_todo_tasks(self):
        resp = self.client.get(TASKS_URL, {"status": "todo"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = self._ids(resp)
        self.assertIn(self.t_todo_high, ids)
        self.assertIn(self.t_todo_low, ids)
        self.assertNotIn(self.t_inprog_high, ids)
        self.assertNotIn(self.t_done_med, ids)
        self.assertEqual(resp.data["count"], 2)

    def test_filter_status_in_progress_returns_correct_tasks(self):
        resp = self.client.get(TASKS_URL, {"status": "in_progress"})
        ids = self._ids(resp)
        self.assertIn(self.t_inprog_high, ids)
        self.assertIn(self.t_inprog_med, ids)
        self.assertEqual(resp.data["count"], 2)

    def test_filter_status_done_returns_correct_tasks(self):
        resp = self.client.get(TASKS_URL, {"status": "done"})
        ids = self._ids(resp)
        self.assertIn(self.t_done_med, ids)
        self.assertIn(self.t_done_low, ids)
        self.assertEqual(resp.data["count"], 2)

    # ------------------------------------------------------------------ #
    # Priority filters                                                     #
    # ------------------------------------------------------------------ #

    def test_filter_priority_high_returns_only_high_priority(self):
        resp = self.client.get(TASKS_URL, {"priority": "high"})
        ids = self._ids(resp)
        self.assertIn(self.t_todo_high, ids)
        self.assertIn(self.t_inprog_high, ids)
        self.assertNotIn(self.t_todo_low, ids)
        self.assertNotIn(self.t_done_med, ids)
        self.assertEqual(resp.data["count"], 2)

    def test_filter_priority_low_returns_only_low_priority(self):
        resp = self.client.get(TASKS_URL, {"priority": "low"})
        ids = self._ids(resp)
        self.assertIn(self.t_todo_low, ids)
        self.assertIn(self.t_done_low, ids)
        self.assertEqual(resp.data["count"], 2)

    # ------------------------------------------------------------------ #
    # Combined status + priority                                           #
    # ------------------------------------------------------------------ #

    def test_filter_combined_status_todo_and_priority_high(self):
        """Only the task that is BOTH todo AND high priority should be returned."""
        resp = self.client.get(TASKS_URL, {"status": "todo", "priority": "high"})
        ids = self._ids(resp)
        self.assertEqual(resp.data["count"], 1)
        self.assertIn(self.t_todo_high, ids)

    def test_filter_combined_in_progress_and_medium_returns_one(self):
        resp = self.client.get(TASKS_URL, {"status": "in_progress", "priority": "medium"})
        self.assertEqual(resp.data["count"], 1)
        self.assertIn(self.t_inprog_med, self._ids(resp))

    def test_filter_with_no_matching_combination_returns_empty(self):
        """done + high priority: no tasks match this combination in our seed data."""
        resp = self.client.get(TASKS_URL, {"status": "done", "priority": "high"})
        self.assertEqual(resp.data["count"], 0)

    # ------------------------------------------------------------------ #
    # Date range filters                                                   #
    # ------------------------------------------------------------------ #

    def test_filter_due_date_from_excludes_earlier_tasks(self):
        """Only tasks due 12+ days from now should appear."""
        cutoff = future_date(12)
        resp = self.client.get(TASKS_URL, {"due_date_from": cutoff})
        ids = self._ids(resp)
        self.assertNotIn(self.t_todo_high, ids)   # due in 5 days
        self.assertNotIn(self.t_todo_low, ids)    # due in 8 days
        self.assertNotIn(self.t_inprog_high, ids) # due in 10 days
        self.assertIn(self.t_inprog_med, ids)     # due in 15 days
        self.assertIn(self.t_done_med, ids)       # due in 20 days
        self.assertIn(self.t_done_low, ids)       # due in 25 days

    def test_filter_due_date_to_excludes_later_tasks(self):
        """Only tasks due within 12 days should appear."""
        cutoff = future_date(12)
        resp = self.client.get(TASKS_URL, {"due_date_to": cutoff})
        ids = self._ids(resp)
        self.assertIn(self.t_todo_high, ids)
        self.assertIn(self.t_todo_low, ids)
        self.assertIn(self.t_inprog_high, ids)
        self.assertNotIn(self.t_inprog_med, ids)

    def test_filter_combined_date_range(self):
        """Tasks due between day 7 and day 16 from now (inclusive)."""
        resp = self.client.get(TASKS_URL, {
            "due_date_from": future_date(7),
            "due_date_to": future_date(16),
        })
        ids = self._ids(resp)
        self.assertNotIn(self.t_todo_high, ids)   # day 5
        self.assertIn(self.t_todo_low, ids)       # day 8
        self.assertIn(self.t_inprog_high, ids)    # day 10
        self.assertIn(self.t_inprog_med, ids)     # day 15
        self.assertNotIn(self.t_done_med, ids)    # day 20

    # ------------------------------------------------------------------ #
    # Sorting                                                              #
    # ------------------------------------------------------------------ #

    def test_ordering_by_due_date_ascending_via_api(self):
        """ordering=due_date should return tasks from nearest to furthest due date."""
        resp = self.client.get(TASKS_URL, {"ordering": "due_date"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        due_dates = [t["due_date"] for t in resp.data["results"]]
        self.assertEqual(due_dates, sorted(due_dates))

    def test_ordering_by_due_date_descending_via_api(self):
        """ordering=-due_date should return tasks from furthest to nearest due date."""
        resp = self.client.get(TASKS_URL, {"ordering": "-due_date"})
        due_dates = [t["due_date"] for t in resp.data["results"]]
        self.assertEqual(due_dates, sorted(due_dates, reverse=True))

    def test_invalid_ordering_key_does_not_crash_api(self):
        """An unrecognised ordering key must be silently ignored, not cause a 500."""
        resp = self.client.get(TASKS_URL, {"ordering": "invalid_field"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 6)

    # ------------------------------------------------------------------ #
    # Project-scoped filters                                               #
    # ------------------------------------------------------------------ #

    def test_project_scoped_filter_by_status(self):
        """Status filter also works via the project-scoped task endpoint."""
        resp = self.client.get(project_tasks_url(self.project_id), {"status": "done"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 2)
        for task in resp.data["results"]:
            self.assertEqual(task["status"], "done")


class TaskSearchAndPaginationTest(IntegrationTestBase):
    """
    FLOW 3: Search tasks by keyword, verify pagination behaviour.
    Creates 15 tasks to exercise the default page size of 10.
    """

    def setUp(self):
        self.user = self.create_user("search_pagination_user")
        self.client, _ = self.auth_client("search_pagination_user")

        proj = self.client.post(PROJECTS_URL, {"name": "Search Project"})
        self.project_id = proj.data["id"]
        url = project_tasks_url(self.project_id)

        # 15 tasks: 8 with "authentication" keyword, 7 without
        self.auth_task_ids = []
        for i in range(1, 9):
            resp = self.client.post(url, {
                "title": f"Fix authentication bug #{i}",
                "description": "JWT token issue",
                "due_date": future_date(i)
            })
            self.auth_task_ids.append(resp.data["id"])

        for i in range(1, 8):
            self.client.post(url, {
                "title": f"Deploy service #{i}",
                "description": "Infrastructure task",
                "due_date": future_date(i + 8)
            })

    # ------------------------------------------------------------------ #
    # Search tests                                                         #
    # ------------------------------------------------------------------ #

    def test_search_by_title_keyword_returns_matching_tasks(self):
        """q=authentication should return only the 8 tasks with that keyword in the title."""
        resp = self.client.get(TASKS_URL, {"q": "authentication"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 8)
        for task in resp.data["results"]:
            self.assertIn("authentication", task["title"].lower())

    def test_search_by_description_keyword(self):
        """q=JWT should match tasks whose description contains 'JWT'."""
        resp = self.client.get(TASKS_URL, {"q": "JWT"})
        self.assertEqual(resp.data["count"], 8)

    def test_search_is_case_insensitive(self):
        """q=AUTHENTICATION (uppercase) must match the same results as q=authentication."""
        lower_resp = self.client.get(TASKS_URL, {"q": "authentication"})
        upper_resp = self.client.get(TASKS_URL, {"q": "AUTHENTICATION"})
        self.assertEqual(lower_resp.data["count"], upper_resp.data["count"])
        lower_ids = {t["id"] for t in lower_resp.data["results"]}
        upper_ids = {t["id"] for t in upper_resp.data["results"]}
        self.assertEqual(lower_ids, upper_ids)

    def test_search_with_no_matching_term_returns_empty(self):
        """q=xylophone should return 0 results."""
        resp = self.client.get(TASKS_URL, {"q": "xylophone"})
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(resp.data["results"], [])

    def test_search_partial_match(self):
        """q=auth (partial) should still match tasks containing 'authentication'."""
        resp = self.client.get(TASKS_URL, {"q": "auth"})
        self.assertEqual(resp.data["count"], 8)

    def test_search_combined_with_status_filter(self):
        """
        Combine q= and status= to get a highly specific subset.
        Mark 3 of the auth tasks as done, then filter for done + auth.
        """
        for task_id in self.auth_task_ids[:3]:
            self.client.put(task_detail_url(task_id), {
                "title": f"Fix authentication bug",
                "status": "done",
                "priority": "medium"
            })

        resp = self.client.get(TASKS_URL, {"q": "authentication", "status": "done"})
        self.assertEqual(resp.data["count"], 3)
        for task in resp.data["results"]:
            self.assertEqual(task["status"], "done")
            self.assertIn("authentication", task["title"].lower())

    # ------------------------------------------------------------------ #
    # Pagination tests                                                     #
    # ------------------------------------------------------------------ #

    def test_default_page_returns_10_results(self):
        """With 15 tasks total, the first page must contain 10 results (default page size)."""
        resp = self.client.get(TASKS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 15)
        self.assertEqual(len(resp.data["results"]), 10)

    def test_second_page_returns_remaining_5_results(self):
        """The second page must contain the remaining 5 tasks."""
        resp = self.client.get(TASKS_URL, {"page": 2})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 5)

    def test_pagination_response_contains_next_and_previous_links(self):
        """First page must have a 'next' link and no 'previous' link."""
        resp = self.client.get(TASKS_URL)
        self.assertIsNotNone(resp.data["next"])
        self.assertIsNone(resp.data["previous"])

    def test_second_page_has_previous_link_and_no_next(self):
        """Second (last) page must have a 'previous' link and no 'next' link."""
        resp = self.client.get(TASKS_URL, {"page": 2})
        self.assertIsNotNone(resp.data["previous"])
        self.assertIsNone(resp.data["next"])

    def test_pagination_covers_all_tasks_without_duplicates(self):
        """Fetching both pages and combining must give all 15 unique task IDs."""
        page1 = self.client.get(TASKS_URL)
        page2 = self.client.get(TASKS_URL, {"page": 2})
        all_ids = (
            [t["id"] for t in page1.data["results"]] +
            [t["id"] for t in page2.data["results"]]
        )
        self.assertEqual(len(all_ids), 15)
        self.assertEqual(len(set(all_ids)), 15)  # no duplicates

    def test_custom_page_size_via_limit_param(self):
        """?limit=5 should return only 5 results per page."""
        resp = self.client.get(TASKS_URL, {"limit": 5})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 5)
        self.assertEqual(resp.data["count"], 15)

    def test_search_result_pagination(self):
        """
        Search for 'authentication' (8 results) with limit=5.
        Verifies pagination works correctly on filtered results.
        """
        resp = self.client.get(TASKS_URL, {"q": "authentication", "limit": 5})
        self.assertEqual(resp.data["count"], 8)
        self.assertEqual(len(resp.data["results"]), 5)
        self.assertIsNotNone(resp.data["next"])

    def test_out_of_range_page_returns_404(self):
        """Requesting a page that doesn't exist must return 404."""
        resp = self.client.get(TASKS_URL, {"page": 999})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
