from django.forms import ValidationError
from jsonfield import JSONField

from django.db import models, transaction
from django.db.models import Max, CASCADE
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.translation import gettext, gettext_lazy as _
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils import timezone
from django.db.models.query_utils import Q
from emath.models.submission import Submission
from judge.contest_format.base import BaseContestFormat

from judge.models import Profile
from judge.models.contest import MinValueOrNoneValidator
from emath.models.problem import Problem
from emath.models import Organization
from emath import exam_format


class Exam(models.Model):
    SCOREBOARD_VISIBLE = 'V'
    SCOREBOARD_AFTER_EXAM = 'C'
    SCOREBOARD_AFTER_PARTICIPATION = 'P'
    SCOREBOARD_VISIBILITY = (
        (SCOREBOARD_VISIBLE, _('Visible')),
        (SCOREBOARD_AFTER_EXAM, _('Hidden for duration of exam')),
        (SCOREBOARD_AFTER_PARTICIPATION, _('Hidden for duration of participation')),
    )
    key = models.CharField(max_length=20, verbose_name=_('exam id'), unique=True,
                           validators=[RegexValidator('^[a-z0-9]+$', _('exam id must be ^[a-z0-9]+$'))])
    name = models.CharField(max_length=100, verbose_name=_('exam name'), db_index=True)
    authors = models.ManyToManyField(Profile, help_text=_('These users will be able to edit the exam.'),
                                     related_name='authors+')
    curators = models.ManyToManyField(Profile, help_text=_('These users will be able to edit the exam, '
                                                           'but will not be listed as authors.'),
                                      related_name='curators+', blank=True)
    testers = models.ManyToManyField(Profile, help_text=_('These users will be able to view the exam, '
                                                          'but not edit it.'),
                                     blank=True, related_name='testers+')
    description = models.TextField(verbose_name=_('description'), blank=True)
    problems = models.ManyToManyField(Problem, verbose_name=_('problems'), through='examProblem')
    start_time = models.DateTimeField(verbose_name=_('start time'), db_index=True)
    end_time = models.DateTimeField(verbose_name=_('end time'), db_index=True)
    time_limit = models.DurationField(verbose_name=_('time limit'), blank=True, null=True)
    is_visible = models.BooleanField(verbose_name=_('publicly visible'), default=False,
                                     help_text=_('Should be set even for organization-private exams, where it '
                                                 'determines whether the exam is visible to members of the '
                                                 'specified organizations.'))
    is_rated = models.BooleanField(verbose_name=_('exam rated'), help_text=_('Whether this exam can be rated.'),
                                   default=False)
    view_exam_scoreboard = models.ManyToManyField(Profile, verbose_name=_('view exam scoreboard'), blank=True,
                                                     related_name='view_exam_scoreboard',
                                                     help_text=_('These users will be able to view the scoreboard.'))
    scoreboard_visibility = models.CharField(verbose_name=_('scoreboard visibility'), default=SCOREBOARD_VISIBLE,
                                             max_length=1, help_text=_('Scoreboard visibility through the duration '
                                                                       'of the exam'), choices=SCOREBOARD_VISIBILITY)
    use_clarifications = models.BooleanField(verbose_name=_('no comments'),
                                             help_text=_("Use clarification system instead of comments."),
                                             default=True)
    rating_floor = models.IntegerField(verbose_name=('rating floor'), help_text=_('Rating floor for exam'),
                                       null=True, blank=True)
    rating_ceiling = models.IntegerField(verbose_name=('rating ceiling'), help_text=_('Rating ceiling for exam'),
                                         null=True, blank=True)
    rate_all = models.BooleanField(verbose_name=_('rate all'), help_text=_('Rate all users who joined.'), default=False)
    rate_exclude = models.ManyToManyField(Profile, verbose_name=_('exclude from ratings'), blank=True,
                                          related_name='rate_exclude+')
    is_private = models.BooleanField(verbose_name=_('private to specific users'), default=False)
    private_contestants = models.ManyToManyField(Profile, blank=True, verbose_name=_('private examants'),
                                                 help_text=_('If private, only these users may see the exam'),
                                                 related_name='private_contestants+')
    hide_problem_tags = models.BooleanField(verbose_name=_('hide problem tags'),
                                            help_text=_('Whether problem tags should be hidden by default.'),
                                            default=False)
    hide_problem_authors = models.BooleanField(verbose_name=_('hide problem authors'),
                                               help_text=_('Whether problem authors should be hidden by default.'),
                                               default=False)
    run_pretests_only = models.BooleanField(verbose_name=_('run pretests only'),
                                            help_text=_('Whether judges should grade pretests only, versus all '
                                                        'testcases. Commonly set during a exam, then unset '
                                                        'prior to rejudging user submissions when the exam ends.'),
                                            default=False)
    is_organization_private = models.BooleanField(verbose_name=_('private to organizations'), default=False)
    organizations = models.ManyToManyField(Organization, blank=True, verbose_name=_('organizations'),
                                           help_text=_('If private, only these organizations may see the exam'))
    og_image = models.CharField(verbose_name=_('OpenGraph image'), default='', max_length=150, blank=True)
    logo_override_image = models.CharField(verbose_name=_('Logo override image'), default='', max_length=150,
                                           blank=True,
                                           help_text=_('This image will replace the default site logo for users '
                                                       'inside the exam.'))
    # tags = models.ManyToManyField(examTag, verbose_name=_('exam tags'), blank=True, related_name='exams')
    user_count = models.IntegerField(verbose_name=_('the amount of live participants'), default=0)
    summary = models.TextField(blank=True, verbose_name=_('exam summary'),
                               help_text=_('Plain-text, shown in meta description tag, e.g. for social media.'))
    access_code = models.CharField(verbose_name=_('access code'), blank=True, default='', max_length=255,
                                   help_text=_('An optional code to prompt examants before they are allowed '
                                               'to join the exam. Leave it blank to disable.'))
    banned_users = models.ManyToManyField(Profile, verbose_name=_('personae non gratae'), blank=True,
                                          help_text=_('Bans the selected users from joining this exam.'))
    format_name = models.CharField(verbose_name=_('exam format'), default='default', max_length=32,
                                   choices=exam_format.choices(), help_text=_('The exam format module to use.'))
    # format_config = JSONField(verbose_name=_('exam format configuration'), null=True, blank=True,
    #                           help_text=_('A JSON object to serve as the configuration for the chosen exam format '
    #                                       'module. Leave empty to use None. Exact format depends on the exam format '
    #                                       'selected.'))
    problem_label_script = models.TextField(verbose_name='exam problem label script', blank=True,
                                            help_text='A custom Lua function to generate problem labels. Requires a '
                                                      'single function with an integer parameter, the zero-indexed '
                                                      'exam problem index, and returns a string, the label.')
    locked_after = models.DateTimeField(verbose_name=_('exam lock'), null=True, blank=True,
                                        help_text=_('Prevent submissions from this exam '
                                                    'from being rejudged after this date.'))
    points_precision = models.IntegerField(verbose_name=_('precision points'), default=3,
                                           validators=[MinValueValidator(0), MaxValueValidator(10)],
                                           help_text=_('Number of digits to round points to.'))
    max_submissions = models.IntegerField(help_text=_('Maximum number of submissions for this exam, '
                                                      'or leave blank for no limit.'),
                                          default=None, null=True, blank=True,
                                          validators=[MinValueOrNoneValidator(1, _('Why include a exam you '
                                                                                   'can\'t submit to?'))])

    def __str__(self) -> str:
        return self.name
    
    def get_absolute_url(self):
        return reverse("emath:exam_detail", args=(self.key))
    
    @property
    def exam_window_length(self):
        return self.end_time - self.start_time

    @cached_property
    def _now(self):
        return timezone.now()

    @cached_property
    def format_class(self):
        return exam_format.formats[self.format_name]
    
    @cached_property
    def format(self):
        return self.format_class(self)
    
    @cached_property
    def get_label_for_problem(self):
        return self.format.get_label_for_problem

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError('What is this? A exam that ended before it starts?')

        try:
            label = self.get_label_for_problem(0)
        except Exception as e:
            raise ValidationError('Exam problem label script: %s' % e)
        else:
            if not isinstance(label, str):
                raise ValidationError('Contest problem label script: script should return a string.')

    @cached_property
    def ended(self):
        return self.end_time < self._now

    @cached_property
    def can_join(self):
        return self.start_time <= self._now
        
    @property
    def time_before_start(self):
        if self.start_time >= self._now:
            return self.start_time - self._now
        else:
            return None

    @property
    def time_before_end(self):
        if self.end_time >= self._now:
            return self.end_time - self._now
        else:
            return None


    
    @cached_property
    def author_ids(self):
        return Exam.authors.through.objects.filter(exam=self).values_list('profile_id', flat=True)
    
    @cached_property
    def editor_ids(self):
        return self.author_ids.union(
            Exam.curators.through.objects.filter(exam=self).values_list('profile_id', flat=True)
        )
    
    @cached_property
    def tester_ids(self):
        return Exam.testers.through.objects.filter(exam=self).values_list('profile_id', flat=True)

    def update_user_count(self):
        self.user_count = self.users.filter(virtual=0).count()
        self.save()

    update_user_count.alters_data = True

    class Inaccessible(Exception):
        pass

    class PrivateExam(Exception):
        pass

    def access_check(self, user):
        if not user.is_authenticated:
            if not self.is_visible:
                raise self.Inaccessible()
            if self.is_private or self.is_organization_private:
                raise self.PrivateExam()
            return
        
        if user.has_perm('emath.see_private_exam') or user.has_perm('emath.edit_all_exam'):
            return
        
        if user.profile.id in self.editor_ids:
            return

        if user.profile.id in self.tester_ids:
            return
        
        if not self.is_visible:
            raise self.Inaccessible()
        
        if not self.is_private and not self.is_organization_private:
            return

        if self.view_exam_scoreboard.filter(id=user.profile.id).exists():
            return

        in_org = self.organizations.filter(id__in=user.profile.organizations.all()).exists()
        in_users = self.private_contestants.filter(id=user.profile.id).exists()

        if self.is_private and not self.is_organization_private:
            if in_users:
                return
            raise self.PrivateExam()
        
        if self.is_private and self.is_organization_private:
            if in_org and in_users:
                return
            raise self.PrivateExam()
        
    def is_accessible_by(self, user):
        try:
            self.access_check(user)
        except (self.Inaccessible, self.PrivateExam):
            return False
        else:
            return True
        
    def has_completed_exam(self, user):
        if user.is_authenticated:
            participation = self.users.filter(virtual=ExamParticipation.LIVE, user=user.profile).first()
            if participation and participation.ended:
                return True
        return False

    @cached_property
    def show_scoreboard(self):
        if not self.can_join:
            return False
        if (self.scoreboard_visibility in (self.SCOREBOARD_AFTER_EXAM, self.SCOREBOARD_AFTER_PARTICIPATION) and
                not self.ended):
            return False
        return True

    def is_in_exam(self, user):
        if user.is_authenticated:
            profile = user.profile
            return profile and profile.current_exam is not None and profile.current_exam.exam == self
        return False

    def can_see_own_scoreboard(self, user):
        if self.can_see_full_scoreboard(user):
            return True
        if not self.can_join:
            return False
        if not self.show_scoreboard and not self.is_in_exam(user):
            return False
        return True

    def can_see_full_scoreboard(self, user):
        if self.show_scoreboard:
            return True
        if not user.is_authenticated:
            return False
        if user.has_perm('emath.see_private_exam') or user.has_perm('emath.edit_all_exam'):
            return True
        if user.profile.id in self.editor_ids:
            return True
        if self.view_exam_scoreboard.filter(id=user.profile.id).exists():
            return True
        if self.scoreboard_visibility == self.SCOREBOARD_AFTER_PARTICIPATION and self.has_completed_exam(user):
            return True
        return False

    @classmethod
    def get_visible_exams(cls, user):
        if not user.is_authenticated:
            return cls.objects.filter(is_visible=True, is_organization_private=False, is_private=False) \
                .defer('description').distinct()
        queryset = cls.objects.defer('description')
        if not (user.has_perm('emath.see_private_exam') or user.has_perm('emath.edit_all_exam')):
            q = Q(is_visible=True)
            q &= (
                Q(view_exam_scoreboard=user.profile) |
                Q(is_organization_private=False, is_private=False) |
                Q(is_organization_private=False, is_private=True, private_contestants=user.profile) 
                # Q(is_organization_private=True, is_private=False, organizations__in=user.profile.organizations.all()) |
                # Q(is_organization_private=True, is_private=True, organizations__in=user.profile.organizations.all(),
                #   private_contestants=user.profile)
            )
            q |= Q(authors=user.profile)
            q |= Q(curators=user.profile)
            q |= Q(testers=user.profile)
            queryset = queryset.filter(q)
        return queryset.distinct()

    def is_editable_by(self, user):
        if user.has_perm('emath.edit_all_exam'):
            return True
        
        if user.has_perm('emath.edit_own_exam') and user.profile.id in self.editor_ids:
            return True
        
        return False

    class Meta:
        permissions = (
            ('see_private_exam', _('See private exams')),
            ('edit_own_exam', _('Edit own exams')),
            ('edit_all_exam', _('Edit all exam')),
            ('clone_exam', _('Clone exam')),
            ('exam_rating', _('Rate exams')),
            ('create_private_exam', _('Create private exams')),
            ('change_exam_visibility', _('Change exam visibility')),
            ('exam_problem_label', _('Edit exam problem label script')),
            ('lock_exam', _('Change lock status of exam'))
        )
        verbose_name = _('exam')
        verbose_name_plural = _('exams')


