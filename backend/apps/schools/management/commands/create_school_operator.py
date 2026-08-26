"""
Create a school and its first operator account in one step.

Production usage (no demo data, no auto-created admin)::

    docker compose run --rm backend python manage.py create_school_operator

The command prompts for:
  * school name
  * external (stable) code
  * operator username
  * initial password (input is hidden)

It is idempotent on the external code: if the school already exists the
command can still add an operator to it via ``--school-code``.
"""
from __future__ import annotations

import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.schools.models import SchoolTenant

User = get_user_model()


class Command(BaseCommand):
    help = "Create a school (if needed) and an operator account for it."

    def add_arguments(self, parser):
        parser.add_argument("--school-name", help="نام مدرسه")
        parser.add_argument("--school-code", help="کد خارجی پایدار مدرسه")
        parser.add_argument("--username", help="نام کاربری مسئول")
        parser.add_argument(
            "--password",
            help="رمز اولیه (در صورت عدم ورود، به‌صورت مخفی پرسیده می‌شود).",
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help="همه‌ی مقادیر باید از آرگومان‌ها بیایند و چیزی پرسیده نشود.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        non_interactive = options["non_interactive"]

        school_name = options["school_name"] or (
            None if non_interactive else input("نام مدرسه: ").strip()
        )
        school_code = options["school_code"] or (
            None if non_interactive else input("کد خارجی پایدار مدرسه (مثلاً SCHOOL-01): ").strip()
        )
        username = options["username"] or (
            None if non_interactive else input("نام کاربری مسئول: ").strip()
        )
        password = options["password"]
        if not password and not non_interactive:
            password = getpass.getpass("رمز اولیه (حداقل ۱۰ کاراکتر): ")
            confirm = getpass.getpass("تکرار رمز: ")
            if password != confirm:
                self.stderr.write(self.style.ERROR("رمزها یکسان نیستند."))
                raise SystemExit(1)

        missing = [
            label
            for label, val in [
                ("school name", school_name),
                ("school code", school_code),
                ("username", username),
                ("password", password),
            ]
            if not val
        ]
        if missing:
            self.stderr.write(self.style.ERROR(f"مقادیر الزامی وارد نشده‌اند: {', '.join(missing)}"))
            raise SystemExit(1)

        if len(password) < 10:
            self.stderr.write(self.style.ERROR("رمز باید حداقل ۱۰ کاراکتر باشد."))
            raise SystemExit(1)

        school, created_school = SchoolTenant.objects.get_or_create(
            external_code=school_code, defaults={"name": school_name}
        )
        if not created_school and school.name != school_name:
            school.name = school_name
            school.save(update_fields=["name"])

        if User.objects.filter(username=username).exists():
            self.stderr.write(
                self.style.ERROR(f"کاربری با نام «{username}» از قبل وجود دارد.")
            )
            raise SystemExit(1)

        user = User.objects.create_user(
            username=username,
            password=password,
            role=User.Role.OPERATOR,
            school_tenant=school,
            is_active=True,
        )

        if created_school:
            self.stdout.write(self.style.SUCCESS(f"مدرسه «{school.name}» ساخته شد."))
        self.stdout.write(
            self.style.SUCCESS(
                f"حساب مسئول «{user.username}» برای مدرسه «{school.name}» ساخته شد."
            )
        )
