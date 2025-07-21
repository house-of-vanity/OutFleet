import logging
import time
from datetime import datetime, timedelta
from celery import group, shared_task
from celery.exceptions import Retry

logger = logging.getLogger(__name__)

def create_task_log(task_id, task_name, action, status='STARTED', server=None, user=None, message='', execution_time=None):
    """Helper function to create task execution log"""
    try:
        from .models import TaskExecutionLog
        TaskExecutionLog.objects.create(
            task_id=task_id,
            task_name=task_name,
            server=server,
            user=user,
            action=action,
            status=status,
            message=message,
            execution_time=execution_time
        )
    except Exception as e:
        # Don't fail tasks if logging fails - just log to console
        logger.error(f"Failed to create task log (task_id: {task_id}, action: {action}): {e}")
        # If table doesn't exist, just continue without logging to DB
        if "does not exist" in str(e):
            logger.info(f"TaskExecutionLog table not found - run migrations. Task: {task_name}, Action: {action}, Status: {status}")

@shared_task(name="cleanup_task_logs")
def cleanup_task_logs():
    """Clean up old task execution logs (older than 30 days)"""
    from .models import TaskExecutionLog
    
    try:
        cutoff_date = datetime.now() - timedelta(days=30)
        old_logs = TaskExecutionLog.objects.filter(created_at__lt=cutoff_date)
        count = old_logs.count()
        
        if count > 0:
            old_logs.delete()
            logger.info(f"Cleaned up {count} old task execution logs")
            return f"Cleaned up {count} old task execution logs"
        else:
            logger.info("No old task execution logs to clean up")
            return "No old task execution logs to clean up"
            
    except Exception as e:
        logger.error(f"Error cleaning up task logs: {e}")
        return f"Error cleaning up task logs: {e}"

