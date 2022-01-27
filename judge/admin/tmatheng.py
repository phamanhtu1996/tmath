# from operator import attrgetter
# from adminsortable2.admin import SortableInlineAdminMixin
# from django.conf.urls import url
# from django.contrib import admin
# from django.core.exceptions import PermissionDenied
# from django.forms import forms
# from django.db import connection, transaction
# from django.db.models import Q, TextField
# from django.forms import ModelForm, ModelMultipleChoiceField
# from django.http import Http404, HttpResponseRedirect
# from django.shortcuts import get_object_or_404
# from django.urls import reverse, reverse_lazy
# from django.utils import timezone
# from django.utils.html import format_html
# from django.utils.translation import gettext, gettext_lazy as _, ungettext
# from reversion.admin import VersionAdmin

# from django_ace import AceWidget, widgets
# from judge import forms
# # from judge.admin.problem import ProblemAdmin
# from judge.models import  Profile, Rating, Submission, MathProblem, Exam, ExamProblem, ExamSubmission
# # from judge.ratings import rate_exam
# from judge.utils.views import NoBatchDeleteMixin
# from judge.widgets import AdminHeavySelect2MultipleWidget, AdminHeavySelect2Widget, AdminMartorWidget, \
#     AdminSelect2MultipleWidget, AdminSelect2Widget

# class ExamProblemInlineForm(ModelForm):
#     class Meta:
#         widgets = {
#             'problem': AdminHeavySelect2Widget(data_view='mathproblem_select2')
#         }

# class ExamProblemInline(SortableInlineAdminMixin, admin.TabularInline):
#     model = ExamProblem
#     verbose_name = _('Problem')
#     verbose_name_plural = 'Problems'
#     fields = ('problem', 'points', 'order')
#             #   'rejudge_column')
#     # readonly_fields = ('rejudge_column',)
#     form = ExamProblemInlineForm

#     # def rejudge_column(self, obj):
#     #     if obj.id is None:
#     #         return ''
#     #     return format_html('<a class="button rejudge-link" href="{}">Rejudge</a>',
#     #                        reverse('admin:judge_Exam_rejudge', args=(obj.Exam.id, obj.id)))
#     # rejudge_column.short_description = ''


# class ExamForm(ModelForm):
#     def __init__(self, *args, **kwargs):
#         super(ExamForm, self).__init__(*args, **kwargs)
#         if 'rate_exclude' in self.fields:
#             if self.instance and self.instance.id:
#                 self.fields['rate_exclude'].queryset = \
#                     Profile.objects.filter(exam_history__exam=self.instance).distinct()
#             else:
#                 self.fields['rate_exclude'].queryset = Profile.objects.none()
#         self.fields['banned_users'].widget.can_add_related = False
#         self.fields['view_exam_scoreboard'].widget.can_add_related = False

#     def clean(self):
#         cleaned_data = super(ExamForm, self).clean()
#         cleaned_data['banned_users'].filter(current_exam__exam=self.instance).update(current_exam=None)

#     class Meta:
#         widgets = {
#             'authors': AdminHeavySelect2MultipleWidget(data_view='profile_select2'),
#             'curators': AdminHeavySelect2MultipleWidget(data_view='profile_select2'),
#             'testers': AdminHeavySelect2MultipleWidget(data_view='profile_select2'),
#             'private_contestants': AdminHeavySelect2MultipleWidget(data_view='profile_select2',
#                                                                    attrs={'style': 'width: 100%'}),
#             'organizations': AdminHeavySelect2MultipleWidget(data_view='organization_select2'),
#             # 'tags': AdminSelect2MultipleWidget,
#             'banned_users': AdminHeavySelect2MultipleWidget(data_view='profile_select2',
#                                                             attrs={'style': 'width: 100%'}),
#             'view_exam_scoreboard': AdminHeavySelect2MultipleWidget(data_view='profile_select2',
#                                                                        attrs={'style': 'width: 100%'}),
#             'description': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('contest_preview')}),
#         }

