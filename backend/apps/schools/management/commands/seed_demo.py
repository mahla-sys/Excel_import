from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.schools.models import SchoolTenant

User = get_user_model()

DEMO_SCHOOLS = [
    ("دبستان پسرانه‌ی فردوسی", "SCHOOL-01", "op01"),
    ("دبستان دخترانه‌ی پروین", "SCHOOL-02", "op02"),
    ("متوسطه‌ی اول پسرانه‌ی ابن‌سینا", "SCHOOL-03", "op03"),
    ("متوسطه‌ی اول دخترانه‌ی فرزانگان", "SCHOOL-04", "op04"),
    ("متوسطه‌ی دوم پسرانه‌ی شهید بهشتی", "SCHOOL-05", "op05"),
    ("متوسطه‌ی دوم دخترانه‌ی آزادگان", "SCHOOL-06", "op06"),
    ("هنرستان فنی و حرفه‌ای سروش", "SCHOOL-07", "op07"),
]


class Command(BaseCommand):
    help = "Seed 7 demo schools and one operator account per school."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="Operator@12345",
            help="Default password for seeded operators (for local dev only).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        for name, code, op_username in DEMO_SCHOOLS:
            school, created = SchoolTenant.objects.get_or_create(
                external_code=code, defaults={"name": name}
            )
            if not created and school.name != name:
                school.name = name
                school.save(update_fields=["name"])

            user, created_user = User.objects.get_or_create(
                username=op_username,
                defaults={
                    "role": User.Role.OPERATOR,
                    "school_tenant": school,
                    "is_active": True,
                },
            )
            user.role = User.Role.OPERATOR
            user.school_tenant = school
            user.is_active = True
            user.set_password(password)
            user.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'Created' if created_user else 'Updated'} operator "
                    f"'{op_username}' for school '{school.name}'."
                )
            )

        self.stdout.write(
            self.style.WARNING(
                f"All operator passwords are: {password}  (dev only, change in production)."
            )
        )
