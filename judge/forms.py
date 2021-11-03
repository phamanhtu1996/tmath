import json
from operator import attrgetter, itemgetter, lshift
from django.forms.utils import flatatt

import pyotp
import webauthn
from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import Q
from django.forms import BooleanField, CharField, ChoiceField, Form, ModelForm, MultipleChoiceField
from django.urls import reverse_lazy
from django.utils.translation import gettext, gettext_lazy as _
from django.utils.safestring import mark_safe

from django_ace import AceWidget, widgets
from judge.models import Contest, Language, Organization, Problem, Profile, Submission, WebAuthnCredential
from judge.utils.subscription import newsletter_id
from judge.widgets import HeavyPreviewPageDownWidget, Select2MultipleWidget, Select2Widget


from judge.models import LanguageLimit, Problem, ProblemClarification, ProblemTranslation, Profile, Solution
from judge.utils.views import NoBatchDeleteMixin
from judge.widgets import HeavySelect2MultipleWidget, MartorWidget, \
    CheckboxSelectMultipleWithSelectAll

from copy import deepcopy

TOTP_CODE_LENGTH = 6

two_factor_validators_by_length = {
    TOTP_CODE_LENGTH: {
        'regex_validator': RegexValidator(
            f'^[0-9]{{{TOTP_CODE_LENGTH}}}$',
            _(f'Two-factor authentication tokens must be {TOTP_CODE_LENGTH} decimal digits.'),
        ),
        'verify': lambda code, profile: not profile.check_totp_code(code),
        'err': _('Invalid two-factor authentication token.'),
    },
    16: {
        'regex_validator': RegexValidator('^[A-Z0-9]{16}$', _('Scratch codes must be 16 base32 characters.')),
        'verify': lambda code, profile: code not in json.loads(profile.scratch_codes),
        'err': _('Invalid scratch code.'),
    },
}


def fix_unicode(string, unsafe=tuple('\u202a\u202b\u202d\u202e')):
    return string + (sum(k in unsafe for k in string) - string.count('\u202c')) * '\u202c'


class Fieldset(object):
    def __init__(self, form, name, boundfields, legend=None, description=''):
        self.form = form
        self.boundfields = boundfields
        if legend is None: legend = name
        self.legend = mark_safe(legend)
        self.description = mark_safe(description)
        self.name = name

    def __iter__(self):
        for bf in self.boundfields:
            yield _mark_row_attrs(bf, self.form)
    
    def __repr__(self):
        return "%s('%s', %s, legend='%s', description='%s')" % (
            self.__class__.__name__, self.name,
            [f.name for f in self.boundfields], self.legend, self.description)
    

class FieldsetCollection(object):
    def __init__(self, form, fieldsets):
        self.form = form
        self.fieldsets = fieldsets
    
    def __len__(self):
        return len(self.fieldsets) or 1
    
    def __iter__(self):
        if not self.fieldsets:
            self.fieldsets = (('main', {'fields': self.form.fields.keys(),
                                         'legend': ''}),)
        for name, options in self.fieldsets:
            try:
                field_names = [n for n in options['fields']
                               if n in self.form.fields]
            except KeyError:
                raise ValueError("Fieldset definition must include 'fields' option." )
            boundfields = [forms.forms.BoundField(self.form, self.form.fields[n], n)
                           for n in field_names]
            yield Fieldset(self.form, name, boundfields,
                           options.get('legend', None),
                           options.get('description', ''))


def _get_meta_attr(attrs, attr, default):
    try:
        ret = getattr(attrs['Meta'], attr)
    except (KeyError, AttributeError):
        ret = default
    return ret


def get_fieldsets(bases, attrs):
    """
    Get the fieldsets definition from the inner Meta class, mapping it
    on top of the fieldsets from any base classes.

    """
    fieldsets = _get_meta_attr(attrs, 'fieldsets', ())
        
    new_fieldsets = {}
    order = []
    
    for base in bases:
        for fs in getattr(base, 'base_fieldsets', ()):
            new_fieldsets[fs[0]] = fs
            order.append(fs[0])

    for fs in fieldsets:
        new_fieldsets[fs[0]] = fs
        if fs[0] not in order:
            order.append(fs[0])
    
    return [new_fieldsets[name] for name in order]
    

def get_row_attrs(bases, attrs):
    """
    Get the row_attrs definition from the inner Meta class.

    """
    return _get_meta_attr(attrs, 'row_attrs', {})

