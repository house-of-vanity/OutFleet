
import logging
from celery import group, shared_task
#from django_celery_results.models import TaskResult
from outline_vpn.outline_vpn import OutlineServerErrorException


logger = logging.getLogger(__name__)

class TaskFailedException(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(f"{self.message}")


@shared_task(name="sync_all_servers")
def sync_all_users():
    from .models import User, ACL
    from vpn.server_plugins import Server

    servers = Server.objects.all()
    
    tasks = group(sync_users.s(server.id) for server in servers)

    result = tasks.apply_async()
    
    return result

@shared_task(name="sync_all_users_on_server")
def sync_users(server_id):
    from .models import Server
    
    try:
        server = Server.objects.get(id=server_id)
        server.sync_users()
        logger.info(f"Successfully synced users for server {server.name}")
    except Exception as e:
        logger.error(f"Error syncing users for server {server.name}: {e}")
        raise TaskFailedException(message=f"Error syncing users for server {server.name}")

@shared_task(name="sync_server_info")
def sync_server(id):
    from vpn.server_plugins import Server
    # task_result = TaskResult.objects.get_task(self.request.id) 
    # task_result.status='RUNNING'
    # task_result.save()
    return {"status": Server.objects.get(id=id).sync()}

@shared_task(name="sync_user_on_server")
def sync_user(user, server_id):
    from .models import User, ACL
    from vpn.server_plugins import Server
    
    errors = {}
    result = {}
    acls = ACL.objects.filter(user=user)

    server = Server.objects.get(id=server_id)

    try:
        if acls.filter(server=server).exists():
            result[server.name] = server.add_user(user)
        else:
            result[server.name] = server.delete_user(user)
    except Exception as e:
        errors[server.name] = {"error": e}
    finally:
        if errors:
            raise TaskFailedException(message=f"Errors during taks: {errors}")
        return result