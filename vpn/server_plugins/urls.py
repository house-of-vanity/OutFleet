from django.urls import path
from vpn.views import shadowsocks

urlpatterns = [
    path('ss/<str:hash_value>/', shadowsocks, name='shadowsocks'),
]