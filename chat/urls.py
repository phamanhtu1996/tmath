from django.urls import path
from django.conf.urls import url, include
from .views import make_message

app_name = 'chat'

urlpatterns = [
    url(r'^send$', make_message, name="send_message")
]
