from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.db import ProgrammingError
from django.db.models import Q
from django.views.generic import ListView
from django.utils.functional import cached_property
from django.http import Http404

from emath.models import Problem
from emath.models.problem import MathGroup
from judge.comments import CommentedDetailView
from judge.pdf_problems import HAS_PDF
from judge.utils.strings import safe_int_or_none
from judge.utils.views import QueryStringSortMixin, TitleMixin, DiggPaginator, generic_message


class ProblemListMixin(object):
    def get_queryset(self):
        return Problem.get_visible_problems(self.request.user)
    

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

        paginator.num_pages

        sort_key = self.order.lstrip('-')
        if sort_key in self.sql_sort:
            queryset = queryset.order_by(self.order, 'id')
        elif sort_key == 'name':
            queryset = queryset.order_by(self.order.replace('name', 'i18n_name'), 'id')
        elif sort_key == 'group':
            queryset = queryset.order_by(self.order + '__name', 'id')

        paginator.object_list = queryset
        return paginator

    @cached_property
    def profile(self):
        if not self.request.user.is_authenticated:
            return None
        return self.request.profile

    def get_normal_queryset(self):
        filter = Q(is_public=True)
        if self.profile is not None:
            filter |= Q(authors=self.profile)

        queryset = Problem.objects.filter(filter).select_related('group').defer('description')
        if not self.request.user.has_perm('see_organization_math_problem'):
            filter = Q(is_organization_private=False)
            # if self.profile is not None:
            #     filter |= Q(organizations__in=self.profile.organizations.all())
            queryset = queryset.filter(filter)

        if self.category is not None:
            queryset = queryset.filter(group__id=self.category)
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

        return queryset.distinct()

    def get_queryset(self):
        return self.get_normal_queryset()

    def get_context_data(self, **kwargs):
        context = super(ProblemList, self).get_context_data(**kwargs)

        context['category'] = self.category
        context['categories'] = MathGroup.objects.all()

        context['has_fts'] = settings.ENABLE_FTS
        context['search_query'] = self.search_query

        context.update(self.get_sort_paginate_context())
        context.update(self.get_sort_context())

        return context

    def GET_with_session(self, request, key):
        if not request.GET:
            return request.session.get(key, False)
        return request.GET.get(key, None) == '1'

    def setup_problem_list(self, request):

        self.search_query = None
        self.category = None

        # This actually copies into the instance dictionary...
        self.all_sorts = set(self.all_sorts)

        self.category = safe_int_or_none(request.GET.get('category'))

    def get(self, request, *args, **kwargs):
        self.setup_problem_list(request)

        try:
            return super(ProblemList, self).get(request, *args, **kwargs)
        except ProgrammingError as e:
            return generic_message(request, 'FTS syntax error', e.args[1], status=400)

class ProblemDetail(ProblemMixin, CommentedDetailView):
    context_object_name = 'problem'
    template_name = 'tmatheng/problem/problem.html'

    def get_comment_page(self):
        return 'p:%s' % self.object.code

    def get_context_data(self, **kwargs):
        context = super(ProblemDetail, self).get_context_data(**kwargs)
        user = self.request.user
        authed = user.is_superuser or user.is_staff
        if not authed:
            raise Http404
        context['has_pdf_render'] = HAS_PDF

        can_edit = self.object.is_editable_by(user)
        context['can_edit_problem'] = can_edit

        context['title'] = self.object.name
        context['language'] = settings.LANGUAGE_CODE
        context['description'] = self.object.description
        context['translated'] = False

        return context