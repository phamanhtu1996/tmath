from collections import defaultdict
from operator import attrgetter
import random, json

from django.conf import settings
from django.db import ProgrammingError
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
from emath.models.problem import MathGroup
from judge.comments import CommentedDetailView

# from emath.models.exam import Exam
from judge.models import Profile
from judge.pdf_problems import HAS_PDF
from judge.utils.diggpaginator import DiggPaginator
from judge.utils.infinite_paginator import InfinitePaginationMixin
from judge.utils.problems import _get_result_data
from judge.utils.raw_sql import join_sql_subquery, use_straight_join
from judge.utils.strings import safe_float_or_none, safe_int_or_none
from judge.utils.views import DiggPaginatorMixin, QueryStringSortMixin, TitleMixin, generic_message
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


class ProblemMixin(object):
    context_object_name = 'problem'
    model = Problem
    slug_field = 'code'
    slug_url_kwarg = 'problem'

    def get_object(self, queryset=None):
        problem = super(ProblemMixin, self).get_object(queryset)
        if not self.request.user.is_authenticated:
            raise Http404
        else:
            return problem

class ProblemListMixin(object):
    def get_queryset(self):
        return Problem.get_visible_problems(self.request.user)
    

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

class ProblemList(QueryStringSortMixin, TitleMixin, ListView):
    model = Problem
    title = _('Problems')
    context_object_name = 'problems'
    template_name = 'tmatheng/problem/list.html'
    paginate_by = 50
    sql_sort = frozenset(('points', 'ac_rate', 'user_count', 'code'))
    manual_sort = frozenset(('name', 'group'))
    all_sorts = sql_sort | manual_sort
    default_desc = frozenset(('points', 'ac_rate', 'user_count'))
    default_sort = 'code'

    def get_paginator(self, queryset, per_page, orphans=0,
                      allow_empty_first_page=True, **kwargs):
        paginator = DiggPaginator(queryset, per_page, body=6, padding=2, orphans=orphans,
                                  allow_empty_first_page=allow_empty_first_page, **kwargs)
        # if not self.in_exam:
            # Get the number of pages and then add in this magic.
            # noinspection PyStatementEffect
        paginator.num_pages

        # queryset = queryset.add_i18n_name(self.request.LANGUAGE_CODE)
        sort_key = self.order.lstrip('-')
        if sort_key in self.sql_sort:
            queryset = queryset.order_by(self.order, 'id')
        elif sort_key == 'name':
            queryset = queryset.order_by(self.order.replace('name', 'i18n_name'), 'id')
        elif sort_key == 'group':
            queryset = queryset.order_by(self.order + '__name', 'id')
        # elif sort_key == 'solved':
        #     if self.request.user.is_authenticated:
        #         profile = self.request.profile
        #         solved = user_completed_ids(profile)
        #         attempted = user_attempted_ids(profile)

        #         def _solved_sort_order(problem):
        #             if problem.id in solved:
        #                 return 1
        #             if problem.id in attempted:
        #                 return 0
        #             return -1

        #         queryset = list(queryset)
        #         queryset.sort(key=_solved_sort_order, reverse=self.order.startswith('-'))
        # elif sort_key == 'type':
        #     if self.show_types:
        #         queryset = list(queryset)
        #         queryset.sort(key=lambda problem: problem.types_list[0] if problem.types_list else '',
        #                         reverse=self.order.startswith('-'))
        paginator.object_list = queryset
        return paginator

    @cached_property
    def profile(self):
        if not self.request.user.is_authenticated:
            return None
        return self.request.profile

    # def get_contest_queryset(self):
    #     queryset = self.profile.current_contest.contest.contest_problems.select_related('problem__group') \
    #         .defer('problem__description').order_by('problem__code') \
    #         .annotate(user_count=Count('submission__participation', distinct=True)) \
    #         .order_by('order')
    #     queryset = TranslatedProblemForeignKeyQuerySet.add_problem_i18n_name(queryset, 'i18n_name',
    #                                                                          self.request.LANGUAGE_CODE,
    #                                                                          'problem__name')
    #     return [{
    #         'id': p['problem_id'],
    #         'code': p['problem__code'],
    #         'name': p['problem__name'],
    #         'i18n_name': p['i18n_name'],
    #         'group': {'full_name': p['problem__group__full_name']},
    #         'points': p['points'],
    #         'partial': p['partial'],
    #         'user_count': p['user_count'],
    #     } for p in queryset.values('problem_id', 'problem__code', 'problem__name', 'i18n_name',
    #                                'problem__group__full_name', 'points', 'partial', 'user_count')]

    def get_normal_queryset(self):
        filter = Q(is_public=True)
        if self.profile is not None:
            filter |= Q(authors=self.profile)
            # filter |= Q(curators=self.profile)
            # filter |= Q(testers=self.profile)
        queryset = Problem.objects.filter(filter).select_related('group').defer('description')
        if not self.request.user.has_perm('see_organization_problem'):
            filter = Q(is_organization_private=False)
            if self.profile is not None:
                filter |= Q(organizations__in=self.profile.organizations.all())
            queryset = queryset.filter(filter)
        # if self.profile is not None and self.hide_solved:
        #     queryset = queryset.exclude(id__in=Submission.objects.filter(user=self.profile, points=F('problem__points'))
        #                                 .values_list('problem__id', flat=True))
        # if self.show_types:
        #     queryset = queryset.prefetch_related('types')
        if self.category is not None:
            queryset = queryset.filter(group__id=self.category)
        # if self.selected_types:
        #     queryset = queryset.filter(types__in=self.selected_types)
        if 'search' in self.request.GET:
            self.search_query = query = ' '.join(self.request.GET.getlist('search')).strip()
            if query:
                if settings.ENABLE_FTS and self.full_text:
                    queryset = queryset.search(query, queryset.BOOLEAN).extra(order_by=['-relevance'])
                else:
                    queryset = queryset.filter(
                        Q(code__icontains=query) | Q(name__icontains=query) |
                        Q(translations__name__icontains=query, translations__language=self.request.LANGUAGE_CODE))
        self.prepoint_queryset = queryset
        # if self.point_start is not None:
        #     queryset = queryset.filter(points__gte=self.point_start)
        # if self.point_end is not None:
        #     queryset = queryset.filter(points__lte=self.point_end)
        return queryset.distinct()

    def get_queryset(self):
        return self.get_normal_queryset()

    def get_context_data(self, **kwargs):
        context = super(ProblemList, self).get_context_data(**kwargs)
        # context['hide_solved'] = 0 if self.in_contest else int(self.hide_solved)
        # context['show_types'] = 0 if self.in_contest else int(self.show_types)
        # context['full_text'] = int(self.full_text)
        context['category'] = self.category
        context['categories'] = MathGroup.objects.all()
        # if self.show_types:
        #     context['selected_types'] = self.selected_types
        #     context['problem_types'] = ProblemType.objects.all()
        context['has_fts'] = settings.ENABLE_FTS
        context['search_query'] = self.search_query
        # context['completed_problem_ids'] = self.get_completed_problems()
        # context['attempted_problems'] = self.get_attempted_problems()

        context.update(self.get_sort_paginate_context())
        # if not self.in_contest:
        context.update(self.get_sort_context())
        #     context['hot_problems'] = hot_problems(timedelta(days=1), settings.DMOJ_PROBLEM_HOT_PROBLEM_COUNT)
        #     context['point_start'], context['point_end'], context['point_values'] = self.get_noui_slider_points()
        # else:
        #     context['hot_problems'] = None
        #     context['point_start'], context['point_end'], context['point_values'] = 0, 0, {}
        #     context['hide_contest_scoreboard'] = self.contest.scoreboard_visibility in \
        #         (self.contest.SCOREBOARD_AFTER_CONTEST, self.contest.SCOREBOARD_AFTER_PARTICIPATION)
        return context

    # def get_noui_slider_points(self):
    #     points = sorted(self.prepoint_queryset.values_list('points', flat=True).distinct())
    #     if not points:
    #         return 0, 0, {}
    #     if len(points) == 1:
    #         return points[0], points[0], {
    #             'min': points[0] - 1,
    #             'max': points[0] + 1,
    #         }

    #     start, end = points[0], points[-1]
    #     if self.point_start is not None:
    #         start = self.point_start
    #     if self.point_end is not None:
    #         end = self.point_end
    #     points_map = {0.0: 'min', 1.0: 'max'}
    #     size = len(points) - 1
    #     return start, end, {points_map.get(i / size, '%.2f%%' % (100 * i / size,)): j for i, j in enumerate(points)}

    def GET_with_session(self, request, key):
        if not request.GET:
            return request.session.get(key, False)
        return request.GET.get(key, None) == '1'

    def setup_problem_list(self, request):
        # self.hide_solved = self.GET_with_session(request, 'hide_solved')
        # self.show_types = self.GET_with_session(request, 'show_types')
        # self.full_text = self.GET_with_session(request, 'full_text')

        self.search_query = None
        self.category = None
        # self.selected_types = []

        # This actually copies into the instance dictionary...
        self.all_sorts = set(self.all_sorts)
        # if not self.show_types:
        #     self.all_sorts.discard('type')

        self.category = safe_int_or_none(request.GET.get('category'))
        # if 'type' in request.GET:
        #     try:
        #         self.selected_types = list(map(int, request.GET.getlist('type')))
        #     except ValueError:
        #         pass

        # self.point_start = safe_float_or_none(request.GET.get('point_start'))
        # self.point_end = safe_float_or_none(request.GET.get('point_end'))

    def get(self, request, *args, **kwargs):
        self.setup_problem_list(request)

        try:
            return super(ProblemList, self).get(request, *args, **kwargs)
        except ProgrammingError as e:
            return generic_message(request, 'FTS syntax error', e.args[1], status=400)

    # def post(self, request, *args, **kwargs):
    #     to_update = ('hide_solved', 'show_types', 'full_text')
    #     for key in to_update:
    #         if key in request.GET:
    #             val = request.GET.get(key) == '1'
    #             request.session[key] = val
    #         else:
    #             request.session.pop(key, None)
    #     return HttpResponseRedirect(request.get_full_path())


