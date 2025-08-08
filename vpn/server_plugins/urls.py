from django.urls import path
from vpn.views import shadowsocks, xray_subscription

urlpatterns = [
    path('ss/<str:hash_value>/', shadowsocks, name='shadowsocks'),
    path('xray/<str:user_hash>/', xray_subscription, name='xray_subscription'),
]