class TaskFailedException(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(f"{self.message}")


@shared_task(name="sync_all_servers", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_all_users(self):
    from vpn.server_plugins import Server
    
    start_time = time.time()
    task_id = self.request.id
    
    create_task_log(task_id, "sync_all_servers", "Starting sync all servers", 'STARTED')
    
    try:
        servers = Server.objects.all()
        
        if not servers.exists():
            message = "No servers found for synchronization"
            logger.warning(message)
            create_task_log(task_id, "sync_all_servers", "No servers to sync", 'SUCCESS', message=message, execution_time=time.time() - start_time)
            return message
        
        # Filter out servers that might not exist anymore
        valid_servers = []
        for server in servers:
            try:
                # Test basic server access
                server.get_server_status()
                valid_servers.append(server)
            except Exception as e:
                logger.warning(f"Skipping server {server.name} (ID: {server.id}) due to connection issues: {e}")
                create_task_log(task_id, "sync_all_servers", f"Skipped server {server.name}", 'STARTED', server=server, message=f"Connection failed: {e}")
        
        # Log all servers that will be synced
        server_list = ", ".join([s.name for s in valid_servers])
        if valid_servers:
            create_task_log(task_id, "sync_all_servers", f"Found {len(valid_servers)} valid servers", 'STARTED', message=f"Servers: {server_list}")
            
            tasks = group(sync_users.s(server.id) for server in valid_servers)
            result = tasks.apply_async()
            
            success_message = f"Initiated sync for {len(valid_servers)} servers: {server_list}"
        else:
            success_message = "No valid servers found for synchronization"
        
        create_task_log(task_id, "sync_all_servers", "Sync initiated", 'SUCCESS', message=success_message, execution_time=time.time() - start_time)
        
        return success_message
        
    except Exception as e:
        error_message = f"Error initiating sync: {e}"
        logger.error(error_message)
        create_task_log(task_id, "sync_all_servers", "Sync failed", 'FAILURE', message=error_message, execution_time=time.time() - start_time)
        raise

@shared_task(name="sync_all_users_on_server", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_users(self, server_id):
    from vpn.server_plugins import Server
    
    start_time = time.time()
    task_id = self.request.id
    server = None
    
    try:
        try:
            server = Server.objects.get(id=server_id)
        except Server.DoesNotExist:
            error_message = f"Server with id {server_id} not found - may have been deleted"
            logger.error(error_message)
            create_task_log(task_id, "sync_all_users_on_server", "Server not found", 'FAILURE', message=error_message, execution_time=time.time() - start_time)
            return error_message  # Don't raise exception for deleted servers
        
        # Test server connectivity before proceeding
        try:
            server.get_server_status()
        except Exception as e:
            error_message = f"Server {server.name} is not accessible: {e}"
            logger.warning(error_message)
            create_task_log(task_id, "sync_all_users_on_server", "Server not accessible", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
            return error_message  # Don't retry for connectivity issues
        
        create_task_log(task_id, "sync_all_users_on_server", f"Starting user sync for server {server.name}", 'STARTED', server=server)
        logger.info(f"Starting user sync for server {server.name}")
        
        # Get all users for this server
        from .models import ACL
        acls = ACL.objects.filter(server=server).select_related('user')
        user_count = acls.count()
        user_list = ", ".join([acl.user.username for acl in acls[:10]])  # First 10 users
        if user_count > 10:
            user_list += f" and {user_count - 10} more"
        
        create_task_log(task_id, "sync_all_users_on_server", f"Found {user_count} users to sync", 'STARTED', server=server, message=f"Users: {user_list}")
        
        sync_result = server.sync_users()
        
        if sync_result:
            success_message = f"Successfully synced {user_count} users for server {server.name}"
            logger.info(success_message)
            create_task_log(task_id, "sync_all_users_on_server", "User sync completed", 'SUCCESS', server=server, message=success_message, execution_time=time.time() - start_time)
            return success_message
        else:
            error_message = f"Sync failed for server {server.name}"
            create_task_log(task_id, "sync_all_users_on_server", "User sync failed", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
            raise TaskFailedException(error_message)
    
    except TaskFailedException:
        # Don't retry TaskFailedException
        raise
    except Exception as e:
        error_message = f"Error syncing users for server {server.name if server else server_id}: {e}"
        logger.error(error_message)
        
        if self.request.retries < 3:
            retry_message = f"Retrying sync for server {server.name if server else server_id} (attempt {self.request.retries + 1})"
            logger.info(retry_message)
            create_task_log(task_id, "sync_all_users_on_server", "Retrying user sync", 'RETRY', server=server, message=retry_message)
            raise self.retry(countdown=60)
        
        create_task_log(task_id, "sync_all_users_on_server", "User sync failed after retries", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
        raise TaskFailedException(error_message)

@shared_task(name="sync_server_info", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def sync_server(self, id):
    from vpn.server_plugins import Server
    
    start_time = time.time()
    task_id = self.request.id
    server = None
    
    try:
        server = Server.objects.get(id=id)
        
        create_task_log(task_id, "sync_server_info", f"Starting server info sync for {server.name}", 'STARTED', server=server)
        logger.info(f"Starting server info sync for {server.name}")
        
        sync_result = server.sync()
        
        success_message = f"Successfully synced server info for {server.name}"
        result_details = f"Sync result: {sync_result}"
        logger.info(f"{success_message}. {result_details}")
        
        create_task_log(task_id, "sync_server_info", "Server info synced", 'SUCCESS', server=server, message=f"{success_message}. {result_details}", execution_time=time.time() - start_time)
        
        return {"status": sync_result, "server": server.name}
        
    except Server.DoesNotExist:
        error_message = f"Server with id {id} not found"
        logger.error(error_message)
        create_task_log(task_id, "sync_server_info", "Server not found", 'FAILURE', message=error_message, execution_time=time.time() - start_time)
        return {"error": error_message}
    except Exception as e:
        error_message = f"Error syncing server info for {server.name if server else id}: {e}"
        logger.error(error_message)
        
        if self.request.retries < 3:
            retry_message = f"Retrying server sync for {server.name if server else id} (attempt {self.request.retries + 1})"
            logger.info(retry_message)
            create_task_log(task_id, "sync_server_info", "Retrying server sync", 'RETRY', server=server, message=retry_message)
            raise self.retry(countdown=30)
        
        create_task_log(task_id, "sync_server_info", "Server sync failed after retries", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
        return {"error": error_message}

@shared_task(name="update_user_statistics", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def update_user_statistics(self):
    """Update cached user statistics from AccessLog data"""
    from .models import User, AccessLog, UserStatistics, ACLLink
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Count, Q
    from django.db import transaction
    
    start_time = time.time()
    task_id = self.request.id
    
    create_task_log(task_id, "update_user_statistics", "Starting statistics update", 'STARTED')
    
    try:
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        # Get all users with ACL links
        users_with_links = User.objects.filter(acl__isnull=False).distinct()
        total_users = users_with_links.count()
        
        create_task_log(task_id, "update_user_statistics", f"Found {total_users} users to process", 'STARTED')
        logger.info(f"Updating statistics for {total_users} users")
        
        updated_count = 0
        
        with transaction.atomic():
            for user in users_with_links:
                logger.debug(f"Processing user {user.username}")
                
                # Get all ACL links for this user
                acl_links = ACLLink.objects.filter(acl__user=user).select_related('acl__server')
                
                for link in acl_links:
                    server_name = link.acl.server.name
                    
                    # Calculate total connections for this specific link (all time)
                    total_connections = AccessLog.objects.filter(
                        user=user.username,
                        server=server_name,
                        acl_link_id=link.link,
                        action='Success'
                    ).count()
                    
                    # Calculate recent connections (last 30 days)
                    recent_connections = AccessLog.objects.filter(
                        user=user.username,
                        server=server_name,
                        acl_link_id=link.link,
                        action='Success',
                        timestamp__gte=thirty_days_ago
                    ).count()
                    
                    # Generate daily usage data for the last 30 days
                    daily_usage = []
                    max_daily = 0
                    
                    for i in range(30):
                        day_start = (now - timedelta(days=29-i)).replace(hour=0, minute=0, second=0, microsecond=0)
                        day_end = day_start + timedelta(days=1)
                        
                        day_connections = AccessLog.objects.filter(
                            user=user.username,
                            server=server_name,
                            acl_link_id=link.link,
                            action='Success',
                            timestamp__gte=day_start,
                            timestamp__lt=day_end
                        ).count()
                        
                        daily_usage.append(day_connections)
                        max_daily = max(max_daily, day_connections)
                    
                    # Update or create statistics for this link
                    stats, created = UserStatistics.objects.update_or_create(
                        user=user,
                        server_name=server_name,
                        acl_link_id=link.link,
                        defaults={
                            'total_connections': total_connections,
                            'recent_connections': recent_connections,
                            'daily_usage': daily_usage,
                            'max_daily': max_daily,
                        }
                    )
                    
                    action = "created" if created else "updated"
                    logger.debug(f"{action} stats for {user.username} on {server_name} (link: {link.link}): {total_connections} total, {recent_connections} recent")
                    
                    updated_count += 1
                
                logger.debug(f"Completed processing user {user.username}")
        
        success_message = f"Successfully updated statistics for {updated_count} user-server-link combinations"
        logger.info(success_message)
        
        create_task_log(
            task_id, 
            "update_user_statistics", 
            "Statistics update completed", 
            'SUCCESS', 
            message=success_message, 
            execution_time=time.time() - start_time
        )
        
        return success_message
        
    except Exception as e:
        error_message = f"Error updating user statistics: {e}"
        logger.error(error_message, exc_info=True)
        
        if self.request.retries < 3:
            retry_message = f"Retrying statistics update (attempt {self.request.retries + 1})"
            logger.info(retry_message)
            create_task_log(task_id, "update_user_statistics", "Retrying statistics update", 'RETRY', message=retry_message)
            raise self.retry(countdown=60)
        
        create_task_log(
            task_id, 
            "update_user_statistics", 
            "Statistics update failed after retries", 
            'FAILURE', 
            message=error_message, 
            execution_time=time.time() - start_time
        )
        raise

@shared_task(name="sync_user_on_server", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 30})
def sync_user(self, user_id, server_id):
    from .models import User, ACL
    from vpn.server_plugins import Server
    
    start_time = time.time()
    task_id = self.request.id
    errors = {}
    result = {}
    user = None
    server = None
    
    try:
        user = User.objects.get(id=user_id)
        server = Server.objects.get(id=server_id)
        
        create_task_log(task_id, "sync_user_on_server", f"Starting user sync for {user.username} on {server.name}", 'STARTED', server=server, user=user)
        logger.info(f"Syncing user {user.username} on server {server.name}")
        
        # Check if ACL exists
        acl_exists = ACL.objects.filter(user=user, server=server).exists()
        
        if acl_exists:
            # User should exist on server
            action_message = f"Adding/updating user {user.username} on server {server.name}"
            create_task_log(task_id, "sync_user_on_server", action_message, 'STARTED', server=server, user=user)
            
            result[server.name] = server.add_user(user)
            
            success_message = f"Successfully added/updated user {user.username} on server {server.name}"
            logger.info(success_message)
            create_task_log(task_id, "sync_user_on_server", "User added/updated", 'SUCCESS', server=server, user=user, message=f"{success_message}. Result: {result[server.name]}", execution_time=time.time() - start_time)
        else:
            # User should be removed from server
            action_message = f"Removing user {user.username} from server {server.name}"
            create_task_log(task_id, "sync_user_on_server", action_message, 'STARTED', server=server, user=user)
            
            result[server.name] = server.delete_user(user)
            
            success_message = f"Successfully removed user {user.username} from server {server.name}"
            logger.info(success_message)
            create_task_log(task_id, "sync_user_on_server", "User removed", 'SUCCESS', server=server, user=user, message=f"{success_message}. Result: {result[server.name]}", execution_time=time.time() - start_time)
            
    except User.DoesNotExist:
        error_msg = f"User with id {user_id} not found"
        logger.error(error_msg)
        errors["user"] = error_msg
        create_task_log(task_id, "sync_user_on_server", "User not found", 'FAILURE', message=error_msg, execution_time=time.time() - start_time)
    except Server.DoesNotExist:
        error_msg = f"Server with id {server_id} not found"
        logger.error(error_msg)
        errors["server"] = error_msg
        create_task_log(task_id, "sync_user_on_server", "Server not found", 'FAILURE', message=error_msg, execution_time=time.time() - start_time)
    except Exception as e:
        error_msg = f"Error syncing user {user.username if user else user_id} on server {server.name if server else server_id}: {e}"
        logger.error(error_msg)
        errors[f"server_{server_id}"] = error_msg
        
        # Retry on failure unless it's a permanent error
        if self.request.retries < 5:
            retry_message = f"Retrying user sync for user {user.username if user else user_id} on server {server.name if server else server_id} (attempt {self.request.retries + 1})"
            logger.info(retry_message)
            create_task_log(task_id, "sync_user_on_server", "Retrying user sync", 'RETRY', server=server, user=user, message=retry_message)
            raise self.retry(countdown=30)
        
        create_task_log(task_id, "sync_user_on_server", "User sync failed after retries", 'FAILURE', server=server, user=user, message=error_msg, execution_time=time.time() - start_time)
    
    if errors:
        raise TaskFailedException(message=f"Errors during task: {errors}")
    
    return result