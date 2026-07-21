from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Project
from .serializers import ProjectSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated] # Locks down the API to logged-in users

    def get_queryset(self):
        """
        Data Isolation: Users can only see their own projects.
        Because of our ActiveManager, this automatically hides soft-deleted projects too.
        """
        return Project.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        """
        Automatically set the owner of the project to the user making the request.
        """
        serializer.save(owner=self.request.user)