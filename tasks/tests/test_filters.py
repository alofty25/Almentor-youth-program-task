"""
tasks/tests/test_filters.py

Unit tests for the apply_task_filters() helper function (tasks/views.py).

apply_task_filters() is a pure queryset-transformation function. We test it
by constructing real Task querysets from in-memory test data and asserting
the filtered results are correct — no HTTP layer involved.
"""

import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import MagicMock

from projects.models import Project
from tasks.models import Task
from tasks.views import apply_task_filters

User = get_user_model()


def _date(days_from_now):
    """Helper: return a date offset from today."""
    return (timezone.now() + datetime.timedelta(days=days_from_now)).date()


def _mock_request(**params):
    """
    Helper: build a mock request object whose query_params behave like a
    dict with .get() support — no actual HTTP required.

    Note: **params is already a plain dict, so its .get() works natively.
    We assign it directly; no override needed (and none is possible on a real dict).
    """
    request = MagicMock()
    request.query_params = params
    return request


class ApplyTaskFiltersStatusTestCase(TestCase):
    """Tests for status= filter parameter."""

    def setUp(self):
        user = User.objects.create_user(username="filter_user_status", password="pass")
        project = Project.objects.create(owner=user, name="Filter Project")
        self.todo_task = Task.objects.create(
            project=project, title="Todo Task", status=Task.Status.TODO, due_date=_date(5)
        )
        self.done_task = Task.objects.create(
            project=project, title="Done Task", status=Task.Status.DONE, due_date=_date(5)
        )
        self.base_qs = Task.objects.filter(project=project)

    def test_filter_by_status_todo_returns_only_todo_tasks(self):
        request = _mock_request(status="todo")
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.todo_task, result)
        self.assertNotIn(self.done_task, result)

    def test_filter_by_status_done_returns_only_done_tasks(self):
        request = _mock_request(status="done")
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.done_task, result)
        self.assertNotIn(self.todo_task, result)

    def test_filter_by_invalid_status_returns_empty_queryset(self):
        """An unrecognised status value must return an empty queryset."""
        request = _mock_request(status="flying")
        result = apply_task_filters(self.base_qs, request)
        self.assertEqual(result.count(), 0)

    def test_no_status_filter_returns_all_tasks(self):
        """Without a status param, the queryset must be returned unfiltered."""
        request = _mock_request()
        result = apply_task_filters(self.base_qs, request)
        self.assertEqual(result.count(), 2)


class ApplyTaskFiltersPriorityTestCase(TestCase):
    """Tests for priority= filter parameter."""

    def setUp(self):
        user = User.objects.create_user(username="filter_user_priority", password="pass")
        project = Project.objects.create(owner=user, name="Priority Project")
        self.low_task = Task.objects.create(
            project=project, title="Low Task", priority=Task.Priority.LOW, due_date=_date(5)
        )
        self.high_task = Task.objects.create(
            project=project, title="High Task", priority=Task.Priority.HIGH, due_date=_date(5)
        )
        self.base_qs = Task.objects.filter(project=project)

    def test_filter_by_priority_low_returns_only_low_priority_tasks(self):
        request = _mock_request(priority="low")
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.low_task, result)
        self.assertNotIn(self.high_task, result)

    def test_filter_by_priority_high_returns_only_high_priority_tasks(self):
        request = _mock_request(priority="high")
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.high_task, result)
        self.assertNotIn(self.low_task, result)


class ApplyTaskFiltersDateRangeTestCase(TestCase):
    """Tests for due_date_from= and due_date_to= filter parameters."""

    def setUp(self):
        user = User.objects.create_user(username="filter_user_date", password="pass")
        project = Project.objects.create(owner=user, name="Date Project")
        self.early_task = Task.objects.create(
            project=project, title="Early Task", due_date=_date(5)
        )
        self.mid_task = Task.objects.create(
            project=project, title="Mid Task", due_date=_date(15)
        )
        self.late_task = Task.objects.create(
            project=project, title="Late Task", due_date=_date(30)
        )
        self.base_qs = Task.objects.filter(project=project)

    def test_due_date_from_filters_out_earlier_tasks(self):
        """Tasks before due_date_from must be excluded."""
        request = _mock_request(due_date_from=_date(10).isoformat())
        result = apply_task_filters(self.base_qs, request)
        self.assertNotIn(self.early_task, result)
        self.assertIn(self.mid_task, result)
        self.assertIn(self.late_task, result)

    def test_due_date_to_filters_out_later_tasks(self):
        """Tasks after due_date_to must be excluded."""
        request = _mock_request(due_date_to=_date(20).isoformat())
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.early_task, result)
        self.assertIn(self.mid_task, result)
        self.assertNotIn(self.late_task, result)

    def test_due_date_range_inclusive_boundaries(self):
        """
        Boundary test: tasks exactly at due_date_from or due_date_to must be included.
        """
        boundary_date = _date(5).isoformat()
        request = _mock_request(due_date_from=boundary_date, due_date_to=boundary_date)
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.early_task, result)
        self.assertNotIn(self.mid_task, result)

    def test_combined_date_range_narrows_results(self):
        """Combining due_date_from and due_date_to returns tasks within the window."""
        request = _mock_request(
            due_date_from=_date(10).isoformat(),
            due_date_to=_date(20).isoformat()
        )
        result = apply_task_filters(self.base_qs, request)
        self.assertNotIn(self.early_task, result)
        self.assertIn(self.mid_task, result)
        self.assertNotIn(self.late_task, result)