def _mark_row_attrs(bf, form):
    row_attrs = deepcopy(form._row_attrs.get(bf.name, {}))
    if bf.field.required:
        req_class = 'required'
    else:
        req_class = 'optional'
    if 'class' in row_attrs:
        row_attrs['class'] = row_attrs['class'] + ' ' + req_class
    else:
        row_attrs['class'] = req_class
    bf.row_attrs = mark_safe(flatatt(row_attrs))
    return bf


class BetterFormBaseMetaclass(type):
    def __new__(cls, name, bases, attrs):
        attrs['base_fieldsets'] = get_fieldsets(bases, attrs)
        attrs['base_row_attrs'] = get_row_attrs(bases, attrs)
        new_class = super(BetterFormBaseMetaclass,
                          cls).__new__(cls, name, bases, attrs)
        return new_class


class BetterFormMetaclass(BetterFormBaseMetaclass, forms.forms.DeclarativeFieldsMetaclass):
    pass


class BetterModelFormMetaclass(BetterFormBaseMetaclass, forms.models.ModelFormMetaclass):
    pass


class BetterBaseForm(object):
    def __init__(self, *args, **kwargs):
        self._fieldsets = deepcopy(self.base_fieldsets)
        self._row_attrs = deepcopy(self.base_row_attrs)
        super(BetterBaseForm, self).__init__(*args, **kwargs)

    @property
    def fieldsets(self):
        return FieldsetCollection(self, self._fieldsets)

    def __iter__(self):
        for bf in super(BetterBaseForm, self).__iter__():
            yield _mark_row_attrs(bf, self)


class BetterForm(BetterBaseForm, forms.Form):
    __metaclass__ = BetterFormMetaclass
    __doc__ = BetterBaseForm.__doc__


class BetterModelForm(BetterBaseForm, forms.ModelForm):
    __metaclass__ = BetterModelFormMetaclass
    __doc__ = BetterBaseForm.__doc__


class ProfileForm(ModelForm):
    if newsletter_id is not None:
        newsletter = forms.BooleanField(label=_('Subscribe to contest updates'), initial=False, required=False)
    test_site = forms.BooleanField(label=_('Enable experimental features'), initial=False, required=False)

    class Meta:
        model = Profile
        fields = ['about', 'organizations', 'timezone', 'language', 'ace_theme', 'user_script']
        widgets = {
            'user_script': AceWidget(theme='github'),
            'timezone': Select2Widget(attrs={'style': 'width:200px'}),
            'language': Select2Widget(attrs={'style': 'width:200px'}),
            'ace_theme': Select2Widget(attrs={'style': 'width:200px'}),
        }

        has_math_config = bool(settings.MATHOID_URL)
        if has_math_config:
            fields.append('math_engine')
            widgets['math_engine'] = Select2Widget(attrs={'style': 'width:200px'})

        if HeavyPreviewPageDownWidget is not None:
            widgets['about'] = HeavyPreviewPageDownWidget(
                preview=reverse_lazy('profile_preview'),
                attrs={'style': 'max-width:700px;min-width:700px;width:700px'},
            )

    def clean_about(self):
        if 'about' in self.changed_data and not self.instance.has_any_solves:
            raise ValidationError(_('You must solve at least one problem before you can update your profile.'))
        return self.cleaned_data['about']

    def clean(self):
        organizations = self.cleaned_data.get('organizations') or []
        max_orgs = settings.DMOJ_USER_MAX_ORGANIZATION_COUNT

        if sum(org.is_open for org in organizations) > max_orgs:
            raise ValidationError(
                _('You may not be part of more than {count} public organizations.').format(count=max_orgs))

        return self.cleaned_data

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(ProfileForm, self).__init__(*args, **kwargs)
        if not user.has_perm('judge.edit_all_organization'):
            self.fields['organizations'].queryset = Organization.objects.filter(
                Q(is_open=True) | Q(id__in=user.profile.organizations.all()),
            )
        if not self.fields['organizations'].queryset:
            self.fields.pop('organizations')


class DownloadDataForm(Form):
    comment_download = BooleanField(required=False, label=_('Download comments?'))
    submission_download = BooleanField(required=False, label=_('Download submissions?'))
    submission_problem_glob = CharField(initial='*', label=_('Filter by problem code glob:'), max_length=100)
    submission_results = MultipleChoiceField(
        required=False,
        widget=Select2MultipleWidget(
            attrs={'style': 'width: 260px', 'data-placeholder': _('Leave empty to include all submissions')},
        ),
        choices=sorted(map(itemgetter(0, 0), Submission.RESULT)),
        label=_('Filter by result:'),
    )

    def clean(self):
        can_download = ('comment_download', 'submission_download')
        if not any(self.cleaned_data[v] for v in can_download):
            raise ValidationError(_('Please select at least one thing to download.'))
        return self.cleaned_data

    def clean_submission_problem_glob(self):
        if not self.cleaned_data['submission_download']:
            return '*'
        return self.cleaned_data['submission_problem_glob']

    def clean_submission_result(self):
        if not self.cleaned_data['submission_download']:
            return ()
        return self.cleaned_data['submission_result']


