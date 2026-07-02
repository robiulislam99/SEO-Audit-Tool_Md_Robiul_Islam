import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django_q.tasks import async_task

from .forms import AuditSubmitForm
from .models import Audit, AuditResult
from .tasks import run_audit


@require_http_methods(["GET"])
def loading(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)
    return render(request, "audits/loading.html", {"audit": audit})


@require_http_methods(["GET"])
def report(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)
    results = audit.results.all()
    return render(
        request,
        "audits/report.html",
        {
            "audit": audit,
            "results": results,
            "passed_results": results.filter(passed=True),
            "failed_results": results.filter(passed=False),
        },
    )


@require_http_methods(["POST"])
def submit_audit(request):
    form = AuditSubmitForm(request.POST)
    if not form.is_valid():
        return render(request, "core/home.html", {"form": form}, status=400)

    audit = Audit.objects.create(
        url=form.cleaned_data["url"],
        status=Audit.Status.PENDING,
    )
    async_task(run_audit, audit.id, form.cleaned_data.get("target_keyword") or None)
    return render(request, "audits/loading.html", {"audit": audit})


@require_http_methods(["POST"])
def submit_audit_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    form = AuditSubmitForm(payload)
    if not form.is_valid():
        return JsonResponse({"error": "Please provide a valid URL."}, status=400)

    audit = Audit.objects.create(
        url=form.cleaned_data["url"],
        status=Audit.Status.PENDING,
    )
    async_task(run_audit, audit.id, form.cleaned_data.get("target_keyword") or None)

    return JsonResponse({"audit_id": audit.id, "status": audit.status})


@require_http_methods(["GET"])
def check_status(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)

    response = {
        "audit_id": audit.id,
        "status": audit.status,
        "error_type": audit.error_type,
        "error_message": audit.error_message,
    }

    if audit.status == Audit.Status.COMPLETED:
        response["redirect_url"] = f"/audits/{audit.id}/report/"

    return JsonResponse(response)


@require_http_methods(["GET"])
def report_api(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)

    if audit.status != Audit.Status.COMPLETED:
        return JsonResponse({"error": "Audit not yet completed", "status": audit.status}, status=409)

    results = list(
        audit.results.values(
            "check_name",
            "category",
            "severity",
            "passed",
            "message",
            "affected_element",
            "recommendation",
        )
    )

    if audit.full_report:
        response_data = {
            "audit_id": audit.id,
            "score": audit.score,
            "created_at": audit.created_at.strftime("%b %d, %Y — %H:%M"),
            "completed_at": audit.completed_at.strftime("%b %d, %Y — %H:%M") if audit.completed_at else None,
            "results": results,
            **audit.full_report,
        }
        return JsonResponse(response_data)

    response_data = {
        "audit_id": audit.id,
        "score": audit.score,
        "created_at": audit.created_at.strftime("%b %d, %Y — %H:%M"),
        "completed_at": audit.completed_at.strftime("%b %d, %Y — %H:%M") if audit.completed_at else None,
        "results": results,
    }

    return JsonResponse(response_data)
