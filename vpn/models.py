import uuid
from django.db import models
from vpn.tasks import sync_user
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .server_plugins import Server
import shortuuid

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    #username = models.CharField(max_length=100)
    is_active = False
    comment = models.TextField(default="", blank=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    servers = models.ManyToManyField('Server', through='ACL', blank=True)
    last_access = models.DateTimeField(null=True, blank=True)
    hash = models.CharField(max_length=64, unique=True)

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
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=64, unique=True, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'server'], name='unique_user_server')
        ]

    
    def __str__(self):
        return f"{self.user.username} - {self.server.name}"
    
    def save(self, *args, **kwargs):
        if not self.link:
            self.link = shortuuid.ShortUUID().random(length=16)
        super().save(*args, **kwargs)

@receiver(post_save, sender=ACL)
def acl_created_or_updated(sender, instance, created, **kwargs):
    sync_user.delay_on_commit(instance.user.id, instance.server.id)

@receiver(pre_delete, sender=ACL)
def acl_deleted(sender, instance, **kwargs):
    sync_user.delay_on_commit(instance.user.id, instance.server.id)