class ExamProblem(models.Model):
    problem = models.ForeignKey(Problem, verbose_name=_('problem'), related_name='exams', on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, verbose_name=_('exam'), related_name='exam_problems', on_delete=models.CASCADE)
    points = models.IntegerField(verbose_name=_('point'))
    order = models.PositiveIntegerField(db_index=True, verbose_name=_('order'))

    class Meta:
        unique_together = ('problem', 'exam')
        verbose_name = _('exam problem')
        verbose_name_plural = _('exam problems')
        ordering = ('order',)


class ExamParticipation(models.Model):
    LIVE = 0
    SPECTATE = -1

    exam = models.ForeignKey(Exam, verbose_name=_('associated exam'), related_name='users', on_delete=models.CASCADE)
    user = models.ForeignKey(Profile, verbose_name=_('user'), related_name='exam_history', on_delete=models.CASCADE)
    real_start = models.DateTimeField(verbose_name=_('start time'), default=timezone.now, db_column='start')
    score = models.FloatField(verbose_name=_('score'), default=0, db_index=True)
    cumtime = models.PositiveIntegerField(verbose_name=_('cumulative time'), default=0)
    is_disqualified = models.BooleanField(verbose_name=_('is disqualified'), default=False,
                                          help_text=_('Whether this participation is disqualified.'))
    tiebreaker = models.FloatField(verbose_name=_('tie-breaking field'), default=0.0)
    virtual = models.IntegerField(verbose_name=_('virtual participation id'), default=LIVE,
                                  help_text=_('0 means non-virtual, otherwise the n-th virtual participation.'))
    format_data = JSONField(verbose_name=_('exam format specific data'), null=True, blank=True)

    def recompute_results(self):
        with transaction.atomic():
            self.exam.format.update_participation(self)
            if self.is_disqualified:
                self.score = -9999
                self.save(update_fields=['score'])
    recompute_results.alters_data = True

    def set_disqualified(self, disqualified):
        self.is_disqualified = disqualified
        self.recompute_results()
        if self.is_disqualified:
            if self.user.current_exam == self:
                self.user.remove_exam()
            self.exam.banned_users.add(self.user)
        else:
            self.exam.banned_users.remove(self.user)
    set_disqualified.alters_data = True

    def set_real_start(self):
        self.real_start = timezone.now()
        self.save()
    set_real_start.alters_data = True

    @cached_property
    def _now(self):
        return timezone.now()
    
    @property
    def live(self):
        return self.virtual == self.LIVE
    
    @property
    def spectate(self):
        return self.virtual == self.SPECTATE
    
    @cached_property
    def start(self):
        exam = self.exam
        return exam.start_time if exam.time_limit is None and (self.live or self.spectate) else self.real_start

    @cached_property
    def end_time(self):
        exam = self.exam
        if self.spectate:
            return exam.end_time
        if self.virtual:
            if exam.time_limit:
                return self.real_start + exam.time_limit
            else:
                return self.real_start + (exam.end_time - exam.start_time)
        return exam.end_time if exam.time_limit is None else \
            min(self.real_start + exam.time_limit, exam.end_time)
    
    @property
    def ended(self):
        return self.end_time is not None and self.end_time < self._now
    
    @property
    def time_remaining(self):
        end = self.end_time
        if end is not None and end >= self._now:
            return end - self._now
        
    def __str__(self) -> str:
        name = self.user.name if self.user.name is not None else self.user.user.username
        if self.spectate:
            return gettext('%s spectating in %s') % (name, self.exam.name)
        if self.virtual:
            return gettext('%s in %s, v%d') % (name, self.exam.name, self.virtual)
        return gettext('%s in %s') % (name, self.exam.name)
    
    class Meta:
        verbose_name = _('exam participation')
        verbose_name_plural = _('exam participations')

        unique_together = ('exam', 'user', 'virtual')

