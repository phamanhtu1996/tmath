from reversion.admin import VersionAdmin

from django.contrib import admin
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import models
from django import forms

# Register your models here.

from chat.models import ChatMessage, ChatRoom
from judge.widgets import AdminHeavySelect2MultipleWidget, AdminHeavySelect2Widget


class ChatRoomForm(forms.ModelForm):
  class Meta:
    model = ChatRoom
    fields = '__all__'


@admin.register(ChatRoom)
class ChatRoomAdmin(VersionAdmin):
  list_filter = ['id', 'title']
  search_fields = ['id', 'title']
  list_display = ['id', 'organization', 'title']
  form = ChatRoomForm
  readonly_fields = ['organization']

  class Meta:
    model = ChatRoom

# Resource: http://masnun.rocks/2017/03/20/django-admin-expensive-count-all-queries/
class CachingPaginator(Paginator):
  def _get_count(self):

    if not hasattr(self, "_count"):
      self._count = None

    if self._count is None:
      try:
        key = "adm:{0}:count".format(hash(self.object_list.query.__str__()))
        self._count = cache.get(key, -1)
        if self._count == -1:
          self._count = super().count
          cache.set(key, self._count, 3600)

      except:
        self._count = len(self.object_list)
    return self._count

  count = property(_get_count)


@admin.register(ChatMessage)
class ChatMessageAdmin(VersionAdmin):
  list_filter = ['room', "publish_on"]
  list_display = ['room', 'user', "publish_on"]
  search_fields = ['room__title', 'user__user__user__username', 'msg']
  readonly_fields = ['room', 'id', "user", "publish_on"]

  show_full_result_count = False
  paginator = CachingPaginator

  class Meta:
    model = ChatMessage