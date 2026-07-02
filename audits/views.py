import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django_q.tasks import async_task
from django.db.models import F
from weasyprint import HTML

from .forms import AuditSubmitForm
from .models import Audit, AuditResult
from .tasks import run_audit


def _build_report_context(audit):
    results = audit.results.all()
    report_data = audit.full_report or {}
    frontend_report = report_data.get("frontend_friendly") or {
        "title": "SEO Audit Report",
        "url": audit.url,
        "summary": {
            "overall_score": audit.score,
            "score_label": "Strong" if (audit.score or 0) >= 80 else "Needs improvement" if (audit.score or 0) >= 50 else "Poor",
            "completed_at": audit.completed_at.strftime("%b %d, %Y — %H:%M UTC") if audit.completed_at else None,
            "issue_count": results.exclude(passed=True).count(),
        },
        "cards": [],
        "sections": [],
        "issue_groups": {},
        "suggestions": report_data.get("suggestions", []),
    }

    return {
        "audit": audit,
        "results": results,
        "passed_results": results.filter(passed=True),
        "failed_results": results.filter(passed=False),
        "report": frontend_report,
    }


def _score_label(score):
    score = score or 0
    if score >= 80:
        return "Strong"
    if score >= 50:
        return "Needs improvement"
    return "Poor"


@require_http_methods(["GET"])
def loading(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)
    return render(request, "audits/loading.html", {"audit": audit})


@require_http_methods(["GET"])
def report(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)
    return render(request, "audits/report.html", _build_report_context(audit))


@require_http_methods(["GET"])
def report_pdf(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)

    if audit.status != Audit.Status.COMPLETED:
        return HttpResponse("PDF is only available for completed audits.", status=409)

    context = _build_report_context(audit)
    report_data = audit.full_report or {}
    context.update(
        {
            "score_label": _score_label(audit.score),
            "category_scores": report_data.get("category_scores", {}),
            "issue_groups": report_data.get("issue_groups", {}),
            "suggestions": report_data.get("suggestions", []),
            "content_quality": report_data.get("content_quality", {}),
            "link_analysis": report_data.get("link_analysis", {}),
            "image_optimization": report_data.get("image_optimization", {}),
            "mobile_friendliness": report_data.get("mobile_friendliness", {}),
            "security": report_data.get("security", {}),
            "performance": report_data.get("performance", {}),
            "checks": report_data.get("checks", []),
            "report_url": request.build_absolute_uri(reverse("audits:report", args=[audit.id])),
        }
    )

    html = render_to_string("audits/report_pdf.html", context, request=request)
    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="seo-audit-{audit.id}.pdf"'
    return response


@require_http_methods(["GET"])
def history(request):
    sort = request.GET.get("sort", "date")
    if sort == "score":
        audits = Audit.objects.order_by(F("score").desc(nulls_last=True), "-created_at")
    else:
        sort = "date"
        audits = Audit.objects.order_by("-created_at")

    return render(
        request,
        "audits/history.html",
        {
            "audits": audits,
            "sort": sort,
        },
    )


@require_POST
def delete_audit(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)
    audit.delete()
    return redirect("audits:history")


@require_POST
def clear_history(request):
    Audit.objects.all().delete()
    return redirect("audits:history")


@require_http_methods(["GET"])
def history_report(request, audit_id):
    return report(request, audit_id)


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
