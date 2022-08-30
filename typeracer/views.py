from django.shortcuts import render
from django.views.generic import ListView, DetailView, View, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from .models import *
from judge.utils.views import TitleMixin
from django.utils.translation import gettext_lazy as _
from judge import event_poster as event

# Create your views here.

def updateProgress(request):
  if request.method == 'POST':
    user = request.POST.get('user')
    progress = request.POST.get('progress')
    contest = request.POST.get('contest')
    event.post('typocontest_%s' % contest, {
      'user': user,
      'progress': progress,
    })
  return JsonResponse({
    'result': 'success',
    'status': 200
  })

def getQuote(request, pk):
  room = TypoRoom.objects.get(pk=pk)
  return JsonResponse({
    'content': room.contest.data.data
  })


class Racer(TemplateView):
  template_name: str = 'typeracer/racer.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['user'] = self.object.user.user
    return context

  def dispatch(self, request, *args, **kwargs):
    index = request.GET.get('user')
    print(index)
    self.object = TypoResult.objects.get(pk=index)
    return super().dispatch(request, *args, **kwargs)
  

class TypoRoomList(TitleMixin, ListView):
  model = TypoRoom
  context_object_name = 'rooms'
  template_name: str = 'typeracer/listroom.html'
  title = _('Rooms')

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    if self.request.user.is_authenticated:
      context['current_room'] = self.request.user.profile.typoroom
    return context

class RoomMixin(object):
  slug_url_kwarg: str = 'pk'
  slug_field: str = 'pk'
  model = TypoRoom
  context_object_name = 'room'


class RoomDetail(TitleMixin, RoomMixin, DetailView):
  template_name: str = 'typeracer/room.html'

  def get_title(self):
    return self.object.name
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    participations = TypoResult.objects.filter(contest=self.object.contest)
    context['participations'] = [user.user.user for user in participations]
    return context
  

class JoinRoom(LoginRequiredMixin, RoomMixin, SingleObjectMixin, View):
  def post(self, request, *args, **kwargs):
    self.object = self.get_object()
    profile = request.profile
    contest = self.object.contest
    participation = TypoResult.objects.get_or_create(user=profile, contest=contest)
    participation[0].ranked = True
    participation[0].save()
    if participation[1]:
      event.post('typopartipation_%s' % contest.id, {
        'user': participation[0].id,
      })
    return HttpResponseRedirect(reverse('typeracer:room_detail', args=(self.object.id, )))