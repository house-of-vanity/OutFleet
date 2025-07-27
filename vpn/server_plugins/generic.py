from polymorphic.models import PolymorphicModel
from django.db import models


class Server(PolymorphicModel):
    SERVER_TYPE_CHOICES = (
        ('Outline', 'Outline'),
        ('Wireguard', 'Wireguard'),
        ('xray_core', 'Xray Core'),
    )

    name = models.CharField(max_length=100, help_text="Server name")
    comment = models.TextField(default="", blank=True)
    registration_date = models.DateTimeField(auto_now_add=True, verbose_name="Created")
    server_type = models.CharField(max_length=50, choices=SERVER_TYPE_CHOICES, editable=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        # Only sync if the server actually exists and is valid
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Schedule sync task for existing servers only
        if not is_new:
            try:
                from vpn.tasks import sync_server
                sync_server.delay(self.id)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to schedule sync for server {self.name}: {e}")

    def get_server_status(self, *args, **kwargs):
        return {"name": self.name}

    def sync(self, *args, **kwargs):
        pass

    def sync_users(self, *args, **kwargs):
        pass

    def add_user(self, *args, **kwargs):
        pass

    def get_user(self, *args, **kwargs):
        pass

    def delete_user(self, *args, **kwargs):
        pass

    class Meta:
        verbose_name = "Server"
        verbose_name_plural = "Servers"
        permissions = [
            ("access_server", "Can view public status"),
        ]

    def __str__(self):
        return self.name
