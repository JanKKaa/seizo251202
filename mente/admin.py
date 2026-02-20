from django.contrib import admin
from .models import Checker

@admin.register(Checker)
class CheckerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
