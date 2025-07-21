from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from vpn.models import AccessLog


class Command(BaseCommand):
    help = 'Simple cleanup of AccessLog entries without acl_link_id using Django ORM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete logs older than this many days (default: 30)'
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Count records to be deleted
        old_logs = AccessLog.objects.filter(
            acl_link_id__isnull=True,
            timestamp__lt=cutoff_date
        )
        
        # Also include empty string acl_link_id
        empty_logs = AccessLog.objects.filter(
            acl_link_id='',
            timestamp__lt=cutoff_date
        )
        
        total_old = old_logs.count()
        total_empty = empty_logs.count()
        total_to_delete = total_old + total_empty
        
        self.stdout.write(f"Found {total_to_delete:,} old logs without acl_link_id to delete")
        
        if total_to_delete == 0:
            self.stdout.write("Nothing to delete.")
            return
        
        # Delete in batches to avoid memory issues
        self.stdout.write("Deleting old logs...")
        
        deleted_count = 0
        deleted_count += old_logs._raw_delete(old_logs.db)
        deleted_count += empty_logs._raw_delete(empty_logs.db)
        
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count:,} old AccessLog records"))
