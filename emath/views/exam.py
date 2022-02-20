from collections import namedtuple
from functools import partial
from itertools import chain
from operator import attrgetter
import random
from django import forms
from django.conf import settings

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, render
from django.views.generic import DetailView, ListView
from django.views.generic.detail import BaseDetailView
from django.db.models import Case, Count, F, FloatField, IntegerField, Max, Min, Q, Sum, Value, When
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse, Http404, HttpResponseRedirect
from django.urls import reverse
from emath.models.problem import Problem
from emath.models.submission import SubmissionProblem

from judge.models import Profile
from judge.utils.opengraph import generate_opengraph
from judge.utils.views import TitleMixin, QueryStringSortMixin, DiggPaginatorMixin, generic_message
from judge.comments import CommentedDetailView
from emath.forms import ProblemForm
from emath.models import Exam, ExamProblem, ExamParticipation, ExamSubmission, Submission

def get_exam_problem(exam, profile):
    return ExamProblem.objects.filter(exam=exam)

def get_ans_problem(problem):
    ans = [problem.answer, problem.wrong_answer1, problem.wrong_answer2, problem.wrong_answer3]
    random.shuffle(ans)
    id = problem.id
    return [(ans[i], ans[i]) for i in range(4)]


class PrivateExamError(Exception):
    def __init__(self, name, is_private, is_organization_private, orgs):
        self.name = name
        self.is_private = is_private
        self.is_organization_private = is_organization_private
        self.orgs = orgs


class ExamMixin(object):
    context_object_name = 'exam'
    model = Exam
    slug_field = 'key'
    slug_url_kwarg = 'exam'

    @cached_property
    def is_editor(self):
        if not self.request.user.is_authenticated:
            return False
        return self.request.profile.id in self.object.editor_ids

    @cached_property
    def is_tester(self):
        if not self.request.user.is_authenticated:
            return False
        return self.request.profile.id in self.object.tester_ids

    @cached_property
    def can_edit(self):
        return self.object.is_editable_by(self.request.user)

    def get_object(self, queryset=None):
        exam = super(ExamMixin, self).get_object(queryset)
        try:
            exam.access_check(self.request.user)
        except Exam.PrivateExam:
            raise PrivateExamError(exam.name, exam.is_private, exam.is_organization_private,
                                   exam.organizations.all())
        except Exam.Inaccessible:
            raise Http404
        else:
            return exam
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            try:
                context['live_participation'] = (
                    self.request.profile.exam_history.get(
                        exam=self.object,
                        virtual=ExamParticipation.LIVE,
                    )
                )
            except ExamParticipation.DoesNotExist:
                context['live_participation'] = None
                context['has_joined'] = False
            else:
                context['has_joined'] = True
        else:
            context['live_participation'] = None
            context['has_joined'] = False

        context['now'] = timezone.now()
        context['is_editor'] = self.is_editor
        context['is_tester'] = self.is_tester
        context['can_edit'] = self.can_edit

        if not self.object.og_image or not self.object.summary:
            metadata = generate_opengraph('generated-meta-exam:%d' % self.object.id,
                                          self.object.description, 'exam')
        context['meta_description'] = self.object.summary or metadata[0]
        context['og_image'] = self.object.og_image or metadata[1]
        context['has_moss_api_key'] = settings.MOSS_API_KEY is not None
        context['logo_override_image'] = self.object.logo_override_image
        if not context['logo_override_image'] and self.object.organizations.count() == 1:
            context['logo_override_image'] = self.object.organizations.first().logo_override_image

        return context
    

