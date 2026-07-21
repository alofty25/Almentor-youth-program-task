from django.urls import path
from .views import ProjectTaskListCreateView, TaskDetailView, GlobalTaskListView

urlpatterns = [
    # Global task list
    path('tasks/', GlobalTaskListView.as_view(), name='global-task-list'),

    # Task detail endpoints
    path('tasks/<int:pk>/', TaskDetailView.as_view(), name='task-detail'),

    # Project-specific tasks
    path('projects/<int:project_id>/tasks/', ProjectTaskListCreateView.as_view(), name='project-tasks'),
]