# class ExamAdmin(NoBatchDeleteMixin, VersionAdmin):
#     fieldsets = (
#         (None, {'fields': ('key', 'name', 'authors', 'curators', 'testers')}),
#         (_('Settings'), {'fields': ('is_visible', 'use_clarifications', 'hide_problem_tags', 'hide_problem_authors',
#                                     'run_pretests_only', 'locked_after', 'scoreboard_visibility',
#                                     'points_precision')}),
#         (_('Scheduling'), {'fields': ('start_time', 'end_time', 'time_limit')}),
#         (_('Details'), {'fields': ('description', 'og_image', 'logo_override_image', 'summary')}),
#         # (_('Format'), {'fields': ('format_name', 'format_config', 'problem_label_script')}),
#         (_('Rating'), {'fields': ('is_rated', 'rate_all', 'rating_floor', 'rating_ceiling', 'rate_exclude')}),
#         (_('Access'), {'fields': ('access_code', 'is_private', 'private_contestants', 'is_organization_private',
#                                   'organizations', 'view_exam_scoreboard')}),
#         (_('Justice'), {'fields': ('banned_users',)}),
#     )
    
#     list_display = ('key', 'name', 'is_visible', 'locked_after', 'start_time', 'end_time', 'time_limit',
#                     'user_count')
#     search_fields = ('key', 'name')
#     inlines = [ExamProblemInline]
#     actions_on_top = True
#     actions_on_bottom = True
#     form = ExamForm
#     # change_list_template = 'admin/judge/exam/change_list.html'
#     # filter_horizontal = ['rate_exclude']
#     date_hierarchy = 'start_time'

#     def get_actions(self, request):
#         actions = super(ExamAdmin, self).get_actions(request)

#         if request.user.has_perm('judge.change_exam_visibility') or \
#                 request.user.has_perm('judge.create_private_exam'):
#             for action in ('make_visible', 'make_hidden'):
#                 actions[action] = self.get_action(action)

#         if request.user.has_perm('judge.lock_exam'):
#             for action in ('set_locked', 'set_unlocked'):
#                 actions[action] = self.get_action(action)

#         return actions

#     def get_queryset(self, request):
#         queryset = Exam.objects.all()
#         if request.user.has_perm('judge.edit_all_exam'):
#             return queryset
#         else:
#             return queryset.filter(Q(authors=request.profile) | Q(curators=request.profile)).distinct()

#     def get_readonly_fields(self, request, obj=None):
#         readonly = []
#         if not request.user.has_perm('judge.exam_rating'):
#             readonly += ['is_rated', 'rate_all', 'rate_exclude']
#         if not request.user.has_perm('judge.lock_exam'):
#             readonly += ['locked_after']
#         # if not request.user.has_perm('judge.exam_access_code'):
#         #     readonly += ['access_code']
#         if not request.user.has_perm('judge.create_private_exam'):
#             readonly += ['is_private', 'private_contestants', 'is_organization_private', 'organizations']
#             if not request.user.has_perm('judge.change_exam_visibility'):
#                 readonly += ['is_visible']
#         if not request.user.has_perm('judge.exam_problem_label'):
#             readonly += ['problem_label_script']
#         return readonly

#     def save_model(self, request, obj, form, change):
#         # `is_visible` will not appear in `cleaned_data` if user cannot edit it
#         if form.cleaned_data.get('is_visible') and not request.user.has_perm('judge.change_exam_visibility'):
#             if not form.cleaned_data['is_private'] and not form.cleaned_data['is_organization_private']:
#                 raise PermissionDenied
#             if not request.user.has_perm('judge.create_private_exam'):
#                 raise PermissionDenied

#         super().save_model(request, obj, form, change)
#         # We need this flag because `save_related` deals with the inlines, but does not know if we have already rescored
#         self._rescored = False
#         if form.changed_data and any(f in form.changed_data for f in ('format_config', 'format_name')):
#             self._rescore(obj.key)
#             self._rescored = True

#         if form.changed_data and 'locked_after' in form.changed_data:
#             self.set_locked_after(obj, form.cleaned_data['locked_after'])