class ExamProblemView(LoginRequiredMixin, ExamMixin, TitleMixin, DetailView):
    context_object_name = 'exam'
    model = Exam
    template_name = 'tmatheng/exam-problem.html'

    def __init__(self, *args, **kwargs):
        super(ExamProblemView, self).__init__(*args, **kwargs)
        self.problems = []

    def get_title(self):
        user = self.request.user
        name = user.profile.name if user.profile.name else user.username
        return "Exam %(exam)s by  %(user)s" % {
            'exam': self.object.name,
            'user': name
        }
    
    def get_content_title(self):
        exam = self.object
        name = self.request.user.profile.name if self.request.user.profile.name else self.request.user.username
        return mark_safe(escape(_('Exam %(exam)s by %(user)s')) % {
            'exam': format_html('<a href="{0}">{1}</a>',
                                   reverse('emath:exam_detail', args=[exam.key]),
                                   exam.name),
            'user': format_html('<a href="{0}">{1}</a>',
                                reverse('user_page', args=[self.request.user.username]),
                                name),
        })

    def get_context_data(self, **kwargs):
        content = super(ExamProblemView, self).get_context_data(**kwargs)
        self.problems = list(ExamProblem.objects.filter(exam=self.object).order_by('id'))
        self.forms = []
        user = self.request.user
        profile = self.request.profile
        exam = self.object
        auth = user.is_authenticated and (profile.current_exam is not None and profile.current_exam.exam == exam)
        content['has_joined'] = auth
        auth = auth or self.is_editor or self.is_tester
        if not auth:
            raise Http404
        content['has_submissions'] = auth and ExamSubmission.objects.filter(exam=exam, participation__user=profile).exists()
        random.shuffle(self.problems)
        for problem in self.problems:
            # print(problem.problem.description)
            self.forms.append(ProblemForm(get_ans_problem(problem.problem), prefix=str(problem.id)))
        exam_problem = self.problems if auth else None
        
        i = 0
        content['data'] = []
        for problem in exam_problem:
            content['data'].append({
                'problem': problem, 
                'form': self.forms[i],
            })
            i += 1
        # content['problems'] = exam_problem
        content['forms'] = self.forms
        content['user_id'] = user.id
        return content
    
    def post(self, request, *args, **kwargs):
        user = self.request.user
        auth = user.is_authenticated
        if not auth:
            raise Http404
        exam_id = request.POST['exam']
        exam = Exam.objects.get(id=exam_id)
        profile = self.request.profile
        LIVE = ExamParticipation.LIVE
        SPECTATE = ExamParticipation.SPECTATE
        spectate = (profile in exam.editor_ids) or (profile in exam.tester_ids)
        if not exam.ended:
            participation = ExamParticipation.objects.get(
                user=self.request.profile, 
                exam=exam, 
                virtual=SPECTATE if spectate else LIVE)
        else:
            participation = ExamParticipation.objects.filter(
                user=self.request.profile, 
                exam=exam, 
                virtual__gt=LIVE
            ).order_by('-virtual').first()

        # print(participation.virtual)

        time = timezone.now().timestamp() - participation.real_start.timestamp()
        submission = Submission.objects.create(
            user=self.request.profile,
            time=time,
            result='AB'
        )
        problems = ExamProblem.objects.filter(exam=exam)
        cnt = 0
        for problem in problems:
            key = str(problem.id) + '-ans'
            answer = self.request.POST[key]
            check = answer == problem.problem.answer
            print(answer, problem.problem.answer)
            if check:
                cnt += 1
            SubmissionProblem.objects.create(
                submission=submission,
                problem=problem,
                output=answer,
                result=check,
                points=1 if check else 0
            )
        if participation.virtual > SPECTATE:
            esub = ExamSubmission(
                submission=submission,
                exam=exam,
                participation=participation,
                points=cnt
            )
            esub.save()
            esub.update_exam()

        total = len(problems)

        submission.points = cnt
        submission.result = 'AC' if cnt == total else 'WA'
        submission.case_points = cnt
        submission.case_total = total
        submission.save()

        return HttpResponseRedirect(reverse('emath:all_submissions'))


class ExamDetail(ExamMixin, TitleMixin, CommentedDetailView):
    context_object_name = 'exam'
    model = Exam
    template_name = 'tmatheng/exam.html'

    def get_comment_page(self):
        return 'c:%s' % self.object.key

    def get_title(self):
        return self.object.name


class ExamListMixin(object):
    def get_queryset(self):
        return Exam.get_visible_exams(self.request.user)


class ExamList(QueryStringSortMixin, DiggPaginatorMixin, TitleMixin, ExamListMixin, ListView):
    model = Exam
    paginate_by = 20
    template_name = 'tmatheng/list.html'
    title = _('Exams')
    context_object_name = 'past_exams'
    all_sorts = frozenset(('name', 'user_count', 'start_time'))
    default_desc = frozenset(('name', 'user_count'))
    default_sort = '-start_time'

    @cached_property
    def _now(self):
        return timezone.now()

    def _get_queryset(self):
        return super().get_queryset().prefetch_related('organizations', 'authors', 'curators', 'testers')

    def get_queryset(self):
        return self._get_queryset().order_by(self.order, 'key').filter(end_time__lt=self._now)

    def get_context_data(self, **kwargs):
        context = super(ExamList, self).get_context_data(**kwargs)
        present, active, future = [], [], []
        for exam in self._get_queryset().exclude(end_time__lt=self._now):
            if exam.start_time > self._now:
                future.append(exam)
            else:
                present.append(exam)

        if self.request.user.is_authenticated:
            for participation in ExamParticipation.objects.filter(virtual=0, user=self.request.profile,
                                                                     exam_id__in=present) \
                    .select_related('exam') \
                    .prefetch_related('exam__authors', 'exam__curators', 'exam__testers') \
                    .annotate(key=F('exam__key')):
                if not participation.ended:
                    active.append(participation)
                    present.remove(participation.exam)

        active.sort(key=attrgetter('end_time', 'key'))
        present.sort(key=attrgetter('end_time', 'key'))
        future.sort(key=attrgetter('start_time'))
        context['active_participations'] = active
        context['current_exams'] = present
        context['future_exams'] = future
        context['now'] = self._now
        context['first_page_href'] = '.'
        context['page_suffix'] = '#past-exams'
        context.update(self.get_sort_context())
        context.update(self.get_sort_paginate_context())
        return context

