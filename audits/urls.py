# audits/urls.py

from django.urls import path
from . import views

app_name = "audits"

urlpatterns = [
    path("submit/", views.submit_audit, name="submit"),
    path("<int:audit_id>/loading/", views.loading, name="loading"),
    path("<int:audit_id>/status/", views.check_status, name="status"),
    path("<int:audit_id>/report/", views.report, name="report"),
]