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


@shared_task(name="sync_xray_inbounds", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def sync_xray_inbounds(self, server_id):
    """Stage 1: Sync inbounds for Xray server."""
    from vpn.server_plugins import Server
    from vpn.server_plugins.xray_v2 import XrayServerV2
    
    start_time = time.time()
    task_id = self.request.id
    server = None
    
    try:
        server = Server.objects.get(id=server_id)
        
        if not isinstance(server.get_real_instance(), XrayServerV2):
            error_message = f"Server {server.name} is not an Xray server"
            logger.error(error_message)
            create_task_log(task_id, "sync_xray_inbounds", "Wrong server type", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
            return {"error": error_message}
        
        create_task_log(task_id, "sync_xray_inbounds", f"Starting inbound sync for {server.name}", 'STARTED', server=server)
        logger.info(f"Starting inbound sync for Xray server {server.name}")
        
        real_server = server.get_real_instance()
        inbound_result = real_server.sync_inbounds()
        
        success_message = f"Successfully synced inbounds for {server.name}"
        logger.info(f"{success_message}. Result: {inbound_result}")
        
        create_task_log(task_id, "sync_xray_inbounds", "Inbound sync completed", 'SUCCESS', server=server, message=f"{success_message}. Result: {inbound_result}", execution_time=time.time() - start_time)
        
        return inbound_result
        
    except Server.DoesNotExist:
        error_message = f"Server with id {server_id} not found"
        logger.error(error_message)
        create_task_log(task_id, "sync_xray_inbounds", "Server not found", 'FAILURE', message=error_message, execution_time=time.time() - start_time)
        return {"error": error_message}
    except Exception as e:
        error_message = f"Error syncing inbounds for {server.name if server else server_id}: {e}"
        logger.error(error_message)
        
        if self.request.retries < 3:
            retry_message = f"Retrying inbound sync for {server.name if server else server_id} (attempt {self.request.retries + 1})"
            logger.info(retry_message)
            create_task_log(task_id, "sync_xray_inbounds", "Retrying inbound sync", 'RETRY', server=server, message=retry_message)
            raise self.retry(countdown=30)
        
        create_task_log(task_id, "sync_xray_inbounds", "Inbound sync failed after retries", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
        return {"error": error_message}


@shared_task(name="sync_xray_users", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def sync_xray_users(self, server_id):
    """Stage 2: Sync users for Xray server."""
    from vpn.server_plugins import Server
    from vpn.server_plugins.xray_v2 import XrayServerV2
    
    start_time = time.time()
    task_id = self.request.id
    server = None
    
    try:
        server = Server.objects.get(id=server_id)
        
        if not isinstance(server.get_real_instance(), XrayServerV2):
            error_message = f"Server {server.name} is not an Xray server"
            logger.error(error_message)
            create_task_log(task_id, "sync_xray_users", "Wrong server type", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
            return {"error": error_message}
        
        create_task_log(task_id, "sync_xray_users", f"Starting user sync for {server.name}", 'STARTED', server=server)
        logger.info(f"Starting user sync for Xray server {server.name}")
        
        # Don't call sync_users() which would create another task - directly perform the sync
        from vpn.models import User
        from vpn.models_xray import UserSubscription
        
        # Get all users who should have access to this server
        users_to_sync = User.objects.filter(
            xray_subscriptions__active=True,
            xray_subscriptions__subscription_group__is_active=True
        ).distinct()
        
        real_server = server.get_real_instance()
        
        added_count = 0
        failed_count = 0
        for user in users_to_sync:
            try:
                if real_server.add_user(user):
                    added_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to sync user {user.username} on server {server.name}: {e}")
        
        user_result = {"users_added": added_count, "total_users": users_to_sync.count(), "failed": failed_count}
        
        success_message = f"Successfully synced {user_result.get('users_added', 0)} users for {server.name}"
        logger.info(f"{success_message}. Result: {user_result}")
        
        create_task_log(task_id, "sync_xray_users", "User sync completed", 'SUCCESS', server=server, message=f"{success_message}. Result: {user_result}", execution_time=time.time() - start_time)
        
        return user_result
        
    except Server.DoesNotExist:
        error_message = f"Server with id {server_id} not found"
        logger.error(error_message)
        create_task_log(task_id, "sync_xray_users", "Server not found", 'FAILURE', message=error_message, execution_time=time.time() - start_time)
        return {"error": error_message}
    except Exception as e:
        error_message = f"Error syncing users for {server.name if server else server_id}: {e}"
        logger.error(error_message)
        
        if self.request.retries < 3:
            retry_message = f"Retrying user sync for {server.name if server else server_id} (attempt {self.request.retries + 1})"
            logger.info(retry_message)
            create_task_log(task_id, "sync_xray_users", "Retrying user sync", 'RETRY', server=server, message=retry_message)
            raise self.retry(countdown=30)
        
        create_task_log(task_id, "sync_xray_users", "User sync failed after retries", 'FAILURE', server=server, message=error_message, execution_time=time.time() - start_time)
        return {"error": error_message}

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
            logger.warning(error_message)
            create_task_log(task_id, "sync_all_users_on_server", "Server not found", 'SUCCESS', message=error_message, execution_time=time.time() - start_time)
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
        
        # For Xray servers, use the sync_server_users task to avoid recursion
        from vpn.server_plugins.xray_v2 import XrayServerV2
        if isinstance(server.get_real_instance(), XrayServerV2):
            logger.info(f"Using XrayServerV2 sync for server {server.name}")
            # Call sync_server_users directly to perform the actual sync
            # Avoid calling server.sync_users() which would create another task
            from vpn.models import User
            from vpn.models_xray import UserSubscription
            
            # Get all users who should have access to this server
            users_to_sync = User.objects.filter(
                xray_subscriptions__active=True,
                xray_subscriptions__subscription_group__is_active=True
            ).distinct()
            
            added_count = 0
            failed_count = 0
            for user in users_to_sync:
                try:
                    if server.add_user(user):
                        added_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to sync user {user.username} on server {server.name}: {e}")
            
            sync_result = {"users_added": added_count, "total_users": users_to_sync.count(), "failed": failed_count}
            logger.info(f"Directly synced {added_count} users for Xray server {server.name}")
        else:
            # For non-Xray servers, sync users directly (non-Xray servers should not create tasks)
            sync_result = server.sync_all_users()
        
        # Check if sync was successful (can be boolean or dict/string)
        sync_successful = bool(sync_result) and (
            sync_result is not False and 
            (isinstance(sync_result, str) and "failed" not in sync_result.lower()) or
            isinstance(sync_result, dict) or 
            sync_result is True
        )
        
        if sync_successful:
            success_message = f"Successfully synced {user_count} users for server {server.name}"
            if isinstance(sync_result, (str, dict)):
                success_message += f". Details: {sync_result}"
            logger.info(success_message)
            create_task_log(task_id, "sync_all_users_on_server", "User sync completed", 'SUCCESS', server=server, message=success_message, execution_time=time.time() - start_time)
            return success_message
        else:
            error_message = f"Sync failed for server {server.name}. Result: {sync_result}"
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


@shared_task(name="sync_user_xray_access", bind=True)
def sync_user_xray_access(self, user_id, server_id):
    """
    Sync user's Xray access based on subscription groups.
    Creates inbounds on server if needed and adds user to them.
    """
    from .models import User, Server
    from .models_xray import SubscriptionGroup, Inbound
    from vpn.xray_api_v2.client import XrayClient
    from vpn.server_plugins.xray_v2 import XrayServerV2
    
    start_time = time.time()
    task_id = self.request.id
    
    try:
        user = User.objects.get(id=user_id)
        server = Server.objects.get(id=server_id)
        
        # Get server instance
        real_server = server.get_real_instance()
        if not isinstance(real_server, XrayServerV2):
            raise ValueError(f"Server {server.name} is not an Xray v2 server")
        
        create_task_log(
            task_id, "sync_user_xray_access", 
            f"Starting Xray sync for {user.username} on {server.name}", 
            'STARTED', server=server, user=user
        )
        
        # Get user's active subscription groups
        user_groups = SubscriptionGroup.objects.filter(
            usersubscription__user=user,
            usersubscription__active=True,
            is_active=True
        ).prefetch_related('inbounds')
        
        if not user_groups.exists():
            logger.info(f"User {user.username} has no active subscriptions")
            return {"status": "No active subscriptions"}
        
        # Collect all inbounds from user's groups
        user_inbounds = Inbound.objects.filter(
            subscriptiongroup__in=user_groups
        ).distinct()
        
        logger.info(f"User {user.username} has access to {user_inbounds.count()} inbounds")
        
        # Connect to Xray server
        client = XrayClient(real_server.api_address)
        
        # Get existing inbounds on server
        try:
            existing_result = client.execute_command('lsi')  # List inbounds
            existing_inbounds = existing_result.get('inbounds', []) if existing_result else []
            existing_tags = {ib.get('tag') for ib in existing_inbounds if ib.get('tag')}
        except Exception as e:
            logger.warning(f"Failed to list existing inbounds: {e}")
            existing_tags = set()
        
        results = {
            'inbounds_created': [],
            'users_added': [],
            'errors': []
        }
        
        # Process each inbound
        for inbound in user_inbounds:
            try:
                # Check if inbound exists on server
                if inbound.name not in existing_tags:
                    logger.info(f"Creating inbound {inbound.name} on server")
                    
                    # Build inbound configuration
                    if not inbound.full_config:
                        inbound.build_config()
                        inbound.save()
                    
                    # Add inbound to server
                    client.execute_command('adi', json_files=[inbound.full_config])
                    results['inbounds_created'].append(inbound.name)
                
                # Add user to inbound
                logger.info(f"Adding user {user.username} to inbound {inbound.name}")
                
                # Create user config based on protocol
                import uuid
                
                # Generate user UUID based on username and inbound
                user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user.username}-{inbound.name}"))
                
                if inbound.protocol == 'vless':
                    user_config = {
                        "email": f"{user.username}@{server.name}",
                        "id": user_uuid,
                        "level": 0
                    }
                elif inbound.protocol == 'vmess':
                    user_config = {
                        "email": f"{user.username}@{server.name}",
                        "id": user_uuid,
                        "level": 0,
                        "alterId": 0
                    }
                elif inbound.protocol == 'trojan':
                    user_config = {
                        "email": f"{user.username}@{server.name}",
                        "password": user_uuid,
                        "level": 0
                    }
                else:
                    logger.warning(f"Unsupported protocol: {inbound.protocol}")
                    continue
                
                # Add user to inbound
                add_request = {
                    "inboundTag": inbound.name,
                    "user": user_config
                }
                
                client.execute_command('adu', json_files=[add_request])
                results['users_added'].append(f"{user.username} -> {inbound.name}")
                
            except Exception as e:
                error_msg = f"Error processing inbound {inbound.name}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        # Log results
        success_msg = (
            f"Xray sync completed for {user.username}: "
            f"Created {len(results['inbounds_created'])} inbounds, "
            f"Added user to {len(results['users_added'])} inbounds"
        )
        
        create_task_log(
            task_id, "sync_user_xray_access", 
            "Xray sync completed", 'SUCCESS', 
            server=server, user=user, 
            message=success_msg,
            execution_time=time.time() - start_time
        )
        
        return results
        
    except Exception as e:
        error_msg = f"Error in Xray sync: {e}"
        logger.error(error_msg, exc_info=True)
        
        create_task_log(
            task_id, "sync_user_xray_access", 
            "Xray sync failed", 'FAILURE', 
            message=error_msg,
            execution_time=time.time() - start_time
        )
        
        raise


@shared_task(name="sync_server_users", bind=True)
def sync_server_users(self, server_id):
    """
    Sync all users for a specific Xray server.
    This is called by XrayServerV2.sync_users()
    """
    from vpn.server_plugins import Server
    from vpn.models import User, ACL
    from vpn.models_xray import UserSubscription
    
    start_time = datetime.now()
    task_id = self.request.id
    
    try:
        server = Server.objects.get(id=server_id)
        real_server = server.get_real_instance()
        
        # Create initial log entry
        create_task_log(
            task_id=task_id,
            task_name='sync_server_users',
            action=f'Starting user sync for server {server.name}',
            status='STARTED',
            server=server
        )
        
        # Get all users who should have access to this server
        # For Xray v2, users access through subscription groups
        users_to_sync = User.objects.filter(
            xray_subscriptions__active=True,
            xray_subscriptions__subscription_group__is_active=True
        ).distinct()
        
        logger.info(f"Syncing {users_to_sync.count()} users for Xray server {server.name}")
        
        added_count = 0
        failed_count = 0
        for user in users_to_sync:
            try:
                if real_server.add_user(user):
                    added_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to sync user {user.username} on server {server.name}: {e}")
        
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Create success log
        create_task_log(
            task_id=task_id,
            task_name='sync_server_users',
            action=f'Completed user sync for server {server.name}',
            status='SUCCESS',
            server=server,
            message=f'Synced {added_count} of {users_to_sync.count()} users. Failed: {failed_count}',
            execution_time=execution_time
        )
        
        logger.info(f"Successfully synced {added_count} users for server {server.name}")
        return {"users_added": added_count, "total_users": users_to_sync.count(), "failed": failed_count}
        
    except Exception as e:
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Create failure log
        create_task_log(
            task_id=task_id,
            task_name='sync_server_users',
            action=f'Failed to sync users for server {server_id}',
            status='FAILURE',
            message=str(e),
            execution_time=execution_time
        )
        
        logger.error(f"Error syncing users for server {server_id}: {e}")
        raise


@shared_task(name="sync_server_inbounds", bind=True)
def sync_server_inbounds(self, server_id, auto_sync_users=True):
    """
    Sync all inbounds for a specific Xray server.
    This is called by XrayServerV2.sync_inbounds()
    """
    from vpn.server_plugins import Server
    from vpn.models_xray import SubscriptionGroup, ServerInbound, UserSubscription
    
    try:
        server = Server.objects.get(id=server_id)
        real_server = server.get_real_instance()
        
        # Get all subscription groups
        groups = SubscriptionGroup.objects.filter(is_active=True).prefetch_related('inbounds')
        
        deployed_count = 0
        for group in groups:
            for inbound in group.inbounds.all():
                try:
                    # Get users for this inbound
                    users_with_access = []
                    group_users = [
                        sub.user for sub in 
                        UserSubscription.objects.filter(
                            subscription_group=group,
                            active=True
                        ).select_related('user')
                    ]
                    users_with_access.extend(group_users)
                    
                    # Remove duplicates
                    users_with_access = list(set(users_with_access))
                    
                    # Deploy inbound with users
                    if real_server.deploy_inbound(inbound, users=users_with_access):
                        deployed_count += 1
                        
                        # Mark as deployed
                        ServerInbound.objects.update_or_create(
                            server=server,
                            inbound=inbound,
                            defaults={'active': True}
                        )
                        
                        logger.info(f"Deployed inbound {inbound.name} with {len(users_with_access)} users on server {server.name}")
                    else:
                        logger.error(f"Failed to deploy inbound {inbound.name} on server {server.name}")
                except Exception as e:
                    logger.error(f"Failed to deploy inbound {inbound.name} on server {server.name}: {e}")
        
        logger.info(f"Successfully deployed {deployed_count} inbounds on server {server.name}")
        
        # Automatically sync users after inbound deployment if requested
        if auto_sync_users and deployed_count > 0:
            logger.info(f"Scheduling user sync for server {server.name} after inbound deployment")
            sync_server_users.apply_async(args=[server_id], countdown=5)  # 5 second delay
        
        return {"inbounds_deployed": deployed_count, "auto_sync_users": auto_sync_users}
        
    except Exception as e:
        logger.error(f"Error syncing inbounds for server {server_id}: {e}")
        raise


@shared_task(name="deploy_inbound_on_server", bind=True)
def deploy_inbound_on_server(self, server_id, inbound_id):
    """
    Deploy a specific inbound on a specific server
    """
    from vpn.server_plugins import Server
    from vpn.models_xray import Inbound
    
    try:
        server = Server.objects.get(id=server_id)
        real_server = server.get_real_instance()
        inbound = Inbound.objects.get(id=inbound_id)
        
        logger.info(f"Deploying inbound {inbound.name} on server {server.name}")
        
        # Get all users that should have access to this inbound
        from vpn.models_xray import UserSubscription
        users_with_access = []
        
        # Find users through subscription groups
        for group in inbound.subscriptiongroup_set.filter(is_active=True):
            group_users = [
                sub.user for sub in 
                UserSubscription.objects.filter(
                    subscription_group=group,
                    active=True
                ).select_related('user')
            ]
            users_with_access.extend(group_users)
        
        # Remove duplicates
        users_with_access = list(set(users_with_access))
        
        logger.info(f"Deploying inbound {inbound.name} with {len(users_with_access)} users")
        
        # Deploy inbound with users
        if real_server.deploy_inbound(inbound, users=users_with_access):
            # Mark as deployed
            from vpn.models_xray import ServerInbound
            ServerInbound.objects.update_or_create(
                server=server,
                inbound=inbound,
                defaults={'active': True}
            )
            logger.info(f"Successfully deployed inbound {inbound.name} on server {server.name}")
            return {"success": True, "inbound": inbound.name, "server": server.name, "users": len(users_with_access)}
        else:
            logger.error(f"Failed to deploy inbound {inbound.name} on server {server.name}")
            return {"success": False, "inbound": inbound.name, "server": server.name, "error": "Deployment failed"}
            
    except Exception as e:
        logger.error(f"Error deploying inbound {inbound_id} on server {server_id}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="remove_inbound_from_server", bind=True)
def remove_inbound_from_server(self, server_id, inbound_name):
    """
    Remove a specific inbound from a specific server
    """
    from vpn.server_plugins import Server
    from vpn.xray_api_v2.client import XrayClient
    
    try:
        server = Server.objects.get(id=server_id)
        real_server = server.get_real_instance()
        
        logger.info(f"Removing inbound {inbound_name} from server {server.name}")
        
        # Remove inbound using Xray API
        client = XrayClient(server=real_server.api_address)
        result = client.remove_inbound(inbound_name)
        
        # Remove from ServerInbound tracking
        from vpn.models_xray import ServerInbound, Inbound
        try:
            inbound = Inbound.objects.get(name=inbound_name)
            ServerInbound.objects.filter(server=server, inbound=inbound).delete()
        except Inbound.DoesNotExist:
            pass  # Inbound was already deleted from Django
        
        logger.info(f"Successfully removed inbound {inbound_name} from server {server.name}")
        return {"success": True, "inbound": inbound_name, "server": server.name}
        
    except Exception as e:
        logger.error(f"Error removing inbound {inbound_name} from server {server_id}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="remove_user_from_server", bind=True)
def remove_user_from_server(self, server_id, user_id):
    """
    Remove a specific user from a specific server
    """
    from vpn.server_plugins import Server
    from vpn.models import User
    
    try:
        server = Server.objects.get(id=server_id)
        real_server = server.get_real_instance()
        user = User.objects.get(id=user_id)
        
        logger.info(f"Removing user {user.username} from server {server.name}")
        
        result = real_server.delete_user(user)
        
        if result:
            logger.info(f"Successfully removed user {user.username} from server {server.name}")
            return {"success": True, "user": user.username, "server": server.name}
        else:
            logger.warning(f"Failed to remove user {user.username} from server {server.name}")
            return {"success": False, "user": user.username, "server": server.name, "error": "Removal failed"}
            
    except Exception as e:
        logger.error(f"Error removing user {user_id} from server {server_id}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="generate_certificate_task", bind=True)
def generate_certificate_task(self, certificate_id):
    """
    Generate Let's Encrypt certificate for a domain
    """
    from .models_xray import Certificate
    from vpn.letsencrypt.letsencrypt_dns import get_certificate_for_domain
    from django.utils import timezone
    from datetime import timedelta
    
    start_time = time.time()
    task_id = self.request.id
    
    try:
        cert = Certificate.objects.get(id=certificate_id)
        
        create_task_log(
            task_id, "generate_certificate_task", 
            f"Starting certificate generation for {cert.domain}", 
            'STARTED'
        )
        
        # Check if we have credentials
        if not cert.credentials:
            raise ValueError(f"No credentials configured for {cert.domain}")
        
        # Get Cloudflare token from credentials
        cf_token = cert.credentials.get_credential('api_token')
        if not cf_token:
            raise ValueError(f"No Cloudflare API token found for {cert.domain}")
        
        logger.info(f"Generating certificate for {cert.domain} using email {cert.acme_email}")
        
        # Request certificate using the library function
        cert_pem, key_pem = get_certificate_for_domain(
            domain=cert.domain,
            email=cert.acme_email,
            cloudflare_token=cf_token,
            staging=False  # Production certificate
        )
        
        # Update certificate object
        cert.certificate_pem = cert_pem
        cert.private_key_pem = key_pem
        cert.expires_at = timezone.now() + timedelta(days=90)  # Let's Encrypt certs are valid for 90 days
        cert.last_renewed = timezone.now()
        cert.save()
        
        success_msg = f"Certificate for {cert.domain} generated successfully"
        logger.info(success_msg)
        
        create_task_log(
            task_id, "generate_certificate_task", 
            "Certificate generated", 'SUCCESS', 
            message=success_msg,
            execution_time=time.time() - start_time
        )
        
        return {"status": "success", "domain": cert.domain}
        
    except Certificate.DoesNotExist:
        error_msg = f"Certificate with id {certificate_id} not found"
        logger.error(error_msg)
        
        create_task_log(
            task_id, "generate_certificate_task", 
            "Certificate not found", 'FAILURE', 
            message=error_msg,
            execution_time=time.time() - start_time
        )
        raise
        
    except Exception as e:
        error_msg = f"Failed to generate certificate: {e}"
        logger.error(error_msg, exc_info=True)
        
        create_task_log(
            task_id, "generate_certificate_task", 
            "Certificate generation failed", 'FAILURE', 
            message=error_msg,
            execution_time=time.time() - start_time
        )
        raise


@shared_task(name="renew_certificates", bind=True)
def renew_certificates(self):
    """
    Check and renew certificates that are about to expire.
    """
    from .models_xray import Certificate
    from .letsencrypt import get_certificate_for_domain
    from datetime import datetime
    
    start_time = time.time()
    task_id = self.request.id
    
    create_task_log(task_id, "renew_certificates", "Starting certificate renewal check", 'STARTED')
    
    try:
        # Get certificates that need renewal
        certs_to_renew = Certificate.objects.filter(
            auto_renew=True,
            cert_type='letsencrypt'
        )
        
        renewed_count = 0
        errors = []
        
        for cert in certs_to_renew:
            if not cert.needs_renewal:
                continue
                
            try:
                logger.info(f"Renewing certificate for {cert.domain}")
                
                # Check if we have credentials
                if not cert.credentials:
                    logger.warning(f"No credentials configured for {cert.domain}")
                    continue
                
                # Get Cloudflare token from credentials
                cf_token = cert.credentials.get_credential('api_token')
                cf_email = cert.credentials.get_credential('email', 'admin@example.com')
                
                if not cf_token:
                    logger.error(f"No Cloudflare API token found for {cert.domain}")
                    continue
                
                # Renew certificate
                cert_pem, key_pem = get_certificate_for_domain(
                    domain=cert.domain,
                    email=cf_email,
                    cloudflare_token=cf_token,
                    staging=False  # Production certificate
                )
                
                # Update certificate
                cert.certificate_pem = cert_pem
                cert.private_key_pem = key_pem
                cert.last_renewed = datetime.now()
                cert.expires_at = datetime.now() + timedelta(days=90)  # Let's Encrypt certs are valid for 90 days
                cert.save()
                
                renewed_count += 1
                logger.info(f"Successfully renewed certificate for {cert.domain}")
                
            except Exception as e:
                error_msg = f"Failed to renew certificate for {cert.domain}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Summary
        if renewed_count > 0 or errors:
            summary = f"Renewed {renewed_count} certificates"
            if errors:
                summary += f", {len(errors)} errors"
            
            create_task_log(
                task_id, "renew_certificates", 
                "Certificate renewal completed", 
                'SUCCESS' if not errors else 'PARTIAL', 
                message=summary,
                execution_time=time.time() - start_time
            )
        else:
            create_task_log(
                task_id, "renew_certificates", 
                "No certificates need renewal", 
                'SUCCESS',
                execution_time=time.time() - start_time
            )
        
        return {
            'renewed': renewed_count,
            'errors': errors
        }
        
    except Exception as e:
        error_msg = f"Certificate renewal task failed: {e}"
        logger.error(error_msg, exc_info=True)
        
        create_task_log(
            task_id, "renew_certificates", 
            "Certificate renewal failed", 
            'FAILURE', 
            message=error_msg,
            execution_time=time.time() - start_time
        )
        
        raise