def ranker(iterable, key=attrgetter('points'), rank=0):
    delta = 1
    last = None
    for item in iterable:
        new = key(item)
        if new != last:
            rank += delta
            delta = 0
        delta += 1
        yield rank, item
        last = key(item)

ExamRankingProfile = namedtuple(
    'ExamRankingProfile',
    'id user css_class username points organization participation '
    'problem_cell result_cell cumtime tiebreaker'
)

def make_exam_ranking_profile(exam, participation, exam_problems):

    def display_user_problem(exam_problem):
        try:
            return exam.format.display_user_problem(participation, exam_problem)
        except (KeyError, TypeError, ValueError):
            return mark_safe('<td>???</td>')

    user = participation.user

    return ExamRankingProfile(
        id=user.id,
        user=user.user,
        css_class=user.css_class,
        username=user.username,
        points=participation.score,
        organization=user.organization,
        participation=participation,
        problem_cell=[display_user_problem(problem) for problem in exam_problems],
        cumtime=participation.cumtime,
        tiebreaker=participation.tiebreaker,
        result_cell=exam.format.display_participation_result(participation),
    )
    
def base_exam_ranking_list(exam, problems, queryset):
    return [make_exam_ranking_profile(exam, participation, problems) for participation in 
            queryset.select_related('user__user').defer('user__about', 'user__organizations__about')]

def exam_ranking_list(exam, problems):
    return base_exam_ranking_list(exam, problems, exam.users.filter(virtual=0)
                                .prefetch_related('user__organizations')
                                .order_by('is_disqualified', '-score', 'cumtime', 'tiebreaker'))

def get_exam_ranking_list(request, exam, participation=None, ranking_list=exam_ranking_list,
                          show_current_virtual=True, ranker=ranker):
    problems = list(exam.exam_problems.select_related('problem').defer('problem__description').order_by('order'))

    users = ranker(ranking_list(exam, problems), key=attrgetter('points', 'cumtime', 'tiebreaker'))

    if show_current_virtual:
        if participation is None and request.user.is_authenticated:
            participation = request.profile.current_exam
            if participation is None or participation.exam_id != exam.id:
                participation = None
        if participation is not None and participation.virtual:
            users = chain([('-', make_exam_ranking_profile(exam, participation, problems))], users)
    
    return users, problems


class ExamRankingBase(ExamMixin, TitleMixin, DetailView):
    template_name = "tmatheng/ranking.html"
    tab = None

    def get_title(self):
        raise NotImplementedError()

    def get_content_title(self):
        return self.object.name

    def get_ranking_list(self):
        raise NotImplementedError()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not self.object.can_see_own_scoreboard(self.request.user):
            raise Http404()

        users, problems = self.get_ranking_list()
        context['users'] = users    
        context['problems'] = problems
        context['tab'] = self.tab
        return context


class ExamRanking(ExamRankingBase):
    tab = 'ranking'

    def get_title(self):
        return _('%s Rankings') % self.object.name
    
    def get_ranking_list(self):
        if not self.object.can_see_full_scoreboard(self.request.user):
            queryset = self.object.users.filter(user=self.request.profile, virtual=ExamParticipation.LIVE)
            return get_exam_ranking_list(
                self.request, self.object,
                ranking_list=partial(base_exam_ranking_list, queryset=queryset),
                ranker=lambda users, key: ((_('???'), user) for user in users)
            )
        return get_exam_ranking_list(self.request, self.object)
    

class ExamParticipationList(LoginRequiredMixin, ExamRankingBase):
    tab = 'participation'

    def get_title(self):
        if self.profile == self.request.profile:
            return _('Your participation in %s') % self.object.name
        return _("%s's participation in %s") % (self.profile.username, self.object.name)

    def get_ranking_list(self):
        if not self.object.can_see_full_scoreboard(self.request.user) and self.profile != self.request.profile:
            raise Http404()

        queryset = self.object.users.filter(user=self.profile, virtual__gte=0).order_by('-virtual')
        live_link = format_html('<a href="{2}#!{1}">{0}</a>', _('Live'), self.profile.username,
                                reverse('exam_ranking', args=[self.object.key]))

        return get_exam_ranking_list(
            self.request, self.object, show_current_virtual=False,
            ranking_list=partial(base_exam_ranking_list, queryset=queryset),
            ranker=lambda users, key: ((user.participation.virtual or live_link, user) for user in users))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['has_rating'] = False
        context['now'] = timezone.now()
        context['rank_header'] = _('Participation')
        return context

    def get(self, request, *args, **kwargs):
        if 'user' in kwargs:
            self.profile = get_object_or_404(Profile, user__username=kwargs['user'])
        else:
            self.profile = self.request.profile
        return super().get(request, *args, **kwargs)


