from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ComponentReplacementHistory, Component,
    Machine, Mold, MoldLifetime,
    MachineStatusEvent, MachineAlarmEvent,
    Change4MEntry
)

@admin.register(ComponentReplacementHistory)
class ComponentReplacementHistoryAdmin(admin.ModelAdmin):
    list_display = ('id','component','replaced_at','shot_at_replacement','baseline_shot_before','confirmed_by','thumbs')

    def thumbs(self, obj):
        tags = []
        for f in obj.images()[:3]:
            tags.append(f'<img src="{f.url}" style="height:34px;margin-right:3px;border:1px solid #ccc;padding:1px;">')
        return format_html(''.join(tags)) if tags else '-'
    thumbs.short_description = 'Images'

@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    pass

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("id","name","address","status","active","last_update")
    list_filter = ("status","active")
    search_fields = ("name","address")

@admin.register(Mold)
class MoldAdmin(admin.ModelAdmin):
    pass

@admin.register(MoldLifetime)
class MoldLifetimeAdmin(admin.ModelAdmin):
    pass

@admin.register(MachineStatusEvent)
class MachineStatusEventAdmin(admin.ModelAdmin):
    list_display = ("id","machine","status_code","status_jp","created_at")
    list_filter = ("status_code",)
    search_fields = ("machine__name",)

@admin.register(MachineAlarmEvent)
class MachineAlarmEventAdmin(admin.ModelAdmin):
    list_display = ("id","machine","alarm_code","alarm_name","created_at","cleared_at","occurrence_count")
    list_filter = ("alarm_code",)
    search_fields = ("machine__name","alarm_code","alarm_name")

@admin.register(Change4MEntry)
class Change4MEntryAdmin(admin.ModelAdmin):
    list_display = ('code', 'message', 'reporter', 'active_from', 'active_until', 'highlight', 'created_at')
    list_filter = ('highlight', 'active_from', 'active_until', 'created_at')
    search_fields = ('code', 'message', 'detail', 'reporter', 'tags', 'created_by')
    ordering = ('-active_from', '-created_at')
