from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from judge.consumers import SubmissionConsumer, DetailSubmission

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter([
            path('ws/submissions/', SubmissionConsumer.as_asgi()),
            path('ws/submission/<int:id>/', DetailSubmission.as_asgi()),
        ])
    ),
})