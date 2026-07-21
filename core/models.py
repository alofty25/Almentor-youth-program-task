# core/models.py
from django.db import models
from django.utils import timezone

class ActiveManager(models.Manager):
    """Base manager that filters out soft-deleted items."""
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class BaseModel(models.Model):
    """
    Abstract base model that provides self-updating 'created_at' and 'updated_at' fields,
    along with soft-delete capabilities.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    # Managers
    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True  # This tells Django NOT to create a separate table for this model

    def delete(self, *args, **kwargs):
        """Soft delete the record."""
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.save()

    def hard_delete(self, *args, **kwargs):
        """Permanently remove the record from the database."""
        super().delete(*args, **kwargs)