class ApplyTaskFiltersSearchTestCase(TestCase):
    """Tests for q= (search) filter parameter."""

    def setUp(self):
        user = User.objects.create_user(username="filter_user_search", password="pass")
        project = Project.objects.create(owner=user, name="Search Project")
        self.task_a = Task.objects.create(
            project=project, title="Fix Login Bug", description="Authentication issue"
        )
        self.task_b = Task.objects.create(
            project=project, title="Write Documentation", description="Covers the login flow"
        )
        self.task_c = Task.objects.create(
            project=project, title="Deploy to Production", description="Server upgrade"
        )
        self.base_qs = Task.objects.filter(project=project)

    def test_search_matches_title_case_insensitive(self):
        """q= should match against task title regardless of case."""
        request = _mock_request(q="fix")
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.task_a, result)
        self.assertNotIn(self.task_b, result)
        self.assertNotIn(self.task_c, result)

    def test_search_matches_description_case_insensitive(self):
        """q= should match against task description regardless of case."""
        request = _mock_request(q="login")
        result = apply_task_filters(self.base_qs, request)
        # 'login' appears in task_a title AND task_b description
        self.assertIn(self.task_a, result)
        self.assertIn(self.task_b, result)
        self.assertNotIn(self.task_c, result)

    def test_search_with_no_matches_returns_empty_queryset(self):
        """q= with a term that matches nothing must return an empty queryset."""
        request = _mock_request(q="xylophone")
        result = apply_task_filters(self.base_qs, request)
        self.assertEqual(result.count(), 0)

    def test_search_partial_match_works(self):
        """q= should do partial matching (icontains), not exact match."""
        request = _mock_request(q="Doc")
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.task_b, result)


class ApplyTaskFiltersSortingTestCase(TestCase):
    """Tests for ordering= sort parameter."""

    def setUp(self):
        user = User.objects.create_user(username="filter_user_sort", password="pass")
        project = Project.objects.create(owner=user, name="Sort Project")
        self.task_near = Task.objects.create(
            project=project, title="Near Task", due_date=_date(3)
        )
        self.task_far = Task.objects.create(
            project=project, title="Far Task", due_date=_date(20)
        )
        self.base_qs = Task.objects.filter(project=project)

    def test_ordering_by_due_date_ascending(self):
        """ordering=due_date should put nearer due dates first."""
        request = _mock_request(ordering="due_date")
        result = list(apply_task_filters(self.base_qs, request))
        self.assertEqual(result[0], self.task_near)
        self.assertEqual(result[1], self.task_far)

    def test_ordering_by_due_date_descending(self):
        """ordering=-due_date should put farther due dates first."""
        request = _mock_request(ordering="-due_date")
        result = list(apply_task_filters(self.base_qs, request))
        self.assertEqual(result[0], self.task_far)
        self.assertEqual(result[1], self.task_near)

    def test_invalid_ordering_key_is_silently_ignored(self):
        """
        Security: an unrecognised ordering key (e.g. SQL injection attempt)
        must be silently ignored, returning the default ordering.
        The queryset should still return results, just not with the bad ordering.
        """
        request = _mock_request(ordering="password; DROP TABLE tasks;")
        result = apply_task_filters(self.base_qs, request)
        # Must not raise and must still return both tasks
        self.assertEqual(result.count(), 2)

    def test_no_ordering_param_uses_model_default_ordering(self):
        """Without an ordering param, the queryset uses the model's Meta.ordering."""
        request = _mock_request()
        result = apply_task_filters(self.base_qs, request)
        self.assertEqual(result.count(), 2)


class ApplyTaskFiltersCombinedTestCase(TestCase):
    """Tests combining multiple filters simultaneously."""

    def setUp(self):
        user = User.objects.create_user(username="filter_user_combo", password="pass")
        project = Project.objects.create(owner=user, name="Combo Project")
        self.match = Task.objects.create(
            project=project, title="Fix Auth Bug",
            status=Task.Status.IN_PROGRESS, priority=Task.Priority.HIGH,
            due_date=_date(10)
        )
        self.no_match_status = Task.objects.create(
            project=project, title="Fix Auth Bug",
            status=Task.Status.TODO, priority=Task.Priority.HIGH,
            due_date=_date(10)
        )
        self.no_match_search = Task.objects.create(
            project=project, title="Deploy App",
            status=Task.Status.IN_PROGRESS, priority=Task.Priority.HIGH,
            due_date=_date(10)
        )
        self.base_qs = Task.objects.filter(project=project)

    def test_combined_status_and_search_filter(self):
        """Combining status= and q= must return only tasks matching BOTH conditions."""
        request = _mock_request(status="in_progress", q="Fix Auth")
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.match, result)
        self.assertNotIn(self.no_match_status, result)   # wrong status
        self.assertNotIn(self.no_match_search, result)   # wrong title

    def test_combined_priority_status_and_date_filter(self):
        """Triple-filter: priority + status + date range must correctly intersect."""
        request = _mock_request(
            priority="high",
            status="in_progress",
            due_date_from=_date(5).isoformat(),
            due_date_to=_date(15).isoformat()
        )
        result = apply_task_filters(self.base_qs, request)
        self.assertIn(self.match, result)
        self.assertNotIn(self.no_match_status, result)
