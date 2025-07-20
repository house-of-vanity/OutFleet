
import logging
from celery import group, shared_task
from celery.exceptions import Retry

logger = logging.getLogger(__name__)

class TaskFailedException(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(f"{self.message}")


@shared_task(name="sync_all_servers", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_all_users(self):
    from vpn.server_plugins import Server

    servers = Server.objects.all()
    
    if not servers.exists():
        logger.warning("No servers found for synchronization")
        return "No servers to sync"
    
    tasks = group(sync_users.s(server.id) for server in servers)
    result = tasks.apply_async()
    
    return f"Initiated sync for {servers.count()} servers"

@shared_task(name="sync_all_users_on_server", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_users(self, server_id):
    from vpn.server_plugins import Server
    
    try:
        server = Server.objects.get(id=server_id)
        logger.info(f"Starting user sync for server {server.name}")
        
        sync_result = server.sync_users()
        
        if sync_result:
            logger.info(f"Successfully synced users for server {server.name}")
            return f"Successfully synced users for server {server.name}"
        else:
            raise TaskFailedException(f"Sync failed for server {server.name}")
            
    except Server.DoesNotExist:
        logger.error(f"Server with id {server_id} not found")
        raise TaskFailedException(f"Server with id {server_id} not found")
    except Exception as e:
        logger.error(f"Error syncing users for server id {server_id}: {e}")
        if self.request.retries < 3:
            logger.info(f"Retrying sync for server id {server_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60)
        raise TaskFailedException(f"Error syncing users for server id {server_id}: {e}")

@shared_task(name="sync_server_info", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def sync_server(self, id):
    from vpn.server_plugins import Server
    
    try:
        server = Server.objects.get(id=id)
        logger.info(f"Starting server info sync for {server.name}")
        
        sync_result = server.sync()
        return {"status": sync_result, "server": server.name}
        
    except Server.DoesNotExist:
        logger.error(f"Server with id {id} not found")
        return {"error": f"Server with id {id} not found"}
    except Exception as e:
        logger.error(f"Error syncing server info for id {id}: {e}")
        if self.request.retries < 3:
            logger.info(f"Retrying server sync for id {id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=30)
        return {"error": f"Error syncing server info: {e}"}

@shared_task(name="sync_user_on_server", bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 5, 'countdown': 30})
def sync_user(self, user_id, server_id):
    from .models import User, ACL
    from vpn.server_plugins import Server
    
    errors = {}
    result = {}
    
    try:
        user = User.objects.get(id=user_id)
        server = Server.objects.get(id=server_id)
        
        logger.info(f"Syncing user {user.username} on server {server.name}")
        
        # Check if ACL exists
        acl_exists = ACL.objects.filter(user=user, server=server).exists()
        
        if acl_exists:
            # User should exist on server
            result[server.name] = server.add_user(user)
            logger.info(f"Added/updated user {user.username} on server {server.name}")
        else:
            # User should be removed from server
            result[server.name] = server.delete_user(user)
            logger.info(f"Removed user {user.username} from server {server.name}")
            
    except User.DoesNotExist:
        error_msg = f"User with id {user_id} not found"
        logger.error(error_msg)
        errors["user"] = error_msg
    except Server.DoesNotExist:
        error_msg = f"Server with id {server_id} not found"
        logger.error(error_msg)
        errors["server"] = error_msg
    except Exception as e:
        error_msg = f"Error syncing user {user_id} on server {server_id}: {e}"
        logger.error(error_msg)
        errors[f"server_{server_id}"] = error_msg
        
        # Retry on failure unless it's a permanent error
        if self.request.retries < 5:
            logger.info(f"Retrying user sync for user {user_id} on server {server_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=30)
    
    if errors:
        raise TaskFailedException(message=f"Errors during task: {errors}")
    
    return result