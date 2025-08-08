import uuid
import logging
from django.db import models
from vpn.tasks import sync_user
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .server_plugins import Server
import shortuuid

from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)

class UserStatistics(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    server_name = models.CharField(max_length=256)
    acl_link_id = models.CharField(max_length=1024, null=True, blank=True, help_text="None for server-level stats")
    
    total_connections = models.IntegerField(default=0)
    recent_connections = models.IntegerField(default=0)
    daily_usage = models.JSONField(default=list, help_text="Daily connection counts for last 30 days")
    max_daily = models.IntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'server_name', 'acl_link_id']
        verbose_name = 'User Statistics'
        verbose_name_plural = 'User Statistics'
        indexes = [
            models.Index(fields=['user', 'server_name']),
            models.Index(fields=['updated_at']),
        ]
    
    def __str__(self):
        link_part = f" (link: {self.acl_link_id})" if self.acl_link_id else " (server total)"
        return f"{self.user.username} - {self.server_name}{link_part}"

class TaskExecutionLog(models.Model):
    task_id = models.CharField(max_length=255, help_text="Celery task ID")
    task_name = models.CharField(max_length=100, help_text="Task name")
    server = models.ForeignKey('Server', on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100, help_text="Action performed")
    status = models.CharField(max_length=20, choices=[
        ('STARTED', 'Started'),
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
        ('RETRY', 'Retry'),
    ], default='STARTED')
    message = models.TextField(help_text="Detailed execution message")
    execution_time = models.FloatField(null=True, blank=True, help_text="Execution time in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Execution Log'
        verbose_name_plural = 'Task Execution Logs'
        indexes = [
            models.Index(fields=['task_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.task_name} - {self.action} ({self.status})"


class AccessLog(models.Model):
    user = models.CharField(max_length=256, blank=True, null=True, editable=False)
    server = models.CharField(max_length=256, blank=True, null=True, editable=False)
    acl_link_id = models.CharField(max_length=1024, blank=True, null=True, editable=False, help_text="ID of the ACL link used")
    action = models.CharField(max_length=100, editable=False)
    data = models.TextField(default="", blank=True, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['server']),
            models.Index(fields=['acl_link_id']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        link_part = f" (link: {self.acl_link_id})" if self.acl_link_id else ""
        return f"{self.action} {self.user} request for {self.server}{link_part} at {self.timestamp}"

class User(AbstractUser):
    #is_active = False
    comment = models.TextField(default="", blank=True, help_text="Free form user comment")
    registration_date = models.DateTimeField(auto_now_add=True, verbose_name="Created")
    servers = models.ManyToManyField('Server', through='ACL', blank=True, help_text="Servers user has access to")
    last_access = models.DateTimeField(null=True, blank=True)
    hash = models.CharField(max_length=64, unique=True, help_text="Random user hash. It's using for client config generation.")

    def get_servers(self):
        return Server.objects.filter(acl__user=self)

    def save(self, *args, **kwargs):
        if not self.hash:
            self.hash = shortuuid.ShortUUID().random(length=16)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class ACL(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    server = models.ForeignKey('Server', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'server'], name='unique_user_server')
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.server.name}"
    
    def save(self, *args, **kwargs):
        # Check if this is a new ACL and if auto_create_link should be enabled
        is_new = self.pk is None
        auto_create_link = kwargs.pop('auto_create_link', True)
        
        super().save(*args, **kwargs)
        
        # Only create default link for new ACLs when auto_create_link is True
        # This happens when ACL is created through admin interface or initial user setup
        if is_new and auto_create_link and not self.links.exists():
            ACLLink.objects.create(acl=self, link=shortuuid.ShortUUID().random(length=16))

@receiver(post_save, sender=ACL)
def acl_created_or_updated(sender, instance, created, **kwargs):
    try:
        sync_user.delay_on_commit(instance.user.id, instance.server.id)
        if created:
            logger.info(f"Scheduled sync for new ACL: user {instance.user.username} on server {instance.server.name}")
        else:
            logger.info(f"Scheduled sync for updated ACL: user {instance.user.username} on server {instance.server.name}")
    except Exception as e:
        logger.error(f"Failed to schedule sync task for ACL {instance.id}: {e}")
        # Don't raise exception to avoid blocking ACL creation/update

@receiver(pre_delete, sender=ACL)
def acl_deleted(sender, instance, **kwargs):
    try:
        sync_user.delay_on_commit(instance.user.id, instance.server.id)
        logger.info(f"Scheduled sync for deleted ACL: user {instance.user.username} on server {instance.server.name}")
    except Exception as e:
        logger.error(f"Failed to schedule sync task for ACL deletion {instance.id}: {e}")
        # Don't raise exception to avoid blocking ACL deletion


class ACLLink(models.Model):
    acl = models.ForeignKey(ACL, related_name='links', on_delete=models.CASCADE)
    comment = models.TextField(default="", blank=True, help_text="ACL link comment, device name, etc...")
    link = models.CharField(max_length=1024, default="", unique=True, blank=True, null=True, verbose_name="Access link", help_text="Access link to get dynamic configuration")
    last_access_time = models.DateTimeField(null=True, blank=True, help_text="Last time this link was accessed")

    def save(self, *args, **kwargs):
        if self.link == "":
            self.link = shortuuid.ShortUUID().random(length=16)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.link


# Import new Xray models
from .models_xray import (
    Credentials, Certificate,
    Inbound, SubscriptionGroup, UserSubscription
)