SUBMISSION_RESULT = (
    ('AC', _('Accepted')),
    ('WA', _('Wrong Answer')),
    ('TLE', _('Time Limit Exceeded')),
    ('MLE', _('Memory Limit Exceeded')),
    ('OLE', _('Output Limit Exceeded')),
    ('IR', _('Invalid Return')),
    ('RTE', _('Runtime Error')),
    ('CE', _('Compile Error')),
    ('IE', _('Internal Error')),
    ('SC', _('Short circuit')),
    ('AB', _('Aborted')),
)


class ExamSubmission(models.Model):
    submission = models.OneToOneField(Submission, verbose_name=_('submission'), null=True,
                                      related_name='exam', on_delete=CASCADE)
    exam = models.ForeignKey(Exam, verbose_name=_('exam'), on_delete=CASCADE, null=True,
                             related_name='submissions', related_query_name='submission')
    participation = models.ForeignKey(ExamParticipation, verbose_name=_('participation'), on_delete=CASCADE, null=True,
                                      related_name='submissions', related_query_name='submission')
    points = models.FloatField(verbose_name=_('points'), default=0.0)

    def update_exam(self):
        self.participation.recompute_results()

    class Meta:
        verbose_name = _('exam submission')
        verbose_name_plural = _('exam submissions')
