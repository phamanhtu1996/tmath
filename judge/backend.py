from typing import Any, Optional
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.base_user import AbstractBaseUser
from django.http.request import HttpRequest
from django.utils import timezone

class CustomAuthBackend(ModelBackend):
    def authenticate(self, request: HttpRequest, username: str | None = ..., password: str | None = ..., **kwargs: Any) -> AbstractBaseUser | None:
        user = super().authenticate(request, username, password, **kwargs)
        if user is not None:
            if user.profile.expiration_date is not None and user.profile.expiration_date < timezone.now():
                return None
        return user