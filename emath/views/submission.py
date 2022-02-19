import json
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from django.utils.functional import cached_property
from django.db.models import Q, Count
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic.list import ListView

from judge.utils.infinite_paginator import InfinitePaginationMixin
from judge.utils.problems import _get_result_data
from judge.utils.raw_sql import join_sql_subquery, use_straight_join
from judge.utils.views import DiggPaginatorMixin, TitleMixin

from emath.models import Submission, Exam

def filter_submissions_by_visible_exams(queryset, user):
    join_sql_subquery(
        queryset,
        subquery=str(Exam.get_visible_exams(user).only('id').query),
        params=[],
        join_fields=[('exam_id', 'id')],
        alias='visible_exams',
    )

def submission_related(queryset):
    return queryset.select_related('user__user', 'exam__exam') \
        .only('id', 'user__user__username', 'user__display_rank', 'user__rating', 'exam__exam__name',
              'exam__exam__key', 'date', 'time',
              'points', 'result', 'case_points', 'case_total', 'exam__exam') \
        .prefetch_related('exam__exam__authors', 'exam__exam__curators')


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
            queryset = queryset.filter(exam__exam=self.exam)
            if not self.exam.can_see_full_scoreboard(self.request.user):
                queryset = queryset.filter(user=self.request.profile)
        else:
            # queryset = queryset.select_related('exam').defer('exam__description')

            if not self.request.user.has_perm('exam.see_private_exam'):
                # Show submissions for any contest you can edit or visible scoreboard
                contest_queryset = Exam.objects.filter(Q(authors=self.request.profile) |
                                                          Q(curators=self.request.profile) |
                                                          Q(scoreboard_visibility=Exam.SCOREBOARD_VISIBLE) |
                                                          Q(end_time__lt=timezone.now())).distinct()
                queryset = queryset.filter(Q(user=self.request.profile) |
                                           Q(exam__exam__in=contest_queryset) |
                                           Q(exam__exam__isnull=True))

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

