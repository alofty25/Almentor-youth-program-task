from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Task
from projects.models import Project
from .serializers import TaskSerializer


# 1. Pagination Class to support ?limit= as per PDF
class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'


# 2. Helper function to handle Search, Filter, and Sorting manually
def apply_task_filters(queryset, request):
    # Filters
    if status_param := request.query_params.get('status'):
        queryset = queryset.filter(status=status_param)

    if priority := request.query_params.get('priority'):
        queryset = queryset.filter(priority=priority)

    if due_date_from := request.query_params.get('due_date_from'):
        queryset = queryset.filter(due_date__gte=due_date_from)

    if due_date_to := request.query_params.get('due_date_to'):
        queryset = queryset.filter(due_date__lte=due_date_to)

    # Search (Full-text/partial on title and description)
    if q := request.query_params.get('q'):
        queryset = queryset.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )

    # Sorting (Ascending or Descending)
    if ordering := request.query_params.get('ordering'):
        allowed_sorts = ['due_date', '-due_date', 'priority', '-priority', 'created_at', '-created_at']
        if ordering in allowed_sorts:
            queryset = queryset.order_by(ordering)

    return queryset


# --- THE VIEWS ---

class ProjectTaskListCreateView(APIView):
    """Handles GET /api/projects/:id/tasks and POST /api/projects/:id/tasks"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, project_id):
        # Ensure project exists and belongs to user (Prevents 500 errors, returns clear 404)
        project = get_object_or_404(Project, id=project_id, owner=request.user)

        # select_related prevents N+1 query problem when serializing project_name!
        tasks = Task.objects.filter(project=project).select_related('project')
        tasks = apply_task_filters(tasks, request)

        paginator = self.pagination_class()
        paginated_tasks = paginator.paginate_queryset(tasks, request, view=self)
        serializer = TaskSerializer(paginated_tasks, many=True)

        return paginator.get_paginated_response(serializer.data)

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, owner=request.user)

        serializer = TaskSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(project=project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TaskDetailView(APIView):
    """Handles GET, PUT, DELETE for /api/tasks/:id"""
    permission_classes = [IsAuthenticated]

    def get_task(self, pk, user):
        """Helper to fetch a task and ensure data isolation."""
        return get_object_or_404(Task.objects.select_related('project'), id=pk, project__owner=user)

    def get(self, request, pk):
        task = self.get_task(pk, request.user)
        serializer = TaskSerializer(task)
        return Response(serializer.data)

    def put(self, request, pk):
        task = self.get_task(pk, request.user)
        serializer = TaskSerializer(task, data=request.data, context={'request': request})

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        task = self.get_task(pk, request.user)
        task.delete()  # Triggers our soft delete
        return Response(status=status.HTTP_204_NO_CONTENT)


class GlobalTaskListView(APIView):
    """Handles GET /api/tasks (List all tasks across all projects)"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        # Fetch all tasks belonging to any project owned by the user
        tasks = Task.objects.filter(project__owner=request.user).select_related('project')
        tasks = apply_task_filters(tasks, request)

        paginator = self.pagination_class()
        paginated_tasks = paginator.paginate_queryset(tasks, request, view=self)
        serializer = TaskSerializer(paginated_tasks, many=True)

        return paginator.get_paginated_response(serializer.data)