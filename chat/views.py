from django.http import JsonResponse

from judge.jinja2.gravatar import gravatar
from .models import ChatMessage, ChatParticipation
from judge.models import Organization

from judge import event_poster as event

# Create your views here.

def make_message(request): 
  if request.method == 'POST':
    user_id = request.POST.get('user')
    org_id = request.POST.get('org')
    msg = request.POST.get('msg')
    organization = Organization.objects.get(pk=org_id)
    room = organization.chat_room.all().first()
    user = ChatParticipation.objects.filter(user__user__pk=user_id, room=room).first()
    message = ChatMessage(room=user.room, msg=msg, user=user)
    message.save()
    # event.post('message', { 
    #                         'org': org_id,
    #                         'user': user_id, 
    #                         'msg': msg,
    #                         'time': message.publish_on
    #                       })
  
  return JsonResponse({
    'user': user.user.user.username,
    'msg': msg,
    'publish': message.publish_on,
    'avatar': gravatar(user.user, 200),
    'class': user.user.css_class,
    'name': user.user.name if user.user.name is user.user.name else user.user.user.username
  })