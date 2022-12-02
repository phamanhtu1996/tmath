from django.contrib import admin
from django.forms import ModelForm, ModelMultipleChoiceField
from django.utils.translation import gettext_lazy as _

from judge.models import Problem
from judge.widgets import AdminHeavySelect2MultipleWidget


class ProblemGroupAdmin(admin.ModelAdmin):
    fields = ('name', 'full_name')
    search_fields = ['name']

class ProblemTypeAdmin(admin.ModelAdmin):
    fields = ('name', 'full_name', 'priority')
    search_fields = ['name']
    list_display = ['priority', '__str__']

    def get_actions(self, request):
        actions = super().get_actions(request)
        func, name, desc = self.get_action('make_public')
        actions[name] = (func, name, desc)
        return actions

    def make_public(self, request, queryset):
        queryset.update(priority=True)

class ProblemClassAdmin(admin.ModelAdmin):
    fields = ('name', 'full_name')
    search_fields = ['name']

class SchoolYearAdmin(admin.ModelAdmin):
    fields = ('start', 'finish')