#     def save_related(self, request, form, formsets, change):
#         super().save_related(request, form, formsets, change)
#         # Only rescored if we did not already do so in `save_model`
#         # if not self._rescored and any(formset.has_changed() for formset in formsets):
#         #     self._rescore(form.cleaned_data['key'])

#     def has_change_permission(self, request, obj=None):
#         if not request.user.has_perm('judge.edit_own_exam'):
#             return False
#         if obj is None:
#             return True
#         return obj.is_editable_by(request.user)

#     # def _rescore(self, exam_key):
#     #     from judge.tasks import rescore_exam
#     #     transaction.on_commit(rescore_exam.s(exam_key).delay)

#     def make_visible(self, request, queryset):
#         if not request.user.has_perm('judge.change_exam_visibility'):
#             queryset = queryset.filter(Q(is_private=True) | Q(is_organization_private=True))
#         count = queryset.update(is_visible=True)
#         self.message_user(request, ungettext('%d exam successfully marked as visible.',
#                                              '%d exams successfully marked as visible.',
#                                              count) % count)
#     make_visible.short_description = _('Mark exams as visible')

#     def make_hidden(self, request, queryset):
#         if not request.user.has_perm('judge.change_exam_visibility'):
#             queryset = queryset.filter(Q(is_private=True) | Q(is_organization_private=True))
#         count = queryset.update(is_visible=True)
#         self.message_user(request, ungettext('%d exam successfully marked as hidden.',
#                                              '%d exams successfully marked as hidden.',
#                                              count) % count)
#     make_hidden.short_description = _('Mark exams as hidden')

#     def set_locked(self, request, queryset):
#         for row in queryset:
#             self.set_locked_after(row, timezone.now())
#         count = queryset.count()
#         self.message_user(request, ungettext('%d exam successfully locked.',
#                                              '%d exams successfully locked.',
#                                              count) % count)
#     set_locked.short_description = _('Lock exam submissions')

#     def set_unlocked(self, request, queryset):
#         for row in queryset:
#             self.set_locked_after(row, None)
#         count = queryset.count()
#         self.message_user(request, ungettext('%d exam successfully unlocked.',
#                                              '%d exams successfully unlocked.',
#                                              count) % count)
#     set_unlocked.short_description = _('Unlock exam submissions')

#     def set_locked_after(self, exam, locked_after):
#         with transaction.atomic():
#             exam.locked_after = locked_after
#             exam.save()
#             Submission.objects.filter(exam_object=exam,
#                                       exam__participation__virtual=0).update(locked_after=locked_after)

#     # def get_urls(self):
#     #     return [
#     #         url(r'^rate/all/$', self.rate_all_view, name='judge_exam_rate_all'),
#     #         url(r'^(\d+)/rate/$', self.rate_view, name='judge_exam_rate'),
#     #         url(r'^(\d+)/judge/(\d+)/$', self.rejudge_view, name='judge_exam_rejudge'),
#     #     ] + super(ExamAdmin, self).get_urls()

#     # def rejudge_view(self, request, exam_id, problem_id):
#     #     queryset = ExamSubmission.objects.filter(problem_id=problem_id).select_related('submission')
#     #     for model in queryset:
#     #         model.submission.judge(rejudge=True)

#     #     self.message_user(request, ungettext('%d submission was successfully scheduled for rejudging.',
#     #                                          '%d submissions were successfully scheduled for rejudging.',
#     #                                          len(queryset)) % len(queryset))
#     #     return HttpResponseRedirect(reverse('admin:judge_exam_change', args=(exam_id,)))

#     # def rate_all_view(self, request):
#     #     if not request.user.has_perm('judge.exam_rating'):
#     #         raise PermissionDenied()
#     #     with transaction.atomic():
#     #         with connection.cursor() as cursor:
#     #             cursor.execute('TRUNCATE TABLE `%s`' % Rating._meta.db_table)
#     #         Profile.objects.update(rating=None)
#     #         for exam in Exam.objects.filter(is_rated=True, end_time__lte=timezone.now()).order_by('end_time'):
#     #             rate_exam(exam)
#     #     return HttpResponseRedirect(reverse('admin:judge_exam_changelist'))

