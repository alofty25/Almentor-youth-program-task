"""
core/management/commands/seed.py

Production-grade database seed command for the Almentor Task Management API.

Usage:
    python manage.py seed          # Seed database with realistic mock data
    python manage.py seed --clear  # Wipe existing seeded data before populating
"""

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from faker import Faker

from projects.models import Project
from tasks.models import Task

User = get_user_model()


class Command(BaseCommand):
    help = "Populates the database with realistic production-like data for testing and development."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Safely hard-delete existing seeded data before seeding.',
        )
        parser.add_argument(
            '--users',
            type=int,
            default=6,
            help='Number of demo users to create (default: 6).',
        )
        parser.add_argument(
            '--projects',
            type=int,
            default=25,
            help='Total number of projects to generate (default: 25).',
        )
        parser.add_argument(
            '--tasks',
            type=int,
            default=120,
            help='Total number of tasks to generate (default: 120).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        fake = Faker()
        Faker.seed(42)  # Deterministic seed for reproducible testing
        random.seed(42)

        should_clear = options['clear']
        num_users_target = options['users']
        num_projects_target = options['projects']
        num_tasks_target = options['tasks']

        self.stdout.write(self.style.MIGRATE_HEADING("=== Starting Database Seeding Process ==="))

        # -------------------------------------------------------------------
        # 1. Idempotency & Clean-up
        # -------------------------------------------------------------------
        if should_clear:
            self.stdout.write(self.style.WARNING("Clearing existing project and task data..."))
            # Hard delete tasks and projects to ensure a clean slate
            Task.all_objects.all().delete()
            Project.all_objects.all().delete()
            # Remove non-superuser demo users
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.SUCCESS("[OK] Existing data cleared successfully."))

        # -------------------------------------------------------------------
        # 2. User Generation
        # -------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("Seeding Users..."))

        demo_users_data = [
            {"username": "demo_admin", "first_name": "System", "last_name": "Admin", "is_staff": True, "is_superuser": True},
            {"username": "sarah_pm", "first_name": "Sarah", "last_name": "Connor", "is_staff": False, "is_superuser": False},
            {"username": "alex_dev", "first_name": "Alex", "last_name": "Rivera", "is_staff": False, "is_superuser": False},
            {"username": "maya_ux", "first_name": "Maya", "last_name": "Lin", "is_staff": False, "is_superuser": False},
            {"username": "david_qa", "first_name": "David", "last_name": "Miller", "is_staff": False, "is_superuser": False},
            {"username": "sam_devops", "first_name": "Sam", "last_name": "Vance", "is_staff": False, "is_superuser": False},
        ]

        users = []
        default_password = "Password123!"

        for user_info in demo_users_data[:num_users_target]:
            user, created = User.objects.get_or_create(
                username=user_info["username"],
                defaults={
                    "email": f"{user_info['username']}@example.com",
                    "first_name": user_info["first_name"],
                    "last_name": user_info["last_name"],
                    "is_staff": user_info["is_staff"],
                    "is_superuser": user_info["is_superuser"],
                }
            )
            if created:
                user.set_password(default_password)
                user.save()
            users.append(user)

        # Generate additional users if requested count is higher than predefined list
        while len(users) < num_users_target:
            fname = fake.first_name()
            lname = fake.last_name()
            uname = f"{fname.lower()}_{lname.lower()}_{random.randint(10,99)}"
            user, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    "email": f"{uname}@example.com",
                    "first_name": fname,
                    "last_name": lname,
                }
            )
            if created:
                user.set_password(default_password)
                user.save()
            users.append(user)

        self.stdout.write(self.style.SUCCESS(f"[OK] {len(users)} users ready (Default Password: '{default_password}')."))

        # -------------------------------------------------------------------
        # 3. Project Generation
        # -------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("Seeding Projects..."))

        project_domains = [
            "NextGen Mobile Banking App",
            "Cloud Infrastructure Migration",
            "AI Customer Support Chatbot",
            "Real-time Analytics Dashboard",
            "GraphQL API Gateway",
            "Design System Component Library",
            "OAuth2 & Security Hardening",
            "Payment Gateway Integration",
            "CI/CD Pipeline Automation",
            "Automated QA Test Suite",
            "E-Commerce Platform Replatforming",
            "Microservices Event Bus",
            "Customer Feedback Portal",
            "Inventory Tracking System",
            "Telemetry & Metrics Collector",
            "Search Engine Optimization Engine",
            "GDPR Data Compliance Module",
            "SaaS Subscription Billing",
            "Notification Push Service",
            "DevOps Monitoring Dashboard",
            "IoT Device Management System",
            "Internal Knowledge Base Wiki",
            "Log Aggregation Pipeline",
            "Feature Flag Management Service",
            "Multi-Tenant Auth Portal",
        ]

        created_projects = []
        project_count = 0

        for name in project_domains[:num_projects_target]:
            owner = random.choice(users)

            # Ensure unique name per user constraint
            counter = 1
            original_name = name
            while Project.all_objects.filter(owner=owner, name=name).exists():
                name = f"{original_name} v{counter}"
                counter += 1

            # Varied descriptions (including edge cases: None and long descriptions)
            desc_type = random.choice(["standard", "short", "long", "none"])
            if desc_type == "standard":
                description = fake.paragraph(nb_sentences=4)
            elif desc_type == "short":
                description = fake.sentence()
            elif desc_type == "long":
                description = "\n\n".join(fake.paragraphs(nb=5))
            else:
                description = None

            project = Project.objects.create(
                owner=owner,
                name=name,
                description=description
            )
            created_projects.append(project)
            project_count += 1

        # Generate additional random projects if target > domains list length
        while len(created_projects) < num_projects_target:
            owner = random.choice(users)
            p_name = fake.bs().title()
            if not Project.all_objects.filter(owner=owner, name=p_name).exists():
                project = Project.objects.create(
                    owner=owner,
                    name=p_name,
                    description=fake.paragraph()
                )
                created_projects.append(project)
                project_count += 1

        # Edge case: Soft-delete ~10% of projects to test soft-delete functionality
        soft_deleted_projects_count = 0
        projects_to_soft_delete = random.sample(created_projects, k=max(1, len(created_projects) // 10))
        for p in projects_to_soft_delete:
            p.delete()  # Triggers soft delete
            soft_deleted_projects_count += 1

        active_projects = [p for p in created_projects if p not in projects_to_soft_delete]

        self.stdout.write(self.style.SUCCESS(
            f"[OK] {project_count} projects created ({len(active_projects)} active, {soft_deleted_projects_count} soft-deleted)."
        ))

        # -------------------------------------------------------------------
        # 4. Task Generation
        # -------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("Seeding Tasks..."))

        task_templates = [
            ("Configure Redis Cache Layer", "Implement Redis caching for hot API endpoints to reduce DB load."),
            ("Optimize PostgreSQL Indexes", "Add composite indexes on foreign keys and filter fields."),
            ("Design High-Fidelity Figma Prototypes", "Create mobile & desktop responsive mockups for the checkout flow."),
            ("Set up Sentry Error Tracking", "Integrate Sentry SDK across backend DRF and front-end client."),
            ("Audit OWASP Top 10 Vulnerabilities", "Run automated security scanner and fix XSS and SQLi risks."),
            ("Migrate Legacy Endpoints to ViewSets", "Refactor function-based views to DRF ModelViewSets."),
            ("Implement JWT Refresh Rotation", "Configure token blacklist and refresh token rotation logic."),
            ("Write Integration Tests for Auth Flow", "Cover login, token refresh, and logout scenarios."),
            ("Configure Docker Multi-stage Builds", "Optimize container image size down to under 150MB."),
            ("Set up Prometheus & Grafana Metrics", "Export HTTP request latency and error rate metrics."),
            ("Implement Rate Limiting Middleware", "Enforce 100 req/min per IP to prevent brute-force attacks."),
            ("Refactor Soft-Delete Base Model", "Ensure ActiveManager filters out deleted records cleanly."),
            ("Write OpenAPI/Swagger Specifications", "Document all REST endpoints with DRF Spectacular."),
            ("Add Full-Text Search Filtering", "Implement icontains search across title and description."),
            ("Implement Dynamic Pagination", "Add page size limit query param support to task list endpoint."),
            ("Fix Memory Leak in WebSocket Handler", "Resolve unclosed socket connections under heavy load."),
            ("Conduct Load Testing with Locust", "Simulate 500 concurrent users performing GET/POST actions."),
            ("Configure Automated Database Backups", "Schedule nightly pg_dump snapshots to AWS S3."),
            ("Update Dependency Lockfile via UV", "Upgrade out-of-date security patches cleanly."),
            ("Add Unit Tests for Serializer Validation", "Verify edge case field validations and error responses."),
            ("Design Dark Mode Theme System", "Define CSS variables and custom palette for dark mode UI."),
            ("Fix Cross-User Data Leak Vulnerability", "Ensure querysets strictly filter by request.user."),
            ("Implement Webhook Event Dispatcher", "Publish task status change events to external webhooks."),
            ("Optimize DB Query N+1 Bottleneck", "Add select_related('project') to task list serializer query."),
            ("Setup GitHub Actions CI Workflow", "Automate test suite execution on push and pull requests."),
        ]

        today = timezone.now().date()
        statuses = [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE]
        priorities = [Task.Priority.LOW, Task.Priority.MEDIUM, Task.Priority.HIGH]

        created_tasks = []

        # Create tasks across both active and soft-deleted projects
        for i in range(num_tasks_target):
            # Select project (mostly active projects, occasionally soft-deleted)
            project = random.choice(created_projects)

            template = random.choice(task_templates)
            title = f"{template[0]} #{i+1}"

            # Variety in description
            desc_choice = random.choice(["template", "faker", "blank"])
            if desc_choice == "template":
                description = f"{template[1]} {fake.sentence()}"
            elif desc_choice == "faker":
                description = fake.paragraph()
            else:
                description = None

            status = random.choice(statuses)
            priority = random.choice(priorities)

            # Varied due dates (Past/Overdue, Today, Near Future, Far Future, None)
            date_scenario = random.choice(["past", "today", "near_future", "far_future", "none"])
            if date_scenario == "past":
                due_date = today - timedelta(days=random.randint(1, 30))
            elif date_scenario == "today":
                due_date = today
            elif date_scenario == "near_future":
                due_date = today + timedelta(days=random.randint(1, 14))
            elif date_scenario == "far_future":
                due_date = today + timedelta(days=random.randint(30, 90))
            else:
                due_date = None

            # Create task bypassing model validator to allow realistic historical past tasks
            task = Task(
                project=project,
                title=title,
                description=description,
                status=status,
                priority=priority,
                due_date=due_date
            )
            task.save()
            created_tasks.append(task)

        # Edge Case: Soft-delete ~10% of tasks directly
        soft_deleted_tasks_count = 0
        tasks_to_soft_delete = random.sample(created_tasks, k=max(1, len(created_tasks) // 10))
        for t in tasks_to_soft_delete:
            t.delete()
            soft_deleted_tasks_count += 1

        active_tasks_count = Task.objects.count()

        self.stdout.write(self.style.SUCCESS(
            f"[OK] {len(created_tasks)} tasks created ({active_tasks_count} active in DB, {soft_deleted_tasks_count} soft-deleted)."
        ))

        # -------------------------------------------------------------------
        # 5. Summary & Usage Guide
        # -------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Seeding Summary ==="))
        self.stdout.write(f"  * Users Created    : {len(users)}")
        self.stdout.write(f"  * Projects Created : {len(created_projects)} ({len(active_projects)} active, {soft_deleted_projects_count} soft-deleted)")
        self.stdout.write(f"  * Tasks Created    : {len(created_tasks)} ({active_tasks_count} active, {soft_deleted_tasks_count} soft-deleted)")
        self.stdout.write(self.style.SUCCESS("\n[OK] Database successfully seeded with production-like data!"))

        self.stdout.write(self.style.HTTP_INFO("\nDemo User Credentials:"))
        for u in users[:6]:
            role = "Admin" if u.is_superuser else "User"
            self.stdout.write(f"  Username: {u.username:<15} | Password: {default_password} | Role: {role}")

        self.stdout.write(self.style.NOTICE("\nTest JWT Login via API:"))
        self.stdout.write('  POST /api/token/  body: {"username": "sarah_pm", "password": "Password123!"}\n')
