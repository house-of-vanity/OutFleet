from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = '''
    Clean up AccessLog entries efficiently using direct SQL.
    
    Examples:
      # Delete logs without acl_link_id older than 30 days (recommended)
      python manage.py cleanup_logs --keep-days=30
      
      # Keep only last 5000 logs without acl_link_id
      python manage.py cleanup_logs --keep-count=5000
      
      # Delete ALL logs older than 7 days (including with acl_link_id) 
      python manage.py cleanup_logs --keep-days=7 --target=all
      
      # Preview what would be deleted
      python manage.py cleanup_logs --keep-days=30 --dry-run
      
      # Force delete without confirmation
      python manage.py cleanup_logs --keep-days=30 --force
    '''

    def add_arguments(self, parser):
        # Primary options (mutually exclusive)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--keep-days',
            type=int,
            help='Keep logs newer than this many days (delete older)'
        )
        group.add_argument(
            '--keep-count', 
            type=int,
            help='Keep this many most recent logs (delete the rest)'
        )
        
        parser.add_argument(
            '--target',
            choices=['no-links', 'all'],
            default='no-links',
            help='Target: "no-links" = only logs without acl_link_id (default), "all" = all logs'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        
        parser.add_argument(
            '--force',
            action='store_true', 
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        keep_days = options.get('keep_days')
        keep_count = options.get('keep_count')
        target = options['target']
        dry_run = options['dry_run']
        force = options['force']
        
        # Build SQL conditions
        if target == 'no-links':
            base_condition = "(acl_link_id IS NULL OR acl_link_id = '')"
            target_desc = "logs without acl_link_id"
        else:
            base_condition = "1=1"
            target_desc = "all logs"
        
        # Get current statistics
        with connection.cursor() as cursor:
            # Total records
            cursor.execute("SELECT COUNT(*) FROM vpn_accesslog")
            total_records = cursor.fetchone()[0]
            
            # Target records count
            cursor.execute(f"SELECT COUNT(*) FROM vpn_accesslog WHERE {base_condition}")
            target_records = cursor.fetchone()[0]
            
            # Records to delete
            if keep_days:
                cutoff_date = timezone.now() - timedelta(days=keep_days)
                cursor.execute(f"""
                    SELECT COUNT(*) FROM vpn_accesslog 
                    WHERE {base_condition} AND timestamp < %s
                """, [cutoff_date])
                to_delete = cursor.fetchone()[0]
                strategy = f"older than {keep_days} days"
            else:  # keep_count
                to_delete = max(0, target_records - keep_count)
                strategy = f"keeping only {keep_count} most recent"
        
        # Print statistics
        self.stdout.write("🗑️  AccessLog Cleanup" + (" (DRY RUN)" if dry_run else ""))
        self.stdout.write(f"   Target: {target_desc}")
        self.stdout.write(f"   Strategy: {strategy}")
        self.stdout.write("")
        self.stdout.write("📊 Statistics:")
        self.stdout.write(f"   Total AccessLog records: {total_records:,}")
        self.stdout.write(f"   Target records: {target_records:,}")
        self.stdout.write(f"   Records to delete: {to_delete:,}")
        self.stdout.write(f"   Records to keep: {target_records - to_delete:,}")
        
        if total_records > 0:
            delete_percent = (to_delete / total_records) * 100
            self.stdout.write(f"   Deletion percentage: {delete_percent:.1f}%")
        
        if to_delete == 0:
            self.stdout.write(self.style.SUCCESS("✅ No records to delete."))
            return
        
        # Show SQL that will be executed
        if dry_run or not force:
            self.stdout.write("")
            self.stdout.write("📝 SQL to execute:")
            if keep_days:
                sql_preview = f"""
                DELETE FROM vpn_accesslog 
                WHERE {base_condition} AND timestamp < '{cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}'
                """
            else:  # keep_count
                sql_preview = f"""
                DELETE FROM vpn_accesslog 
                WHERE {base_condition} 
                  AND id NOT IN (
                    SELECT id FROM (
                      SELECT id FROM vpn_accesslog 
                      WHERE {base_condition}
                      ORDER BY timestamp DESC 
                      LIMIT {keep_count}
                    ) AS recent_logs
                  )
                """
            self.stdout.write(sql_preview.strip())
        
        if dry_run:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"🔍 DRY RUN: Would delete {to_delete:,} records"))
            return
        
        # Confirm deletion
        if not force:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"⚠️  About to DELETE {to_delete:,} records!"))
            confirm = input("Type 'DELETE' to confirm: ")
            if confirm != 'DELETE':
                self.stdout.write("❌ Cancelled.")
                return
        
        # Execute deletion
        self.stdout.write("")
        self.stdout.write(f"🗑️  Deleting {to_delete:,} records...")
        
        with connection.cursor() as cursor:
            if keep_days:
                # Simple time-based deletion
                cursor.execute(f"""
                    DELETE FROM vpn_accesslog 
                    WHERE {base_condition} AND timestamp < %s
                """, [cutoff_date])
            else:
                # Keep count deletion (more complex)
                cursor.execute(f"""
                    DELETE FROM vpn_accesslog 
                    WHERE {base_condition} 
                      AND id NOT IN (
                        SELECT id FROM (
                          SELECT id FROM vpn_accesslog 
                          WHERE {base_condition}
                          ORDER BY timestamp DESC 
                          LIMIT %s
                        ) AS recent_logs
                      )
                """, [keep_count])
            
            deleted_count = cursor.rowcount
        
        # Final statistics
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM vpn_accesslog")
            final_total = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM vpn_accesslog WHERE {base_condition}")
            final_target = cursor.fetchone()[0]
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✅ Cleanup completed!"))
        self.stdout.write(f"   Deleted: {deleted_count:,} records")
        self.stdout.write(f"   Remaining total: {final_total:,}")
        
        if target == 'no-links':
            self.stdout.write(f"   Remaining without links: {final_target:,}")
        
        # Calculate space saved (rough estimate)
        if deleted_count > 0:
            # Rough estimate: ~200 bytes per AccessLog record
            space_saved_mb = (deleted_count * 200) / (1024 * 1024)
            if space_saved_mb > 1024:
                space_saved_gb = space_saved_mb / 1024
                self.stdout.write(f"   Estimated space saved: ~{space_saved_gb:.1f} GB")
            else:
                self.stdout.write(f"   Estimated space saved: ~{space_saved_mb:.1f} MB")
