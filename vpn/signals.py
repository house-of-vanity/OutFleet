"""
Django signals for automatic Xray server synchronization
"""
import logging
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.db import transaction
from celery import group

from .models_xray import (
    Inbound, 
    SubscriptionGroup, 
    UserSubscription, 
    Certificate,
    ServerInbound
)
from .server_plugins.xray_v2 import XrayServerV2

logger = logging.getLogger(__name__)


def get_active_xray_servers():
    """Get all active Xray servers"""
    from .server_plugins import Server
    return [
        server.get_real_instance() 
        for server in Server.objects.all() 
        if hasattr(server.get_real_instance(), 'api_enabled') and 
           server.get_real_instance().api_enabled
    ]


def schedule_inbound_sync_for_servers(inbound, servers=None):
    """Schedule inbound deployment on servers"""
    if servers is None:
        servers = get_active_xray_servers()
    
    if not servers:
        logger.warning("No active Xray servers found for inbound sync")
        return
    
    logger.info(f"Scheduling inbound {inbound.name} deployment on {len(servers)} servers")
    
    # Schedule deployment tasks
    from .tasks import deploy_inbound_on_server
    tasks = []
    for server in servers:
        task = deploy_inbound_on_server.s(server.id, inbound.id)
        tasks.append(task)
    
    # Execute all deployments in parallel
    job = group(tasks)
    result = job.apply_async()
    
    logger.info(f"Scheduled inbound deployment tasks: {result}")
    return result


def schedule_user_sync_for_servers(servers=None):
    """Schedule user sync on servers after inbound changes"""
    if servers is None:
        servers = get_active_xray_servers()
    
    if not servers:
        logger.warning("No active Xray servers found for user sync")
        return
    
    logger.info(f"Scheduling user sync on {len(servers)} servers")
    
    # Schedule user sync tasks
    from .tasks import sync_server_users
    tasks = []
    for server in servers:
        task = sync_server_users.s(server.id)
        tasks.append(task)
    
    # Execute all user syncs in parallel with delay to allow inbound sync to complete
    job = group(tasks)
    result = job.apply_async(countdown=10)  # 10 second delay
    
    logger.info(f"Scheduled user sync tasks: {result}")
    return result


@receiver(post_save, sender=Inbound)
def inbound_created_or_updated(sender, instance, created, **kwargs):
    """
    When an inbound is created or updated, deploy it to all servers
    where subscription groups contain this inbound
    """
    if created:
        logger.info(f"New inbound {instance.name} created, will deploy when added to groups")
    else:
        logger.info(f"Inbound {instance.name} updated, scheduling redeployment")
        
        # Get all subscription groups that contain this inbound
        groups = instance.subscriptiongroup_set.filter(is_active=True)
        
        if groups.exists():
            # Get all servers that should have this inbound
            servers = get_active_xray_servers()
            
            # Schedule redeployment
            transaction.on_commit(lambda: schedule_inbound_sync_for_servers(instance, servers))
            
            # Schedule user sync after inbound update
            transaction.on_commit(lambda: schedule_user_sync_for_servers(servers))


@receiver(post_delete, sender=Inbound)
def inbound_deleted(sender, instance, **kwargs):
    """
    When an inbound is deleted, remove it from all servers
    """
    logger.info(f"Inbound {instance.name} deleted, scheduling removal from servers")
    
    # Schedule removal from all servers
    from .tasks import remove_inbound_from_server
    servers = get_active_xray_servers()
    tasks = []
    
    for server in servers:
        task = remove_inbound_from_server.s(server.id, instance.name)
        tasks.append(task)
    
    if tasks:
        job = group(tasks)
        transaction.on_commit(lambda: job.apply_async())


