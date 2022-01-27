from collections import defaultdict
from operator import attrgetter
import random, json

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe
from django.db.models import Q, Prefetch, F, Count
from django.utils.functional import cached_property

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _
from emath.models.exam import ExamParticipation

# from emath.models.exam import Exam
from judge.models import Profile
from judge.utils.infinite_paginator import InfinitePaginationMixin
from judge.utils.problems import _get_result_data
from judge.utils.raw_sql import join_sql_subquery, use_straight_join
from judge.utils.views import DiggPaginatorMixin, QueryStringSortMixin, TitleMixin
from emath.models import ExamProblem, Submission, Exam, Problem
from .forms import ProblemForm

def get_exam_problem(exam, profile):
    return ExamProblem.objects.filter(exam=exam)

def get_ans_problem(problem):
    ans = [problem.answer, problem.wrong_answer1, problem.wrong_answer2, problem.wrong_answer3]
    random.shuffle(ans)
    id = problem.id
    return [('%(id)s_%(ans)s' % {'id': id, 'ans': ans[i]}, ans[i]) for i in range(4)]

def judge(request):
    if request.is_ajax and request.method == 'POST':
        user_answer = request.POST.get("ans", None)
        user_id = request.POST.get("id", None)
        profile=Profile.objects.get(user__id=user_id)
        exam_id = request.POST.get("exam_id", None)
        exam = Exam.object.get(id=exam_id)
        time = timezone.now() - exam.start_time
        points = 0
        problems = get_exam_problem(exam, profile)
        for problem in problems:
            points += problem.points
        cnt = 0
        num_problem = 0
        case_all = 0
        for ans in user_answer:
            problem = ExamProblem.objects.filter(id=ans['id'])
            case_all += problem.points
            if problem.problem.answer == ans['ans']:
                cnt += problem.points
                num_problem += 1
        submission = Submission(
            user=profile,
            exam=exam,
            time=time,
            points=cnt,
            result='AC' if cnt == points else 'WA',
            case_points=cnt,
            case_total=case_all
        )
        submission.save()
        return JsonResponse({'url': reverse('exam_submission')}, status = 200)

    return JsonResponse({}, status = 400)


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


class ExamProblemView(LoginRequiredMixin, ExamMixin, TitleMixin, DetailView):
    context_object_name = 'exam'
    model = Exam
    template_name = 'tmatheng/exam.html'

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
                                   reverse('emath:exam_detail', args=[exam.id]),
                                   exam.name),
            'user': format_html('<a href="{0}">{1}</a>',
                                reverse('user_page', args=[self.request.user.username]),
                                name),
        })

    def get_context_data(self, **kwargs):
        content = super(ExamProblemView, self).get_context_data(**kwargs)
        self.problems = ExamProblem.objects.filter(exam=self.object).order_by('id')
        self.forms = []
        for problem in self.problems:
            self.forms.append(ProblemForm(get_ans_problem(problem.problem), prefix=str(problem.problem.id)))
        exam = self.object
        user = self.request.user
        profile = self.request.profile
        auth = user.is_authenticated
        exam_problem = self.problems if auth or user.profile.current_exam is None else None
        if not auth:
            raise Http404
        try:
            participation = ExamParticipation.objects.get(
                user=profile, exam=exam
            )
        except ExamParticipation.DoesNotExist:
            participation = ExamParticipation.objects.create(
                user=profile, exam=exam
            )
        participation.set_real_start()
        profile.current_exam = participation
        profile.save()
        
        exam._updating_stats_only = True
        exam.update_user_count()
        # problems = [problem for problem in exam_problem]
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
        content['exam_id'] = exam.id
        return content
    
    def post(self, request, *args, **kwargs):
        i = 0
        cnt = 0
        exam = None
        for item in request.POST:
            if i > 0:
                value = request.POST.get(item)
                x, y = value.split('_')
                problem = ExamProblem.objects.get(id=x)
                if exam is None:
                    exam = problem.exam
                if y == problem.problem.answer:
                    cnt += problem.points
            i += 1
        
        problems = ExamProblem.objects.filter(exam=exam)
        participation = ExamParticipation.objects.filter(user=self.request.profile, exam=exam).first()
        points = 0
        for problem in problems:
            points += problem.points

        time = timezone.now().timestamp() - participation.real_start.timestamp()
        sub = Submission(
            user=self.request.profile,
            exam=exam,
            time=time,
            points=cnt,
            result='AC' if cnt == points else 'WA',
            case_points=cnt,
            case_total=points
        )
        sub.save()
        return HttpResponseRedirect(reverse('emath:all_submissions'))


def filter_submissions_by_visible_exams(queryset, user):
    join_sql_subquery(
        queryset,
        subquery=str(Exam.get_visible_exams(user).only('id').query),
        params=[],
        join_fields=[('exam_id', 'id')],
        alias='visible_exams',
    )

