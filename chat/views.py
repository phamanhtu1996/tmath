from django.http import JsonResponse
from django.shortcuts import render
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
    event.post('message', { 
                            'org': org_id,
                            'user': user_id, 
                            'msg': msg,
                            'time': message.publish_on
                          })
  
  return JsonResponse({'status': 200})