from django.db import models
from django.utils.translation import gettext_lazy as _, gettext
from django.utils.functional import cached_property
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ObjectDoesNotExist

from judge.models import Profile

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

class Submission(models.Model):
    STATUS = (
        ('QU', _('Queued')),
        ('P', _('Processing')),
        ('G', _('Grading')),
        ('D', _('Completed')),
        ('IE', _('Internal Error')),
        ('CE', _('Compile Error')),
        ('AB', _('Aborted')),
    )
    IN_PROGRESS_GRADING_STATUS = ('QU', 'P', 'G')
    RESULT = SUBMISSION_RESULT
    USER_DISPLAY_CODES = {
        'AC': _('Accepted'),
        'WA': _('Wrong Answer'),
        'QU': _('Queued'),
        'P': _('Processing'),
        'G': _('Grading'),
        'D': _('Completed'),
    }

    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name=_('emath_user'))
    date = models.DateTimeField(verbose_name=_('submission time'), auto_now_add=True, db_index=True)
    time = models.FloatField(verbose_name=_('execution time'), null=True, db_index=True)
    points = models.FloatField(verbose_name=_('points granted'), null=True, db_index=True)
    result = models.CharField(verbose_name=_('result'), max_length=3, choices=SUBMISSION_RESULT,
                              default=None, null=True, blank=True, db_index=True)
    case_points = models.FloatField(verbose_name=_('test case points'), default=0)
    case_total = models.FloatField(verbose_name=_('test case total points'), default=0)

    @classmethod
    def result_class_from_code(cls, result, case_points, case_total):
        if result == 'AC':
            if case_points == case_total:
                return 'AC'
            return '_AC'
        return result

    @property
    def result_class(self):
        # This exists to save all these conditionals from being executed (slowly) in each row.jade template
        # if self.status in ('IE', 'CE'):
        #     return self.status
        return Submission.result_class_from_code(self.result, self.case_points, self.case_total)

    # @property
    # def memory_bytes(self):
    #     return self.memory * 1024 if self.memory is not None else 0

    @property
    def short_status(self):
        return self.result #or self.status

    @property
    def long_status(self):
        return Submission.USER_DISPLAY_CODES.get(self.short_status, '')

    @cached_property
    def is_locked(self):
        return self.locked_after is not None and self.locked_after < timezone.now()

    # def judge(self, *args, force_judge=False, **kwargs):
    #     if force_judge or not self.is_locked:
    #         judge_submission(self, *args, **kwargs)

    # judge.alters_data = True

    # def abort(self):
    #     abort_submission(self)

    # abort.alters_data = True

    def can_see_detail(self, user):
        if not user.is_authenticated:
            return False
        profile = user.profile
        # source_visibility = self.problem.submission_source_visibility
        if self.problem.is_editable_by(user):
            return True
        elif user.has_perm('judge.view_all_submission'):
            return True
        elif self.user_id == profile.id:
            return True
        # elif source_visibility == SubmissionSourceAccess.ALWAYS:
        #     return True
        # elif source_visibility == SubmissionSourceAccess.SOLVED and \
        #         (self.problem.is_public or self.problem.testers.filter(id=profile.id).exists()) and \
        #         self.problem.submission_set.filter(user_id=profile.id, result='AC',
        #                                            points=self.problem.points).exists():
        #     return True
        # elif source_visibility == SubmissionSourceAccess.ONLY_OWN and \
        #         self.problem.testers.filter(id=profile.id).exists():
        #     return True

        # If user is an author or curator of the exam the submission was made in
        if self.exam_object is not None and user.profile.id in self.exam_object.editor_ids:
            return True

        return False

    # @property
    # def is_graded(self):
    #     return self.status not in ('QU', 'P', 'G')

    # @cached_property
    # def exam_key(self):
    #     if hasattr(self, 'exam'):
    #         return self.exam_object.key

    def __str__(self):
        return 'Submission %d of %s by %s' % (self.id, self.exam, self.user.user.username)

    def get_absolute_url(self):
        return reverse('submission_status', args=(self.id,))

    # @cached_property
    # def exam_or_none(self):
    #     try:
    #         return self.exam
    #     except ObjectDoesNotExist:
    #         return None

    # @classmethod
    # def get_id_secret(cls, sub_id):
    #     return (hmac.new(utf8bytes(settings.EVENT_DAEMON_SUBMISSION_KEY), b'%d' % sub_id, hashlib.sha512)
    #                 .hexdigest()[:16] + '%08x' % sub_id)

    @cached_property
    def id_secret(self):
        return self.get_id_secret(self.id)

    class Meta:
        permissions = (
            # ('abort_any_submission', _('Abort any submission')),
            # ('rejudge_submission', _('Rejudge the submission')),
            # ('rejudge_submission_lot', _('Rejudge a lot of submissions')),
            ('spam_emath_submission', _('Submit without limit')),
            ('view_all_emath_submission', _('View all submission')),
            # ('resubmit_other', _("Resubmit others' submission")),
            ('lock_emath_submission', _('Change lock status of submission')),
        )
        verbose_name = _('emath_submission')
        verbose_name_plural = _('emath_submissions')


class SubmissionProblem(models.Model):
    submission = models.ForeignKey(Submission, verbose_name=_('submission'),
                                   related_name='problems', on_delete=models.CASCADE)
    problem = models.ForeignKey('ExamProblem', verbose_name=_('problem'), on_delete=models.CASCADE)
    result = models.BooleanField(verbose_name=_('result for this problem'), default=False)
    points = models.FloatField(verbose_name=_('points granted'), null=True)
    output = models.TextField(verbose_name=_('Student\'s answer'), blank=True)

    class Meta:
        unique_together = ('submission', 'problem')
        verbose_name = _('submission problem')
        verbose_name_plural = _('submission problems')