@receiver(m2m_changed, sender=SubscriptionGroup.inbounds.through)
def subscription_group_inbounds_changed(sender, instance, action, pk_set, **kwargs):
    """
    When inbounds are added/removed from subscription groups,
    automatically deploy/remove them on servers
    """
    if action in ['post_add', 'post_remove']:
        logger.info(f"Subscription group {instance.name} inbounds changed: {action}")
        
        if action == 'post_add' and pk_set:
            # Inbounds were added to the group - deploy them
            inbounds = Inbound.objects.filter(pk__in=pk_set)
            servers = get_active_xray_servers()
            
            for inbound in inbounds:
                logger.info(f"Deploying inbound {inbound.name} (added to group {instance.name})")
                transaction.on_commit(
                    lambda inb=inbound: schedule_inbound_sync_for_servers(inb, servers)
                )
            
            # Schedule user sync after all inbounds are deployed
            transaction.on_commit(lambda: schedule_user_sync_for_servers(servers))
            
        elif action == 'post_remove' and pk_set:
            # Inbounds were removed from the group
            inbounds = Inbound.objects.filter(pk__in=pk_set)
            
            for inbound in inbounds:
                # Check if inbound is still used by other active groups
                other_groups = inbound.subscriptiongroup_set.filter(is_active=True).exclude(id=instance.id)
                
                if not other_groups.exists():
                    # Inbound is not used by any other group - remove from servers
                    logger.info(f"Removing inbound {inbound.name} from servers (no longer in any group)")
                    from .tasks import remove_inbound_from_server
                    servers = get_active_xray_servers()
                    tasks = []
                    
                    for server in servers:
                        task = remove_inbound_from_server.s(server.id, inbound.name)
                        tasks.append(task)
                    
                    if tasks:
                        job = group(tasks)
                        transaction.on_commit(lambda: job.apply_async())


@receiver(post_save, sender=ServerInbound)
def server_inbound_created_or_updated(sender, instance, created, **kwargs):
    """
    When ServerInbound is created or updated, immediately deploy the inbound
    template to the server (not wait for subscription group changes)
    """
    logger.info(f"ServerInbound {instance.inbound.name} {'created' if created else 'updated'} for server {instance.server.name}")
    
    if instance.active:
        # Deploy inbound immediately
        servers = [instance.server.get_real_instance()]
        transaction.on_commit(
            lambda: schedule_inbound_sync_for_servers(instance.inbound, servers)
        )
        
        # Schedule user sync after inbound deployment
        transaction.on_commit(lambda: schedule_user_sync_for_servers(servers))
    else:
        # Remove inbound from server if deactivated
        logger.info(f"Removing inbound {instance.inbound.name} from server {instance.server.name} (deactivated)")
        from .tasks import remove_inbound_from_server
        task = remove_inbound_from_server.s(instance.server.id, instance.inbound.name)
        transaction.on_commit(lambda: task.apply_async())


@receiver(post_delete, sender=ServerInbound)
def server_inbound_deleted(sender, instance, **kwargs):
    """
    When ServerInbound is deleted, remove the inbound from the server
    """
    logger.info(f"ServerInbound {instance.inbound.name} deleted from server {instance.server.name}")
    
    from .tasks import remove_inbound_from_server
    task = remove_inbound_from_server.s(instance.server.id, instance.inbound.name)
    transaction.on_commit(lambda: task.apply_async())


@receiver(post_save, sender=UserSubscription)
def user_subscription_created_or_updated(sender, instance, created, **kwargs):
    """
    When user subscription is created or updated, sync the user to servers
    """
    if created:
        logger.info(f"New subscription created for user {instance.user.username} in group {instance.subscription_group.name}")
    else:
        logger.info(f"Subscription updated for user {instance.user.username} in group {instance.subscription_group.name}")
    
    if instance.active:
        # Schedule user sync on all servers
        servers = get_active_xray_servers()
        transaction.on_commit(lambda: schedule_user_sync_for_servers(servers))


