import json
from collections import defaultdict

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist, PermissionDenied
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.utils.functional import cached_property
from django.db.models import Q, Count
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.generic.list import ListView
from judge.models.profile import Profile

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
        join_fields=[('exam__exam_id', 'id')],
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
    paginate_by = 20
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
        # if not self.in_exam:
        #     filter_submissions_by_visible_exams(queryset, self.request.user)

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
        return True

    def get_context_data(self, **kwargs):
        context = super(AllSubmissions, self).get_context_data(**kwargs)
        context['dynamic_update'] = context['page_obj'].number == 1
        # context['last_msg'] = event.last()
        context['stats_update_interval'] = self.stats_update_interval
        return context


class ExamSubmissionsBase(SubmissionsListBase):
    show_problem = False
    dynamic_update = False

    def get_queryset(self):
        # if self.in_exam and not self.exam.exam_problems.filter(problem_id=self.problem.id).exists():
        #     raise Http404()
        return super(ExamSubmissionsBase, self)._get_queryset().filter(exam__exam_id=self.exam.id)

    def get_title(self):
        return _('All submissions for %s') % self.exam_name

    def get_content_title(self):
        return format_html('All submissions for <a href="{1}">{0}</a>', self.exam_name,
                           reverse('emath:exam_detail', args=[self.exam.key]))

    def access_check_contest(self, request):
        if self.in_exam and not self.exam.can_see_own_scoreboard(request.user):
            raise Http404()

    def access_check(self, request):
        # FIXME: This should be rolled into the `is_accessible_by` check when implementing #1509
        if self.in_exam and request.user.is_authenticated and request.profile.id in self.exam.editor_ids:
            return

        if not self.exam.is_accessible_by(request.user):
            raise Http404()

        # if self.check_contest_in_access_check:
        #     self.access_check_contest(request)

    def get(self, request, *args, **kwargs):
        if 'exam' not in kwargs:
            raise ImproperlyConfigured(_('Must pass a exam'))
        self.exam = get_object_or_404(Exam, key=kwargs['exam'])
        self.exam_name = self.exam.name
        return super(ExamSubmissionsBase, self).get(request, *args, **kwargs)

    def get_all_submissions_page(self):
        return reverse('emath:all_submissions')

    def get_context_data(self, **kwargs):
        context = super(ExamSubmissionsBase, self).get_context_data(**kwargs)
        # context['best_submissions_link'] = reverse('ranked_submissions', kwargs={'problem': self.exam.key})
        return context


class ExamSubmissions(ExamSubmissionsBase):
    def get_my_submissions_page(self):
        if self.request.user.is_authenticated:
            return reverse('emath:user_submission', kwargs={
                'exam': self.exam.key,
                'user': self.request.user.username,
            })


class UserMixin(object):
    def get(self, request, *args, **kwargs):
        if 'user' not in kwargs:
            raise ImproperlyConfigured('Must pass a user')
        self.profile = get_object_or_404(Profile, user__username=kwargs['user'])
        self.username = kwargs['user']
        return super(UserMixin, self).get(request, *args, **kwargs)


class ConditionalUserTabMixin(object):
    @cached_property
    def is_own(self):
        return self.request.user.is_authenticated and self.request.profile == self.profile
    
    def get_context_data(self, **kwargs):
        context = super(ConditionalUserTabMixin, self).get_context_data(**kwargs)
        if self.is_own:
            context["tab"] = 'my_submissions_tab'
        else:
            context['tab'] = 'user_submissions_tab'
            context['tab_user'] = self.profile.user.username
        return context
    

class AllUserSubmissions(ConditionalUserTabMixin, UserMixin, SubmissionsListBase):
    def get_queryset(self):
        return super(AllUserSubmissions, self).get_queryset().filter(user_id=self.profile.id)

    def get_title(self):
        if self.is_own:
            return _('All my submissions')
        return _('All submissions by %s') % self.username

    def get_content_title(self):
        if self.is_own:
            return format_html('All my submissions')
        return format_html('All submissions by <a href="{1}">{0}</a>', self.username,
                           reverse('user_page', args=[self.username]))

    def get_my_submissions_page(self):
        if self.request.user.is_authenticated:
            return reverse('all_user_submissions', kwargs={'user': self.request.user.username})

    def get_context_data(self, **kwargs):
        context = super(AllUserSubmissions, self).get_context_data(**kwargs)
        context['dynamic_update'] = context['page_obj'].number == 1
        context['dynamic_user_id'] = self.profile.id
        # context['last_msg'] = event.last()
        return context


class UserExamSubmissions(ConditionalUserTabMixin, UserMixin, ExamSubmissions):
    
    def access_check(self, request):
        super(UserExamSubmissions, self).access_check(request)

        if not self.is_own:
            self.access_check_contest(request)

    def get_queryset(self):
        return super(UserExamSubmissions, self).get_queryset().filter(user_id=self.profile.id)

    def get_title(self):
        if self.is_own:
            return _("My submissions for %(exam)s") % {'exam': self.exam_name}
        return _("%(user)s's submissions for %(exam)s") % {'user': self.username, 'exam': self.exam_name}

    def get_content_title(self):
        if self.request.user.is_authenticated and self.request.profile == self.profile:
            return format_html('''My submissions for <a href="{3}">{2}</a>''',
                               self.username, reverse('user_page', args=[self.username]),
                               self.exam_name, reverse('emath:exam_detail', args=[self.exam.key]))
        return format_html('''<a href="{1}">{0}</a>'s submissions for <a href="{3}">{2}</a>''',
                           self.username, reverse('user_page', args=[self.username]),
                           self.exam_name, reverse('emath:exam_detail', args=[self.exam.key]))

    def get_context_data(self, **kwargs):
        context = super(UserExamSubmissions, self).get_context_data(**kwargs)
        context['dynamic_user_id'] = self.profile.id
        return context