from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from judge.jinja2.gravatar import gravatar
from judge.models.profile import Profile
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
    profile = Profile.objects.get(user__id=user_id)
    if not profile in organization:
      response = JsonResponse({'error': 'You not in this organization'})
      response.status_code = 403 
      return response
    room = organization.room
    user = ChatParticipation.objects.filter(user__user__pk=user_id, room=room).first()
    message = ChatMessage(room=user.room, msg=msg, user=user)
    message.save()
    data = {'org': org_id,}
    if event.real:
      event.post('messages_%s' % room.id,  data)
  return JsonResponse(data)


class NewMessageAjax(LoginRequiredMixin, DetailView):
  template_name = "organization/message-row.html"

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['msg'] = self.msg
    context['user'] = self.msg.user.user.user

  def get(self, request, *args, **kwargs):
    if 'id' not in request.GET or not request.GET['id'].isdigit():
      return HttpResponseBadRequest()
    if 'org' not in request.GET or not request.GET['org'].isdigit():
      return HttpResponseBadRequest()
    org_id = request.GET['org']
    organization = Organization.objects.get(pk=org_id)
    id = request.GET['id']
    self.msg = ChatMessage.objects.filter(room=organization.chat_room.all().first(), pk_gt=id).first()
    return super().get(request, *args, **kwargs)