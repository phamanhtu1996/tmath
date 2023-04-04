import os

from django.urls import path
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack
from judge.consumers import SubmissionConsumer, DetailSubmission, TicketConsumer, DetailTicketConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmoj.settings')

ws_patterns = [
    path('ws/submissions/', SubmissionConsumer.as_asgi()),
    path('ws/submission/<str:key>/', DetailSubmission.as_asgi()),
    path('ws/tickets/', TicketConsumer.as_asgi()),
    path('ws/ticket/<int:id>/', DetailTicketConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(ws_patterns)
        )
    ),
})