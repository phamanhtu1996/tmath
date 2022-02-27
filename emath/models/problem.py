from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator

from django.conf import settings
from django.utils import timezone
from django.db import models
from django.db.models.query_utils import Q
from django.utils.translation import gettext, gettext_lazy as _
from django.urls import reverse
from django.utils.functional import cached_property

from judge.models.problem import disallowed_characters_validator
from judge.models import Profile

from emath.models import Organization

class MathGroup(models.Model):
    name = models.CharField(max_length=20, verbose_name=_('problem category ID'), unique=True)
    full_name = models.CharField(max_length=100, verbose_name=_('problem category name'))

    def __str__(self) -> str:
        return self.full_name

    class Meta:
        ordering = ['full_name']
        verbose_name = _('problem type')
        verbose_name_plural = _('problem types')
    

class SubmissionSourceAccess:
    ALWAYS = 'A'
    SOLVED = 'S'
    ONLY_OWN = 'O'
    FOLLOW = 'F'


class Problem(models.Model):

    code = models.CharField(verbose_name=_("code"), max_length=20, unique=True, blank=False, null=False,
                            validators=[RegexValidator('^[a-z0-9]+$', _('Problem code must be ^[a-z0-9]+$'))],
                            help_text=_('A short, unique code for the problem, '
                                        'used in the url after /problem/'))
    name = models.CharField(verbose_name=_("name"), max_length=200, blank=False, null=False,
                            help_text=_('The full name of the problem, '
                                        'as shown in the problem list.'))
    datetime = models.DateTimeField(verbose_name=_("time"), default=timezone.now, blank=False, null=False,
                            help_text=_("Doesn't have magic ability to auto-publish due to backward compatibility"))
    point = models.FloatField(verbose_name=_("points"),
                            help_text=_('Points awarded for problem completion. '
                                        "Points are displayed with a 'p' suffix if partial."),
                            validators=[MinValueValidator(settings.DMOJ_PROBLEM_MIN_PROBLEM_POINTS)])
    authors = models.ManyToManyField(Profile, verbose_name=_("authors"), blank=True, related_name=_("emath_authors"),
                            help_text=_('These users will be able to edit the problem, '
                                                 'and be listed as authors.'))
    description = models.TextField(verbose_name=_('problem body'), validators=[disallowed_characters_validator])
    answer = models.CharField(verbose_name=_("answer"), max_length=50, blank=True, null=True,
                            help_text=_("One number that is the answer of this problem."))
    wrong_answer1 = models.CharField(verbose_name=_("wrong answer"), max_length=50, default=None, blank=True, null=True,
                            help_text=_("One number that is a wrong answer of this problem."))
    wrong_answer2 = models.CharField(verbose_name=_("wrong answer"), max_length=50, default=None, blank=True, null=True,
                            help_text=_("One number that is a wrong answer of this problem."))
    wrong_answer3 = models.CharField(verbose_name=_("wrong answer"), max_length=50, default=None, blank=True, null=True,
                            help_text=_("One number that is a wrong answer of this problem."))
    is_public = models.BooleanField(verbose_name=_('publicly visible'), db_index=True, default=False)
    ac_rate = models.FloatField(verbose_name=_('solve rate'), default=0)
    user_count = models.IntegerField(verbose_name=_('number of users'), default=0,
                                     help_text=_('The number of users who solved the problem.'))
    organizations = models.ManyToManyField(Organization, blank=True, verbose_name=_('organizations'),
                                           help_text=_('If private, only these organizations may see the problem.'))
    is_organization_private = models.BooleanField(verbose_name=_('private to organizations'), default=False)

    group = models.ForeignKey(MathGroup, verbose_name=_("group"), 
                            help_text=_('The group of problem, shown under Category in the problem list.'), on_delete=models.CASCADE)
    
    difficult = models.IntegerField(verbose_name=_("difficult"), validators=[MinValueValidator(0), MaxValueValidator(3000)],
                            help_text=_("Difficult of problem"))
    
    is_full_markup = models.BooleanField(verbose_name=_('allow full markdown access'), default=False)
    
    def __init__(self, *args, **kwargs):
        super(Problem, self).__init__(*args, **kwargs)
        self._translated_name_cache = {}
        self._i18n_name = None
        self.__original_code = self.code

    class Meta:
        verbose_name = _("Math Problem")
        verbose_name_plural = _("Math Problems")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('emath:problem_detail', args=(self.code,))

    @classmethod
    def get_visible_problems(cls, user):
        if not user.is_authenticated:
            return cls.get_public_problems
        
        queryset = cls.objects.defer('description')
        if not (user.has_perm('judge.view_private_math_problem') or user.has_perm('judge.edit_all_math_problem')):
            q = Q(is_public=True)
            if not (user.has_perm('judge.see_organization_math_problem') or user.has_perm('judge.edit_public_math_problem')):
                q &= (
                    Q(is_organization_private=False) or
                    Q(is_organization_private=True, organizations__in=user.profile.organizations.all())
                )
            if user.has_perm('judge.edit_own_math_problem'):
                q |= Q(is_organization_private=True, organizations__in=user.profile.admin_of.all())
            q |= Q(authors=user.profile)
            queryset = queryset.filter(q)

        return queryset


    @classmethod
    def get_public_problems(cls):
        return cls.objects.filter(is_public=True, is_organization_private=False).defer('description')

    @classmethod
    def get_editable_problems(cls, user):
        if not user.has_perm('judge.edit_own_math_problem'):
            return cls.objects.none()
        if user.has_perm('judge.edit_all_math_problem'):
            return cls.objects.all()
        
        q = Q(authors=user.profile)
        q |= Q(is_organization_private=True, organizations__in=user.profile.admin_of.all())

        if user.has_perm('judge.edit_public_math_problem'):
            q |= Q(is_public=True)
        
        return cls.objects.filter(q)

    @cached_property
    def author_ids(self):
        return Problem.authors.through.objects.filter(problem=self).values_list('profile_id', flat=True)

    def is_editable_by(self, user):
        if not user.is_authenticated:
            return False
        if user.has_perm('emath.edit_all_math_problem') or user.has_perm('emath.edit_public_math_problem') and self.is_public:
            return True
        return user.has_perm('emath.edit_own_math_problem') and \
            (user.profile.id in self.author_ids or
                self.is_organization_private and self.organizations.filter(admins=user.profile).exists())

    @property
    def markdown_style(self):
        return 'problem-full' if self.is_full_markup else 'problem'

    class Meta:
        permissions = (
            ('view_private_math_problem', _('View private Math problems')),
            ('edit_own_math_problem', _('Edit own Math problems')),
            ('edit_all_math_problem', _('Edit all Math problems')),
            ('edit_public_math_problem', _('Edit all public Math problems')),
            ('see_organization_math_problem', _('See organizations-private Math problems')),
            ('change_public_math_visibility', _('Change public math problem visibility'))
        )


class Answer(models.Model):
    problem = models.ForeignKey(Problem, verbose_name=_("problem"), related_name='answers', null=True, on_delete=models.CASCADE)
    description = models.CharField(_("Content"), max_length=100, blank=False)
    is_correct = models.BooleanField(_("Correct answer"), default=False)