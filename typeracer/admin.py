from django.contrib import admin
from .models import *

# Register your models here.
class TypoResultAdmin(admin.ModelAdmin):
  readonly_fields = ['user', 'time', 'order', 'progress', 'speed', 'contest']

class TypoRoomAdmin(admin.ModelAdmin):
  autocomplete_fields = ['contest', ]

class TypoContestAdmin(admin.ModelAdmin):
  search_fields = ('name', )

admin.site.register(TypoContest, TypoContestAdmin)
admin.site.register(TypoData)
admin.site.register(TypoRoom, TypoRoomAdmin)
admin.site.register(TypoResult, TypoResultAdmin)
