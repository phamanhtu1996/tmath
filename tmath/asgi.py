"""
ASGI config for tmath project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.urls import path
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

from judge.consumers import SubmissionConsumer, DetailSubmission, TicketConsumer, DetailTicketConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tmath.settings')

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
    )
})