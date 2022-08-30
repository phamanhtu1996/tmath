import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now


# Create your models here.

DIFFICULT = (
    ('newbie', _('Newbie')),
    ('amateur', _('Amateur')),
    ('expert', _('Expert')),
    ('master', _('Master')),
    ('gmaster', _('Grand Master')),
  )


class TypoData(models.Model):
  name = models.CharField(_('name'), max_length=255, unique=True)
  data = models.TextField(blank=False)
  difficult = models.CharField(_('difficult'), max_length=10, choices=DIFFICULT, default='newbie')

  def __str__(self) -> str:
    return self.name


class TypoContest(models.Model):
  data = models.ForeignKey(TypoData, related_name='contest', null=True, on_delete=models.SET_NULL)
  time_start = models.DateTimeField(_('time start'), help_text=_('time to start racing'))
  time_join = models.DateTimeField(_('time join'), help_text=_('time to participation join'))
  time_end_join = models.DateTimeField(_('time end join'), help_text=_('time end join'))

  @property
  def time_until_start(self):
    current = now()
    if current >= self.time_start:
      return 0
    return (self.time_start - current).total_seconds()


class TypoResult(models.Model):
  user = models.ForeignKey('judge.Profile', verbose_name=_('user'), related_name='typos', on_delete=models.CASCADE)
  time = models.TimeField(_('time'), default=datetime.time(0, 0))
  speed = models.FloatField(_('speed'), default=0)
  ranked = models.BooleanField(_('is ranking'), default=False)
  contest = models.ForeignKey("typeracer.TypoContest", verbose_name=_("contest"), related_name='participations', null=True, blank=True, on_delete=models.CASCADE)

  class Meta:
    unique_together = ('user', 'contest')
    verbose_name = _('typo result')
    verbose_name_plural = _('typo results')


class TypoProfile(models.Model):
  max_speed = models.FloatField(_('max speed'), default=0)
  date = models.DateTimeField(_('date created'))
  level = models.CharField(_('level'), max_length=10, choices=DIFFICULT, default='newbie')


class TypoRoom(models.Model):
  name = models.CharField(_("name"), max_length=255, default='')
  contest = models.ForeignKey(TypoContest, related_name='room', null=True, blank=True, on_delete=models.SET_NULL)
  access_code = models.CharField(_('access code'), max_length=100, blank=True, default='')

  def __str__(self) -> str:
    return self.name

  @property
  def user_count(self):
    return TypoResult.objects.filter(contest=self.contest).count()