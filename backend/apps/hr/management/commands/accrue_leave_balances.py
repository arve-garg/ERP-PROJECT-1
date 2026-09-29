"""Accrue monthly leave balances for active employees."""

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.hr.services import accrue_monthly_leave_balances


class Command(BaseCommand):
    help = "Accrue one month's leave allowance for eligible employees. Reruns are idempotent."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--year", type=int, default=timezone.localdate().year)
        parser.add_argument("--month", type=int, default=timezone.localdate().month)

    def handle(self, *args: Any, **options: Any) -> None:
        year = options["year"]
        month = options["month"]
        if month < 1 or month > 12:
            raise CommandError("--month must be between 1 and 12.")
        count = accrue_monthly_leave_balances(year, month)
        self.stdout.write(
            self.style.SUCCESS(f"Applied {count} leave accrual(s) for {year}-{month:02d}.")
        )
