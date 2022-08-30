from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(TypoContest)
admin.site.register(TypoData)
admin.site.register(TypoRoom)
admin.site.register(TypoResult)