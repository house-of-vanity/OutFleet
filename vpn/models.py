import uuid
from django.db import models
from vpn.tasks import sync_user
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .server_plugins import Server
import shortuuid

from django.contrib.auth.models import AbstractUser

class AccessLog(models.Model):
    user = models.CharField(max_length=256, blank=True, null=True, editable=False)
    server = models.CharField(max_length=256, blank=True, null=True, editable=False)
    action = models.CharField(max_length=100, editable=False)
    data = models.TextField(default="", blank=True, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.user} request for {self.server} at {self.timestamp}"

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
        super().save(*args, **kwargs)
        if not self.links.exists():
            ACLLink.objects.create(acl=self, link=shortuuid.ShortUUID().random(length=16))

@receiver(post_save, sender=ACL)
def acl_created_or_updated(sender, instance, created, **kwargs):
    sync_user.delay_on_commit(instance.user.id, instance.server.id)

@receiver(pre_delete, sender=ACL)
def acl_deleted(sender, instance, **kwargs):
    sync_user.delay_on_commit(instance.user.id, instance.server.id)


class ACLLink(models.Model):
    acl = models.ForeignKey(ACL, related_name='links', on_delete=models.CASCADE)
    comment = models.TextField(default="", blank=True, help_text="ACL link comment, device name, etc...")
    link = models.CharField(max_length=1024, default="", unique=True, blank=True, null=True, verbose_name="Access link", help_text="Access link to get dynamic configuration")

    def save(self, *args, **kwargs):
        if self.link == "":
            self.link = shortuuid.ShortUUID().random(length=16)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.link