def submission_related(queryset):
    return queryset.select_related('user__user', 'exam') \
        .only('id', 'user__user__username', 'user__display_rank', 'user__rating', 'exam__name',
              'exam__key', 'date', 'time',
              'points', 'result', 'case_points', 'case_total', 'exam') \
        .prefetch_related('exam__authors', 'exam__curators')


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
        for contest in self._get_queryset().exclude(end_time__lt=self._now):
            if contest.start_time > self._now:
                future.append(contest)
            else:
                present.append(contest)

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


def get_result_data(*args, **kwargs):
    if args:
        submissions = args[0]
        if kwargs:
            raise ValueError(_("Can't pass both queryset and keyword filters"))
    else:
        submissions = Submission.objects.filter(**kwargs) if kwargs is not None else Submission.objects
    raw = submissions.values('result').annotate(count=Count('result')).values_list('result', 'count')
    return _get_result_data(defaultdict(int, raw))


class SubmissionsListBase(DiggPaginatorMixin, TitleMixin, ListView):
    model = Submission
    paginate_by = 50
    show_problem = True
    title = _('All submissions')
    content_title = _('All submissions')
    tab = 'all_submissions_list'
    template_name = 'tmatheng/submission/list.html'
    context_object_name = 'submissions'
    first_page_href = None

    def get_result_data(self):
        return self._get_result_data()

    def _get_result_data(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return get_result_data(queryset.order_by())
        pass

    @cached_property
    def in_exam(self):
        return self.request.user.is_authenticated and self.request.profile.current_exam is not None
    
    @cached_property
    def exam(self):
        return self.request.profile.current_exam.exam

    def _get_queryset(self):
        queryset = Submission.objects.all()
        use_straight_join(queryset)
        queryset = submission_related(queryset.order_by('-id'))
        # if self.show_problem:
        #     queryset = queryset.prefetch_related(Prefetch('problem__translations',
        #                                                   queryset=ProblemTranslation.objects.filter(
        #                                                       language=self.request.LANGUAGE_CODE), to_attr='_trans'))
        if self.in_exam:
            queryset = queryset.filter(exam=self.exam)
            if not self.exam.can_see_full_scoreboard(self.request.user):
                queryset = queryset.filter(user=self.request.profile)
        else:
            queryset = queryset.select_related('exam').defer('exam__description')

            if not self.request.user.has_perm('judge.see_private_contest'):
                # Show submissions for any contest you can edit or visible scoreboard
                contest_queryset = Exam.objects.filter(Q(authors=self.request.profile) |
                                                          Q(curators=self.request.profile) |
                                                          Q(scoreboard_visibility=Exam.SCOREBOARD_VISIBLE) |
                                                          Q(end_time__lt=timezone.now())).distinct()
                queryset = queryset.filter(Q(user=self.request.profile) |
                                           Q(exam__in=contest_queryset) |
                                           Q(exam__isnull=True))

        # if self.selected_languages:
        #     queryset = queryset.filter(language__in=Language.objects.filter(key__in=self.selected_languages))
        # if self.selected_statuses:
        #     queryset = queryset.filter(result__in=self.selected_statuses)

        return queryset
    
    def get_queryset(self):
        queryset = self._get_queryset()
        if not self.in_exam:
            filter_submissions_by_visible_exams(queryset, self.request.user)

        return queryset

    def get_context_data(self, **kwargs):
        context = super(SubmissionsListBase, self).get_context_data(**kwargs)
        # authenticated = self.request.user.is_authenticated
        context['dynamic_update'] = False
        context['dynamic_contest_id'] = self.in_exam and self.exam.id
        context['show_problem'] = self.show_problem
        # context['completed_problem_ids'] = user_completed_ids(self.request.profile) if authenticated else []
        # context['editable_problem_ids'] = user_editable_ids(self.request.profile) if authenticated else []
        # context['tester_problem_ids'] = user_tester_ids(self.request.profile) if authenticated else []

        # context['all_languages'] = Language.objects.all().values_list('key', 'name')
        # context['selected_languages'] = self.selected_languages

        # context['all_statuses'] = self.get_searchable_status_codes()
        # context['selected_statuses'] = self.selected_statuses

        context['results_json'] = mark_safe(json.dumps(self.get_result_data()))
        context['results_colors_json'] = mark_safe(json.dumps(settings.DMOJ_STATS_SUBMISSION_RESULT_COLORS))

        context['page_suffix'] = suffix = ('?' + self.request.GET.urlencode()) if self.request.GET else ''
        context['first_page_href'] = (self.first_page_href or '.') + suffix
        # context['my_submissions_link'] = self.get_my_submissions_page()
        # context['all_submissions_link'] = self.get_all_submissions_page()
        context['tab'] = self.tab
        return context

    
class AllSubmissions(InfinitePaginationMixin, SubmissionsListBase):
    stats_update_interval = 3600

    @property
    def use_infinite_pagination(self):
        return not self.in_exam

    def get_context_data(self, **kwargs):
        context = super(AllSubmissions, self).get_context_data(**kwargs)
        context['dynamic_update'] = context['page_obj'].number == 1
        # context['last_msg'] = event.last()
        context['stats_update_interval'] = self.stats_update_interval
        return context