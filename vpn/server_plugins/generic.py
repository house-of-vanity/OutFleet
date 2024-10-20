from polymorphic.models import PolymorphicModel
from django.db import models
from vpn.tasks import sync_server


class Server(PolymorphicModel):
    SERVER_TYPE_CHOICES = (
        ('Outline', 'Outline'),
        ('Wireguard', 'Wireguard'),
    )

    name = models.CharField(max_length=100)
    comment = models.TextField(default="", blank=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    server_type = models.CharField(max_length=50, choices=SERVER_TYPE_CHOICES, editable=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        sync_server.delay(self.id)
        super().save(*args, **kwargs)

    def get_server_status(self, *args, **kwargs):
        return {"name": self.name}

    def sync(self, *args, **kwargs):
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

    def __str__(self):
        return self.name
