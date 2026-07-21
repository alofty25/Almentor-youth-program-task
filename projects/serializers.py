from rest_framework import serializers
from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        # We don't expose 'owner' or 'deleted_at' to the user
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        """
        Business Rule: Duplicate project names should be rejected.
        We ensure the name is unique PER USER.
        """
        request = self.context.get('request')
        user = request.user

        # Check if the user already has a project with this name
        query = Project.objects.filter(owner=user, name=value)

        # If we are updating an existing project, exclude it from the check
        if self.instance:
            query = query.exclude(pk=self.instance.pk)

        if query.exists():
            raise serializers.ValidationError("You already have a project with this name.")

        return value