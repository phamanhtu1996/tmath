from django.urls import path
from django.conf.urls import include
from .views import make_message

app_name = 'chat'

urlpatterns = [
    path('send/', make_message, name="send_message")
]