#     # def rate_view(self, request, id):
#     #     if not request.user.has_perm('judge.exam_rating'):
#     #         raise PermissionDenied()
#     #     exam = get_object_or_404(Exam, id=id)
#     #     if not exam.is_rated or not exam.ended:
#     #         raise Http404()
#     #     with transaction.atomic():
#     #         exam.rate()
#     #     return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:judge_exam_changelist')))

#     def get_form(self, request, obj=None, **kwargs):
#         form = super(ExamAdmin, self).get_form(request, obj, **kwargs)
#         if 'problem_label_script' in form.base_fields:
#             # form.base_fields['problem_label_script'] does not exist when the user has only view permission
#             # on the model.
#             form.base_fields['problem_label_script'].widget = AceWidget('lua', request.profile.ace_theme)

#         perms = ('edit_own_exam', 'edit_all_exam')
#         form.base_fields['curators'].queryset = Profile.objects.filter(
#             Q(user__is_superuser=True) |
#             Q(user__groups__permissions__codename__in=perms) |
#             Q(user__user_permissions__codename__in=perms),
#         ).distinct()
#         return form


# class ProblemGroupForm(ModelForm):
#     problems = ModelMultipleChoiceField(
#         label=_('Included problems'),
#         queryset=MathProblem.objects.defer('description').all(),
#         required=False,
#         help_text=_('These problems are included in this group of problems'),
#         widget=AdminHeavySelect2MultipleWidget(data_view='mathproblem_select2'))


# class MathProblemGroupAdmin(admin.ModelAdmin):
#     fields = ('name', 'full_name', 'problems')
#     form = ProblemGroupForm

#     def save_model(self, request, obj, form, change):
#         super(MathProblemGroupAdmin, self).save_model(request, obj, form, change)
#         obj.problem_set.set(form.cleaned_data['problems'])
#         obj.save()

#     def get_form(self, request, obj=None, **kwargs):
#         self.form.base_fields['problems'].initial = [o.pk for o in obj.problem_set.all()] if obj else []
#         return super(MathProblemGroupAdmin, self).get_form(request, obj, **kwargs)


# class MathProblemForm(ModelForm):
#     change_message = forms.CharField(max_length=256, label='Edit reason', required=False)

#     def __init__(self, *args, **kwargs):
#         super(MathProblemForm, self).__init__(*args, **kwargs)
#         self.fields['authors'].widget.can_add_related = False
#         # self.fields['curators'].widget.can_add_related = False
#         # self.fields['testers'].widget.can_add_related = False
#         # self.fields['banned_users'].widget.can_add_related = False
#         self.fields['change_message'].widget.attrs.update({
#             'placeholder': gettext('Describe the changes you made (optional)'),
#         })
    
#     class Meta:
#         widgets = {
#             'authors': AdminHeavySelect2MultipleWidget(data_view='profile_select2', attrs={'style': 'width: 100%'}),
#             # 'curators': AdminHeavySelect2MultipleWidget(data_view='profile_select2', attrs={'style': 'width: 100%'}),
#             # 'testers': AdminHeavySelect2MultipleWidget(data_view='profile_select2', attrs={'style': 'width: 100%'}),
#             # 'banned_users': AdminHeavySelect2MultipleWidget(data_view='profile_select2',
#             #                                                 attrs={'style': 'width: 100%'}),
#             'organizations': AdminHeavySelect2MultipleWidget(data_view='organization_select2',
#                                                              attrs={'style': 'width: 100%'}),
#             # 'types': AdminSelect2MultipleWidget,
#             'group': AdminSelect2Widget,
#             'description': AdminMartorWidget(attrs={'data-markdownfy-url': reverse_lazy('problem_preview')}),
#         }


# class MathProblemCreatorListFilter(admin.SimpleListFilter):
#     title = parameter_name = 'creator'

#     def lookups(self, request, model_admin):
#         queryset = Profile.objects.exclude(authored_problems=None).values_list('user__username', flat=True)
#         return [(name, name) for name in queryset]
    
