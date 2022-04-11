from django.db import models
from django.utils.translation import gettext_lazy as _

from judge.models import Profile


class ChatRoom(models.Model):
  organization = models.ForeignKey("judge.Organization", 
                                  verbose_name=_("Organization"), 
                                  on_delete=models.CASCADE, 
                                  related_name='chat_room',
                                  unique=True)
  title = models.CharField(_("Room title"), max_length=255)

  def __str__(self) -> str:
      return self.title

  @property
  def group_name(self):
    return _(self.organization.name + ' chat room')


class ChatParticipation(models.Model):
  room = models.ForeignKey(ChatRoom, verbose_name=_("Room chat"), on_delete=models.CASCADE)
  user = models.ForeignKey("judge.Profile", verbose_name=_("User"), on_delete=models.CASCADE)

  def __str__(self) -> str:
      return self.user.user.username


class ChatMessageManager(models.Manager):
  def by_room(self, room):
    qs = ChatMessage.objects.filter(room=room).order_by('-publish_on')
    return qs
  

class ChatMessage(models.Model):
  room = models.ForeignKey("chat.ChatRoom", verbose_name=_("Chat room"), default=None, on_delete=models.CASCADE)
  msg = models.TextField(_('Message'), blank=False, unique=False)
  user = models.ForeignKey("chat.ChatParticipation", verbose_name=_("User"), on_delete=models.CASCADE)
  publish_on = models.DateTimeField(_('Time publish'), auto_now_add=True)

  objects = ChatMessageManager()

  def __str__(self) -> str:
      return self.msg

  