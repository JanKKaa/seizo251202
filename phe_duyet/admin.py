from django.contrib import admin
from .models import Approval, Comment, Document, Message


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "title", "created_by", "recipient", "submission_date")
    list_filter = ("category", "submission_date")
    search_fields = ("title", "created_by__username", "recipient__username")


admin.site.register(Approval)
admin.site.register(Comment)
admin.site.register(Message)
