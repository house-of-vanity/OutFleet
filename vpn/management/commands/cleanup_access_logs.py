from django.core.management.base import BaseCommand
from django.db import connection, transaction
from datetime import datetime, timedelta
from vpn.models import AccessLog


class Command(BaseCommand):
    help = 'Clean up old AccessLog entries without acl_link_id'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete logs older than this many days (default: 30)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10000,
            help='Number of records to delete in each batch (default: 10000)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--keep-recent',
            type=int,
            default=1000,
            help='Keep this many recent logs even if they have no link (default: 1000)'
        )

    def handle(self, *args, **options):
        days = options['days']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        keep_recent = options['keep_recent']
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        self.stdout.write(f"🔍 Analyzing AccessLog cleanup...")
        self.stdout.write(f"   - Delete logs without acl_link_id older than {days} days")
        self.stdout.write(f"   - Keep {keep_recent} most recent logs without links")
        self.stdout.write(f"   - Batch size: {batch_size}")
        self.stdout.write(f"   - Dry run: {dry_run}")
        
        # Count total records to be deleted
        with connection.cursor() as cursor:
            # Count logs without acl_link_id
            cursor.execute("""
                SELECT COUNT(*) FROM vpn_accesslog 
                WHERE (acl_link_id IS NULL OR acl_link_id = '')
            """)
            total_without_link = cursor.fetchone()[0]
            
            # Count logs to be deleted (older than cutoff, excluding recent ones to keep)
            cursor.execute("""
                SELECT COUNT(*) FROM vpn_accesslog 
                WHERE (acl_link_id IS NULL OR acl_link_id = '') 
                  AND timestamp < %s
                  AND id NOT IN (
                    SELECT id FROM (
                      SELECT id FROM vpn_accesslog 
                      WHERE acl_link_id IS NULL OR acl_link_id = ''
                      ORDER BY timestamp DESC 
                      LIMIT %s
                    ) AS recent_logs
                  )
            """, [cutoff_date, keep_recent])
            total_to_delete = cursor.fetchone()[0]
            
            # Count total records
            cursor.execute("SELECT COUNT(*) FROM vpn_accesslog")
            total_records = cursor.fetchone()[0]
        
        self.stdout.write(f"📊 Statistics:")
        self.stdout.write(f"   - Total AccessLog records: {total_records:,}")
        self.stdout.write(f"   - Records without acl_link_id: {total_without_link:,}")
        self.stdout.write(f"   - Records to be deleted: {total_to_delete:,}")
        self.stdout.write(f"   - Records to be kept (recent): {keep_recent:,}")
        
        if total_to_delete == 0:
            self.stdout.write(self.style.SUCCESS("✅ No records to delete."))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"🔍 DRY RUN: Would delete {total_to_delete:,} records"))
            return
        
        # Confirm deletion
        if not options.get('verbosity', 1) == 0:  # Only ask if not --verbosity=0
            confirm = input(f"❓ Delete {total_to_delete:,} records? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write("❌ Cancelled.")
                return
        
        self.stdout.write(f"🗑️  Starting deletion of {total_to_delete:,} records...")
        
        deleted_total = 0
        batch_num = 0
        
        while True:
            batch_num += 1
            
            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Delete batch
                    cursor.execute("""
                        DELETE FROM vpn_accesslog 
                        WHERE (acl_link_id IS NULL OR acl_link_id = '') 
                          AND timestamp < %s
                          AND id NOT IN (
                            SELECT id FROM (
                              SELECT id FROM vpn_accesslog 
                              WHERE acl_link_id IS NULL OR acl_link_id = ''
                              ORDER BY timestamp DESC 
                              LIMIT %s
                            ) AS recent_logs
                          )
                        LIMIT %s
                    """, [cutoff_date, keep_recent, batch_size])
                    
                    deleted_in_batch = cursor.rowcount
            
            if deleted_in_batch == 0:
                break
            
            deleted_total += deleted_in_batch
            progress = (deleted_total / total_to_delete) * 100
            
            self.stdout.write(
                f"   Batch {batch_num}: Deleted {deleted_in_batch:,} records "
                f"(Total: {deleted_total:,}/{total_to_delete:,}, {progress:.1f}%)"
            )
            
            if deleted_in_batch < batch_size:
                break
        
        self.stdout.write(self.style.SUCCESS(f"✅ Cleanup completed!"))
        self.stdout.write(f"   - Deleted {deleted_total:,} old AccessLog records")
        self.stdout.write(f"   - Kept {keep_recent:,} recent records without links")
        
        # Show final statistics
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM vpn_accesslog")
            final_total = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM vpn_accesslog 
                WHERE acl_link_id IS NULL OR acl_link_id = ''
            """)
            final_without_link = cursor.fetchone()[0]
        
        self.stdout.write(f"📊 Final statistics:")
        self.stdout.write(f"   - Total AccessLog records: {final_total:,}")
        self.stdout.write(f"   - Records without acl_link_id: {final_without_link:,}")