class ProblemDetail(ProblemMixin, CommentedDetailView):
    context_object_name = 'problem'
    template_name = 'tmatheng/problem/problem.html'

    def get_comment_page(self):
        return 'p:%s' % self.object.code

    def get_context_data(self, **kwargs):
        context = super(ProblemDetail, self).get_context_data(**kwargs)
        user = self.request.user
        authed = user.is_authenticated
        # context['has_submissions'] = authed and Submission.objects.filter(user=user.profile,
        #                                                                   problem=self.object).exists()
        # contest_problem = (None if not authed or user.profile.current_contest is None else
        #                    get_contest_problem(self.object, user.profile))
        # context['contest_problem'] = contest_problem
        # if contest_problem:
        #     clarifications = self.object.clarifications
        #     context['has_clarifications'] = clarifications.count() > 0
        #     context['clarifications'] = clarifications.order_by('-date')
        #     context['submission_limit'] = contest_problem.max_submissions
        #     if contest_problem.max_submissions:
        #         context['submissions_left'] = max(contest_problem.max_submissions -
        #                                           get_contest_submission_count(self.object, user.profile,
        #                                                                        user.profile.current_contest.virtual), 0)

        # context['available_judges'] = Judge.objects.filter(online=True, problems=self.object)
        # context['show_languages'] = self.object.allowed_languages.count() != Language.objects.count()
        context['has_pdf_render'] = HAS_PDF
        # context['completed_problem_ids'] = self.get_completed_problems()
        # context['attempted_problems'] = self.get_attempted_problems()

        can_edit = self.object.is_editable_by(user)
        context['can_edit_problem'] = can_edit
        # if user.is_authenticated:
        #     tickets = self.object.tickets
        #     if not can_edit:
        #         tickets = tickets.filter(own_ticket_filter(user.profile.id))
        #     context['has_tickets'] = tickets.exists()
        #     context['num_open_tickets'] = tickets.filter(is_open=True).values('id').distinct().count()

        # try:
        #     context['editorial'] = Solution.objects.get(problem=self.object)
        # except ObjectDoesNotExist:
        #     pass
        # try:
        #     translation = self.object.translations.get(language=self.request.LANGUAGE_CODE)
        # except ProblemTranslation.DoesNotExist:
        context['title'] = self.object.name
        context['language'] = settings.LANGUAGE_CODE
        context['description'] = self.object.description
        context['translated'] = False
        # else:
        #     context['title'] = translation.name
        #     context['language'] = self.request.LANGUAGE_CODE
        #     context['description'] = translation.description
        #     context['translated'] = True

        # if not self.object.og_image or not self.object.summary:
        #     metadata = generate_opengraph('generated-meta-problem:%s:%d' % (context['language'], self.object.id),
        #                                   context['description'], 'problem')
        # context['meta_description'] = self.object.summary or metadata[0]
        # context['og_image'] = self.object.og_image or metadata[1]
        return context