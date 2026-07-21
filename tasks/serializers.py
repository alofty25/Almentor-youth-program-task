import logging
from rest_framework import serializers
from .models import Task

logger = logging.getLogger(__name__)


class TaskSerializer(serializers.ModelSerializer):
    # Each task must include its project's name
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'project_id', 'project_name', 'title', 'description',
            'status', 'priority', 'due_date', 'created_at', 'updated_at'
        ]
        # Project ID is set via the URL, so it's read-only here
        read_only_fields = ['id', 'project_id', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        """
        Business Rule: Status transitions are allowed, but done -> todo is unusual.
        Handle gracefully by logging the event.
        """
        new_status = validated_data.get('status', instance.status)

        if instance.status == Task.Status.DONE and new_status == Task.Status.TODO:
            # We get the user from the view context to log who did it
            user = self.context['request'].user
            logger.warning(
                f"UNUSUAL ACTIVITY: Task '{instance.title}' (ID: {instance.id}) moved from DONE to TODO by user {user.username}.")

        return super().update(instance, validated_data)