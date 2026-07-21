from django.db import models
from django.conf import settings
from core.models import BaseModel


class Project(BaseModel):
    # Link the project to a specific user
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        # Bonus Data Integrity: A user shouldn't have duplicate project names,
        # but User A and User B can both have a project named "Website".
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='unique_project_name_per_user')
        ]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


    def delete(self, *args, **kwargs):
        """Soft delete the project and cascade soft-delete its tasks."""
        # self.tasks.all() works because we set related_name='tasks' in the Task model
        for task in self.tasks.all():
            task.delete()

        # Call the parent BaseModel delete to soft-delete the project itself
        super().delete(*args, **kwargs)