class ExamAccessDenied(Exception):
    pass


class ExamAccessCodeForm(forms.Form):
    access_code = forms.CharField(max_length=255)

    def __init__(self, *args, **kwargs):
        super(ExamAccessCodeForm, self).__init__(*args, **kwargs)
        self.fields['access_code'].widget.attrs.update({'autocomplete': 'off'})



class ExamJoin(LoginRequiredMixin, ExamMixin, BaseDetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.ask_for_access_code()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.request.profile.emath:
            raise ExamAccessDenied()
        try:
            return self.join_exam(request)
        except ExamAccessDenied:
            if request.POST.get('access_code'):
                return self.ask_for_access_code(ExamAccessCodeForm(request.POST))
            else:
                return HttpResponseRedirect(request.path)

    def join_exam(self, request, access_code=None):
        exam = self.object

        if not exam.can_join and not (self.is_editor or self.is_tester):
            return generic_message(request, _('exam not ongoing'),
                                   _('"%s" is not currently ongoing.') % exam.name)

        profile = request.profile
        if profile.current_exam is not None:
            return generic_message(request, _('Already in exam'),
                                   _('You are already in a exam: "%s".') % profile.current_exam.exam.name)

        if not request.user.is_superuser and exam.banned_users.filter(id=profile.id).exists():
            return generic_message(request, _('Banned from joining'),
                                   _('You have been declared persona non grata for this exam. '
                                     'You are permanently barred from joining this exam.'))

        requires_access_code = (not self.can_edit and exam.access_code and access_code != exam.access_code)
        if exam.ended:
            if requires_access_code:
                raise ExamAccessDenied()

            while True:
                virtual_id = max((ExamParticipation.objects.filter(exam=exam, user=profile)
                                  .aggregate(virtual_id=Max('virtual'))['virtual_id'] or 0) + 1, 1)
                try:
                    participation = ExamParticipation.objects.create(
                        exam=exam, user=profile, virtual=virtual_id,
                        real_start=timezone.now(),
                    )
                # There is obviously a race condition here, so we keep trying until we win the race.
                except IntegrityError:
                    pass
                else:
                    break
        else:
            SPECTATE = ExamParticipation.SPECTATE
            LIVE = ExamParticipation.LIVE
            try:
                participation = ExamParticipation.objects.get(
                    exam=exam, user=profile, virtual=(SPECTATE if self.is_editor or self.is_tester else LIVE),
                )
            except ExamParticipation.DoesNotExist:
                if requires_access_code:
                    raise ExamAccessDenied()

                participation = ExamParticipation.objects.create(
                    exam=exam, user=profile, virtual=(SPECTATE if self.is_editor or self.is_tester else LIVE),
                    real_start=timezone.now(),
                )
            else:
                if participation.ended:
                    participation = ExamParticipation.objects.get_or_create(
                        exam=exam, user=profile, virtual=SPECTATE,
                        defaults={'real_start': timezone.now()},
                    )[0]

        profile.current_exam = participation
        profile.save()
        exam._updating_stats_only = True
        exam.update_user_count()
        return HttpResponseRedirect(reverse('emath:exam_detail', args=(exam.key,)))

    def ask_for_access_code(self, form=None):
        exam = self.object
        wrong_code = False
        if form:
            if form.is_valid():
                if form.cleaned_data['access_code'] == exam.access_code:
                    return self.join_exam(self.request, form.cleaned_data['access_code'])
                wrong_code = True
        else:
            form = ExamAccessCodeForm()
        return render(self.request, 'exam/access_code.html', {
            'form': form, 'wrong_code': wrong_code,
            'title': _('Enter access code for "%s"') % exam.name,
        })


class ExamLeave(LoginRequiredMixin, ExamMixin, BaseDetailView):
    def post(self, request, *args, **kwargs):
        exam = self.get_object()

        profile = request.profile
        if profile.current_exam is None or profile.current_exam.exam_id != exam.id:
            return generic_message(request, _('No such exam'),
                                   _('You are not in exam "%s".') % exam.key, 404)

        profile.remove_exam()
        return HttpResponseRedirect(reverse('emath:exam_detail', args=(exam.key,)))


ExamDay = namedtuple('ExamDay', 'date weekday is_pad is_today starts ends oneday')