class ProblemSubmitForm(ModelForm):
    source = CharField(max_length=65536, widget=AceWidget(theme='twilight', no_ace_media=True))
    judge = ChoiceField(choices=(), widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, judge_choices=(), **kwargs):
        super(ProblemSubmitForm, self).__init__(*args, **kwargs)
        self.fields['language'].empty_label = None
        self.fields['language'].label_from_instance = attrgetter('display_name')
        self.fields['language'].queryset = Language.objects.filter(judges__online=True).distinct()

        if judge_choices:
            self.fields['judge'].widget = Select2Widget(
                attrs={'style': 'width: 150px', 'data-placeholder': _('Any judge')},
            )
            self.fields['judge'].choices = judge_choices

    class Meta:
        model = Submission
        fields = ['language']


class EditOrganizationForm(ModelForm):
    class Meta:
        model = Organization
        fields = ['about', 'logo_override_image', 'admins']
        widgets = {'admins': Select2MultipleWidget(attrs={'style': 'width: 200px'})}
        if HeavyPreviewPageDownWidget is not None:
            widgets['about'] = HeavyPreviewPageDownWidget(preview=reverse_lazy('organization_preview'))


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(CustomAuthenticationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': _('Username')})
        self.fields['password'].widget.attrs.update({'placeholder': _('Password')})

        self.has_google_auth = self._has_social_auth('GOOGLE_OAUTH2')
        self.has_facebook_auth = self._has_social_auth('FACEBOOK')
        self.has_github_auth = self._has_social_auth('GITHUB_SECURE')

    def _has_social_auth(self, key):
        return (getattr(settings, 'SOCIAL_AUTH_%s_KEY' % key, None) and
                getattr(settings, 'SOCIAL_AUTH_%s_SECRET' % key, None))


class NoAutoCompleteCharField(forms.CharField):
    def widget_attrs(self, widget):
        attrs = super(NoAutoCompleteCharField, self).widget_attrs(widget)
        attrs['autocomplete'] = 'off'
        return attrs


class TOTPForm(Form):
    TOLERANCE = settings.DMOJ_TOTP_TOLERANCE_HALF_MINUTES

    totp_or_scratch_code = NoAutoCompleteCharField(required=False)

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop('profile')
        super().__init__(*args, **kwargs)

    def clean(self):
        totp_or_scratch_code = self.cleaned_data.get('totp_or_scratch_code')
        try:
            validator = two_factor_validators_by_length[len(totp_or_scratch_code)]
        except KeyError:
            raise ValidationError(_('Invalid code length.'))
        validator['regex_validator'](totp_or_scratch_code)
        if validator['verify'](totp_or_scratch_code, self.profile):
            raise ValidationError(validator['err'])


class TOTPEnableForm(TOTPForm):
    def __init__(self, *args, **kwargs):
        self.totp_key = kwargs.pop('totp_key')
        super().__init__(*args, **kwargs)

    def clean(self):
        totp_validate = two_factor_validators_by_length[TOTP_CODE_LENGTH]
        code = self.cleaned_data.get('totp_or_scratch_code')
        totp_validate['regex_validator'](code)
        if not pyotp.TOTP(self.totp_key).verify(code, valid_window=settings.DMOJ_TOTP_TOLERANCE_HALF_MINUTES):
            raise ValidationError(totp_validate['err'])


class TwoFactorLoginForm(TOTPForm):
    webauthn_response = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.webauthn_challenge = kwargs.pop('webauthn_challenge')
        self.webauthn_origin = kwargs.pop('webauthn_origin')
        super().__init__(*args, **kwargs)

    def clean(self):
        totp_or_scratch_code = self.cleaned_data.get('totp_or_scratch_code')
        if self.profile.is_webauthn_enabled and self.cleaned_data.get('webauthn_response'):
            if len(self.cleaned_data['webauthn_response']) > 65536:
                raise ValidationError(_('Invalid WebAuthn response.'))

            if not self.webauthn_challenge:
                raise ValidationError(_('No WebAuthn challenge issued.'))

            response = json.loads(self.cleaned_data['webauthn_response'])
            try:
                credential = self.profile.webauthn_credentials.get(cred_id=response.get('id', ''))
            except WebAuthnCredential.DoesNotExist:
                raise ValidationError(_('Invalid WebAuthn credential ID.'))

            user = credential.webauthn_user
            # Work around a useless check in the webauthn package.
            user.credential_id = credential.cred_id
            assertion = webauthn.WebAuthnAssertionResponse(
                webauthn_user=user,
                assertion_response=response.get('response'),
                challenge=self.webauthn_challenge,
                origin=self.webauthn_origin,
                uv_required=False,
            )

            try:
                sign_count = assertion.verify()
            except Exception as e:
                raise ValidationError(str(e))

            credential.counter = sign_count
            credential.save(update_fields=['counter'])
        elif totp_or_scratch_code:
            if self.profile.is_totp_enabled and self.profile.check_totp_code(totp_or_scratch_code):
                return
            elif self.profile.scratch_codes and totp_or_scratch_code in json.loads(self.profile.scratch_codes):
                scratch_codes = json.loads(self.profile.scratch_codes)
                scratch_codes.remove(totp_or_scratch_code)
                self.profile.scratch_codes = json.dumps(scratch_codes)
                self.profile.save(update_fields=['scratch_codes'])
                return
            elif self.profile.is_totp_enabled:
                raise ValidationError(_('Invalid two-factor authentication token or scratch code.'))
            else:
                raise ValidationError(_('Invalid scratch code.'))
        else:
            raise ValidationError(_('Must specify either totp_token or webauthn_response.'))


class ProblemCloneForm(Form):
    code = CharField(max_length=20, validators=[RegexValidator('^[a-z0-9]+$', _('Problem code must be ^[a-z0-9]+$'))])

    def clean_code(self):
        code = self.cleaned_data['code']
        if Problem.objects.filter(code=code).exists():
            raise ValidationError(_('Problem with code already exists.'))
        return code


class ContestCloneForm(Form):
    key = CharField(max_length=20, validators=[RegexValidator('^[a-z0-9]+$', _('Contest id must be ^[a-z0-9]+$'))])

    def clean_key(self):
        key = self.cleaned_data['key']
        if Contest.objects.filter(key=key).exists():
            raise ValidationError(_('Contest with key already exists.'))
        return key


class ProblemCreateForm(ModelForm):
    
    def __init__(self, *args, **kwargs):
        super(ProblemCreateForm, self).__init__(*args, **kwargs)
        self.fields['authors'].widget.can_add_related = False
        self.fields['curators'].widget.can_add_related = False
        self.fields['testers'].widget.can_add_related = False
        # self.fields['banned_users'].widget.can_add_related = False
        # self.fields['change_message'].widget.attrs.update({
        #     'placeholder': gettext('Describe the changes you made (optional)'),
        # })

    class Meta:
        model = Problem
        fields = ['code', 'name', 'is_public', 'is_manually_managed', 'date', 'authors', 'curators', 'testers',
                'is_organization_private', 'organizations', 'submission_source_visibility_mode', 'is_full_markup',
                'description', 'license', 'time_limit', 'memory_limit', 'types', 'group', 
                'allowed_languages']
        widgets = {
            'authors': HeavySelect2MultipleWidget(data_view='profile_select2', attrs={'style': 'width: 25%'}),
            'curators': HeavySelect2MultipleWidget(data_view='profile_select2', attrs={'style': 'width: 25%'}),
            'testers': HeavySelect2MultipleWidget(data_view='profile_select2', attrs={'style': 'width: 25%'}),
            # 'banned_users': AdminHeavySelect2MultipleWidget(data_view='profile_select2',
                                                            # attrs={'style': 'width: 100%'}),
            'organizations': HeavySelect2MultipleWidget(data_view='organization_select2',
                                                             attrs={'style': 'width: 50%'}),
            'types': Select2MultipleWidget,
            'group': Select2Widget,
            'allowed_languages': CheckboxSelectMultipleWithSelectAll,
            'description': MartorWidget(attrs={'data-markdownfy-url': reverse_lazy('problem_preview')}),
        }


class ProblemSolutionForm(ModelForm):
    class Meta:
        model = Solution
        fields = ('is_public', 'publish_on', 'authors', 'content')
        widgets = {
            'authors': HeavySelect2MultipleWidget(data_view='profile_select2', attrs={'style': 'width: 25%'}),
            'content': MartorWidget(attrs={'data-markdownfy-url': reverse_lazy('problem_preview')}),
        }

ProblemSolutionInlineForm = forms.inlineformset_factory(
    Problem,
    Solution,
    form=ProblemSolutionForm,
    extra=0,
    can_delete=False,
)


class LanguageLimitForm(ModelForm):
    class Meta:
        model = LanguageLimit
        fields = ('language', 'time_limit', 'memory_limit')

# ProblemCreateAllForm = forms.inlineformset_factory()