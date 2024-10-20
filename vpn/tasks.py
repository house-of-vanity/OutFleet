
import logging
from celery import shared_task
#from django_celery_results.models import TaskResult
from outline_vpn.outline_vpn import OutlineServerErrorException


logger = logging.getLogger(__name__)

class TaskFailedException(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(f"{self.message}")


@shared_task(name="sync.server")
def sync_server(id):
    from vpn.server_plugins import Server
    # task_result = TaskResult.objects.get_task(self.request.id) 
    # task_result.status='RUNNING'
    # task_result.save()
    return {"status": Server.objects.get(id=id).sync()}

@shared_task(name="sync.user")
def sync_user(id):
    from .models import User, ACL
    from vpn.server_plugins import Server
    
    errors = {}
    result = {}
    user = User.objects.get(id=id)
    acls = ACL.objects.filter(user=user)

    servers = Server.objects.all()
    
    for server in servers:
        try:
            if acls.filter(server=server).exists():
                result[server.name] = server.add_user(user)
            else:
                result[server.name] = server.delete_user(user)

        except User.DoesNotExist as e:
            result = {"error": e}
            logger.error("User not found.")
        except Exception as e:
            errors[server.name] = {"error": e}
        finally:
            if errors:
                logger.error("ERROR ERROR")
                raise TaskFailedException(message=f"Errors during taks: {errors}")
            else:
                logger.error(f"PUK PUEK. {errors}")
            return result