# audits/admin.py
from django.contrib import admin
from .models import Audit, AuditResult


class AuditResultInline(admin.TabularInline):
    model = AuditResult
    extra = 0
    readonly_fields = ['check_name', 'category', 'severity', 'passed', 'message']


@admin.register(Audit)
class AuditAdmin(admin.ModelAdmin):
    list_display = ['url', 'status', 'score', 'created_at']
    list_filter = ['status']
    inlines = [AuditResultInline]


@admin.register(AuditResult)
class AuditResultAdmin(admin.ModelAdmin):
    list_display = ['audit', 'check_name', 'category', 'passed']
    list_filter = ['category', 'passed']