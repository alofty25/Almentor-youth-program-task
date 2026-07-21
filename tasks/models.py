from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import BaseModel


def validate_due_date(value):
    """Validator to ensure the due_date is today or in the future."""
    if value < timezone.now().date():
        raise ValidationError("Due date cannot be in the past.")


class Task(BaseModel):
    class Status(models.TextChoices):
        TODO = 'todo', 'To Do'
        IN_PROGRESS = 'in_progress', 'In Progress'
        DONE = 'done', 'Done'

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='tasks'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )

    due_date = models.DateField(blank=True, null=True, validators=[validate_due_date])

    class Meta:
        ordering = ['due_date', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"