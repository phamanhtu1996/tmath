# from django.db import models
# from django.utils.translation import gettext, gettext_lazy as _
# from django.urls import reverse

# from judge.models import Profile
# from judge.models.contest import RATE, NEWBIE

# class Organization(models.Model):
#     name = models.CharField(max_length=128, verbose_name=_('organization title'))
#     slug = models.SlugField(max_length=128, verbose_name=_('organization slug'),
#                             help_text=_('Organization name shown in URL'))
#     short_name = models.CharField(max_length=20, verbose_name=_('short name'),
#                                   help_text=_('Displayed beside user name during contests'))
#     about = models.TextField(verbose_name=_('organization description'))
#     admins = models.ManyToManyField('judge.Profile', verbose_name=_('administrators'), related_name='admin_emath',
#                                     help_text=_('Those who can edit this organization'))
#     creation_date = models.DateTimeField(verbose_name=_('creation date'), auto_now_add=True)
#     is_open = models.BooleanField(verbose_name=_('is open organization?'),
#                                   help_text=_('Allow joining organization'), default=True)
#     slots = models.IntegerField(verbose_name=_('maximum size'), null=True, blank=True,
#                                 help_text=_('Maximum amount of users in this organization, '
#                                             'only applicable to private organizations'))
#     access_code = models.CharField(max_length=7, help_text=_('Student access code'),
#                                    verbose_name=_('access code'), null=True, blank=True)
#     logo_override_image = models.CharField(verbose_name=_('Logo override image'), default='', max_length=150,
#                                            blank=True,
#                                            help_text=_('This image will replace the default site logo for users '
#                                                        'viewing the organization.'))
#     rate = models.IntegerField(_("Rate of Organization"), default=NEWBIE, choices=RATE)

#     def __contains__(self, item):
#         if isinstance(item, int):
#             return self.members.filter(id=item).exists()
#         elif isinstance(item, Profile):
#             return self.members.filter(id=item.id).exists()
#         else:
#             raise TypeError('Organization membership test must be Profile or primany key')

#     def __str__(self):
#         return self.name

#     def get_absolute_url(self):
#         return reverse('organization_home', args=(self.id, self.slug))

#     def get_users_url(self):
#         return reverse('organization_users', args=(self.id, self.slug))

#     class Meta:
#         ordering = ['name']
#         permissions = (
#             ('organization_emath_admin', _('Administer EMath organizations')),
#             ('edit_all_emath_organization', _('Edit all EMath organizations')),
#         )
#         verbose_name = _('organization')
#         verbose_name_plural = _('organizations')


# class OrganizationRequest(models.Model):
#     user = models.ForeignKey(Profile, verbose_name=_('user'), related_name='emath_requests', on_delete=models.CASCADE)
#     organization = models.ForeignKey(Organization, verbose_name=_('organization'), related_name='requests',
#                                      on_delete=models.CASCADE)
#     time = models.DateTimeField(verbose_name=_('request time'), auto_now_add=True)
#     state = models.CharField(max_length=1, verbose_name=_('state'), choices=(
#         ('P', 'Pending'),
#         ('A', 'Approved'),
#         ('R', 'Rejected'),
#     ))
#     reason = models.TextField(verbose_name=_('reason'))

#     class Meta:
#         verbose_name = _('organization join request')
#         verbose_name_plural = _('organization join requests')
