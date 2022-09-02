from django.shortcuts import render
from django.views.generic import ListView, DetailView, View, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.urls import reverse
from .models import *
from judge.utils.views import TitleMixin, generic_message
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from judge import event_poster as event
from judge.models import Profile
import datetime
from random import randint

# Create your views here.

def get_random_contest(limit=300):
  data = TypoData.objects.all()
  i = randint(0, data.count() - 1)
  contest = TypoContest.objects.create(
    data = data[i],
    time_start = timezone.now() + timezone.timedelta(seconds=limit),
    time_join = timezone.now(),
    limit = 300
  )
  return contest

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

def get_rank(index):
  if index == 0:
    return '1st'
  if index == 1:
    return '2nd'
  if index == 2:
    return '3rd'
  return str(index + 1) + 'th'

def finishTypoContest(request):
  if request.method == 'POST':
    user = request.POST.get('user')
    contest = request.POST.get('contest')
    progress = request.POST.get('progress')
    speed = request.POST.get('speed')
    time = request.POST.get('time')
    contest_object = TypoContest.objects.get(pk=contest)
    rank = TypoResult.objects.filter(contest=contest_object, is_finish=True).count()
    result = TypoResult.objects.get(
      user=Profile.objects.get(user__pk=user),
      contest=contest_object,
    )
    result.speed = int(speed)
    result.time = int(time) / 1000
    result.progress = int(progress)
    result.order = rank + 1
    result.is_finish = True
    result.save()
    event.post('typocontestresult_%s' % contest, {
      'user': user,
      'ranking': get_rank(rank),
    })
  return JsonResponse({
    'result': 'success',
    'status': 200,
  })

def getQuote(request, pk):
  room: TypoRoom = TypoRoom.objects.get(pk=pk)
  contest: TypoContest = room.contest
  if contest._now >= contest.time_start:
    return JsonResponse({
      'content': room.contest.data.data
    })
  else:
    return JsonResponse({
      'content': ''
    })


class Racer(TemplateView):
  template_name: str = 'typeracer/racer.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['user'] = self.object.user.user
    return context

  def dispatch(self, request, *args, **kwargs):
    index = request.GET.get('user')
    self.object = TypoResult.objects.get(pk=index)
    return super().dispatch(request, *args, **kwargs)
  

class TypoRoomList(TitleMixin, ListView):
  model = TypoRoom
  context_object_name = 'rooms'
  template_name: str = 'typeracer/listroom.html'
  title = _('Rooms')

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    if self.request.user.is_authenticated and self.request.user.profile.typo_contest is not None:
      context['current_room'] = self.request.user.profile.typo_contest.room
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

  def get(self, request, *args, **kwargs):
    self.object = self.get_object()
    if not self.object.contest:
      raise Http404()
    result = TypoResult.objects.get(user=self.request.user.profile, contest=self.object.contest)
    if result.is_finish:
      return HttpResponseRedirect(reverse('typeracer:typo_ranking', args=(self.object.contest.id, )))
    return super().get(request, *args, **kwargs)


class Ranking(TitleMixin, DetailView):
  slug_url_kwarg: str = 'pk'
  slug_field: str = 'pk'
  model = TypoContest
  context_object_name = 'contest'
  template_name: str = 'typeracer/rank.html'
  title: str = 'Typo Contest'
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['ranks'] = TypoResult.objects.filter(contest=self.object, is_finish=True).order_by('-progress', '-speed', 'time')
    return context


class JoinRoom(LoginRequiredMixin, RoomMixin, SingleObjectMixin, View):
  def post(self, request, *args, **kwargs):
    self.object = self.get_object()
    profile: Profile = request.profile
    if profile.typo_contest is not None:
      return generic_message(request, 'Can\'t join room', 'You are in %s' % profile.typo_contest.room.name, 403)
    contest = self.object.contest
    room: TypoRoom = self.object
    if contest is None or (contest.ended and room.is_random):
      contest = get_random_contest(limit=15 if room.practice else 300)
      room.contest = contest
      room.save()
    if not contest.can_join:
      return generic_message(request, 'Can\'t join room', 'Contest is started', 403)
    user_count = TypoResult.objects.filter(contest=contest)
    if room.max_user > 0 and room.max_user == user_count:
      return generic_message(request, 'Can\'t join room', 'Room is full', 403)
    participation = TypoResult.objects.get_or_create(user=profile, contest=contest)
    if participation[1]:
      event.post('typopartipation_%s' % contest.id, {
        'user': participation[0].id,
      })
    elif participation[0].is_finish:
      return HttpResponseRedirect(reverse('typeracer:typo_ranking', args=(contest.id, )))
    return HttpResponseRedirect(reverse('typeracer:room_detail', args=(room.id, )))