#     def queryset(self, request, queryset):
#         if self.value() is None:
#             return queryset
#         return queryset.filter(authors__user__username=self.value())


# class MathProblemAdmin(NoBatchDeleteMixin, VersionAdmin):
#     fieldsets = (
#         (None, {
#             "fields": (
#                 'code', 'name', 'is_public', 'datetime', 'authors',# 'curators', 'testers',
#                 'is_organization_private', 'organizations',# 'submission_source_visibility_mode', 'is_full_markup',
#                 'description'# 'license',
#             ),
#         }),
#         (_('Answer'), {'fields': ('answer', 'wrong_answer1', 'wrong_answer2', 'wrong_answer3',)}),
#         (_('Taxonomy'), {'fields': ('group',)}),
#         (_('Points'), {"fields": ('point',)}),
#         # (_('Justice'), {'fields': ('banned_users',)}),
#         (_('History'), {"fields": ('change_message',)}),
#     )
#     list_display = ['code', 'name', 'show_authors', 'point', 'is_public', 'show_public']
#     ordering = ['code']
#     search_fields = ('code', 'name', 'authors__user__username')
#     list_max_show_all = 1000
#     actions_on_top = True
#     actions_on_bottom = True

#     list_filter = ('is_public', MathProblemCreatorListFilter)
#     form = MathProblemForm
#     date_hierarchy = 'datetime'

#     def get_actions(self, request):
#         actions = super(MathProblemAdmin, self).get_actions(request)

#         if request.user.has_perm('judge.change_public_math_visibility'):
#             func, name, desc = self.get_action('make_public')
#             actions[name] = (func, name, desc)

#             func, name, desc = self.get_action('make_private')
#             actions[name] = (func, name, desc)

#         func, name, desc = self.get_action('update_publish_date')
#         actions[name] = (func, name, desc)

#         return actions
    
#     def update_publish_date(self, request, queryset):
#         count = queryset.update(datetime=timezone.now())
#         self.message_user(request, ungettext("%d problem's publish date successfully updated.",
#                                              "%d problems' publish date successfully updated.",
#                                              count) % count)

#     update_publish_date.short_description = _('Set publish date to now')

#     def show_authors(self, obj):
#         return ', '.join(map(attrgetter('user.username'), obj.authors.all()))

#     show_authors.short_description = _('Authors')

#     def show_public(self, obj):
#         return format_html('<a href="{1}">{0}</a>', gettext('View on site'), obj.get_absolute_url())

#     show_public.short_description = ''

#     def make_public(self, request, queryset):
#         count = queryset.update(is_public=True)
#         # for problem_id in queryset.values_list('id', flat=True):
#         #     self._rescore(request, problem_id)
#         self.message_user(request, ungettext('%d problem successfully marked as public.',
#                                              '%d problems successfully marked as public.',
#                                              count) % count)

#     make_public.short_description = _('Mark problems as public')

#     def make_private(self, request, queryset):
#         count = queryset.update(is_public=False)
#         # for problem_id in queryset.values_list('id', flat=True):
#         #     self._rescore(request, problem_id)
#         self.message_user(request, ungettext('%d problem successfully marked as private.',
#                                              '%d problems successfully marked as private.',
#                                              count) % count)

#     make_private.short_description = _('Mark problems as private')

#     def get_queryset(self, request):
#         return MathProblem.get_editable_problems(request.user).prefetch_related('authors__user').distinct()

#     def get_form(self, *args, **kwargs):
#         form = super(MathProblemAdmin, self).get_form(*args, **kwargs)
#         form.base_fields['authors'].queryset = Profile.objects.all()
#         return form
    
#     # def save_model(self, request, obj, form, change):
#     #     super(ProblemAdmin, self).save_model(request, obj, form, change)
#         # if (form.changed_data and any (f in form.changed_data for f in ('is_public', 'is_organization_private', 'points'))):

#     def construct_change_message(self, request, form, *args, **kwargs):
#         if form.cleaned_data.get('change_message'):
#             return form.cleaned_data['change_message']
#         return super(MathProblemAdmin, self).construct_change_message(request, form, *args, **kwargs)