@receiver(post_delete, sender=UserSubscription)
def user_subscription_deleted(sender, instance, **kwargs):
    """
    When user subscription is deleted, remove user from servers if no other subscriptions
    """
    logger.info(f"Subscription deleted for user {instance.user.username} in group {instance.subscription_group.name}")
    
    # Check if user has other active subscriptions
    other_subscriptions = UserSubscription.objects.filter(
        user=instance.user,
        active=True
    ).exclude(id=instance.id).exists()
    
    if not other_subscriptions:
        # User has no more subscriptions - remove from all servers
        logger.info(f"User {instance.user.username} has no more subscriptions, removing from servers")
        from .tasks import remove_user_from_server
        servers = get_active_xray_servers()
        tasks = []
        
        for server in servers:
            task = remove_user_from_server.s(server.id, instance.user.id)
            tasks.append(task)
        
        if tasks:
            job = group(tasks)
            transaction.on_commit(lambda: job.apply_async())


@receiver(post_save, sender=Certificate)
def certificate_updated(sender, instance, created, **kwargs):
    """
    When certificate is updated, redeploy all inbounds that use it
    """
    if not created and instance.certificate_pem:  # Only on updates when cert is available
        logger.info(f"Certificate {instance.domain} updated, redeploying dependent inbounds")
        
        # Find all inbounds that use this certificate
        inbounds = Inbound.objects.filter(certificate=instance)
        servers = get_active_xray_servers()
        
        for inbound in inbounds:
            transaction.on_commit(
                lambda inb=inbound: schedule_inbound_sync_for_servers(inb, servers)
            )


@receiver(post_save, sender=SubscriptionGroup)
def subscription_group_updated(sender, instance, created, **kwargs):
    """
    When subscription group is created/updated, sync its state
    """
    if created:
        logger.info(f"New subscription group {instance.name} created")
    else:
        logger.info(f"Subscription group {instance.name} updated")
        
        if not instance.is_active:
            # Group was deactivated - remove its inbounds from servers if not used elsewhere
            logger.info(f"Subscription group {instance.name} deactivated, checking inbounds")
            
            for inbound in instance.inbounds.all():
                # Check if inbound is used by other active groups
                other_groups = inbound.subscriptiongroup_set.filter(is_active=True).exclude(id=instance.id)
                
                if not other_groups.exists():
                    # Remove inbound from servers
                    logger.info(f"Removing inbound {inbound.name} from servers (group deactivated)")
                    from .tasks import remove_inbound_from_server
                    servers = get_active_xray_servers()
                    tasks = []
                    
                    for server in servers:
                        task = remove_inbound_from_server.s(server.id, inbound.name)
                        tasks.append(task)
                    
                    if tasks:
                        job = group(tasks)
                        transaction.on_commit(lambda: job.apply_async())


@receiver(post_save, sender=ServerInbound)
def server_inbound_created_or_updated(sender, instance, created, **kwargs):
    """
    When ServerInbound is created or updated, immediately deploy the inbound
    template to the server (not wait for subscription group changes)
    """
    logger.info(f"ServerInbound {instance.inbound.name} {'created' if created else 'updated'} for server {instance.server.name}")
    
    if instance.active:
        # Deploy inbound immediately
        servers = [instance.server.get_real_instance()]
        transaction.on_commit(
            lambda: schedule_inbound_sync_for_servers(instance.inbound, servers)
        )
        
        # Schedule user sync after inbound deployment
        transaction.on_commit(lambda: schedule_user_sync_for_servers(servers))
    else:
        # Remove inbound from server if deactivated
        logger.info(f"Removing inbound {instance.inbound.name} from server {instance.server.name} (deactivated)")
        from .tasks import remove_inbound_from_server
        task = remove_inbound_from_server.s(instance.server.id, instance.inbound.name)
        transaction.on_commit(lambda: task.apply_async())


@receiver(post_delete, sender=ServerInbound)
def server_inbound_deleted(sender, instance, **kwargs):
    """
    When ServerInbound is deleted, remove the inbound from the server
    """
    logger.info(f"ServerInbound {instance.inbound.name} deleted from server {instance.server.name}")
    
    from .tasks import remove_inbound_from_server
    task = remove_inbound_from_server.s(instance.server.id, instance.inbound.name)
    transaction.on_commit(lambda: task.apply_async())