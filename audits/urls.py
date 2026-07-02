# audits/urls.py

from django.urls import path
from . import views

app_name = "audits"

urlpatterns = [
    # existing server-rendered flow (keep for backward compatibility / no-JS fallback)
    path("submit/", views.submit_audit, name="submit"),
    path("history/", views.history, name="history"),
    path("history/clear/", views.clear_history, name="clear_history"),
    path("history/<int:audit_id>/delete/", views.delete_audit, name="delete_audit"),
    path("history/<int:audit_id>/", views.history_report, name="history_report"),
    path("<int:audit_id>/loading/", views.loading, name="loading"),
    path("<int:audit_id>/report/", views.report, name="report"),
    path("<int:audit_id>/report/pdf/", views.report_pdf, name="report_pdf"),

    # JSON API for the fetch-based frontend
    path("api/submit/", views.submit_audit_api, name="api_submit"),
    path("api/<int:audit_id>/status/", views.check_status, name="status"),
    path("api/<int:audit_id>/report/", views.report_api, name="api_report"),
]