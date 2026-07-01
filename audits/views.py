# audits/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django_q.tasks import async_task

from .forms import AuditSubmitForm
from .models import Audit
from .tasks import run_audit


def home(request):
    """Landing page — shows the URL submission form."""
    form = AuditSubmitForm()
    return render(request, "core/home.html", {"form": form})


@require_http_methods(["POST"])
def submit_audit(request):
    """
    Handles form submission. Creates a pending Audit record,
    queues the background job, and redirects to the loading page.
    """
    form = AuditSubmitForm(request.POST)

    if not form.is_valid():
        return render(request, "core/home.html", {"form": form})

    url = form.cleaned_data["url"]
    target_keyword = form.cleaned_data.get("target_keyword") or None

    audit = Audit.objects.create(url=url, status=Audit.Status.PENDING)

    # Queue the background job — returns immediately, doesn't block the request
    async_task(run_audit, audit.id, target_keyword)

    return redirect("audits:loading", audit_id=audit.id)


def loading(request, audit_id):
    """
    Shown right after submission while the audit runs in the background.
    The template polls check_status() every few seconds via JS.
    """
    audit = get_object_or_404(Audit, id=audit_id)

    # If it's already done (fast audits, or user refreshed the page), skip straight to report
    if audit.status == Audit.Status.COMPLETED:
        return redirect("audits:report", audit_id=audit.id)

    return render(request, "audits/loading.html", {"audit": audit})


def check_status(request, audit_id):
    audit = get_object_or_404(Audit, id=audit_id)

    return JsonResponse({
        "status": audit.status,
        "score": audit.score,
        "error_message": audit.error_message,
        "error_type": audit.error_type,
        "redirect_url": (
            f"/audits/{audit.id}/report/"
            if audit.status == Audit.Status.COMPLETED
            else None
        ),
    })


def report(request, audit_id):
    """Final results dashboard — shown once the audit is completed."""
    audit = get_object_or_404(Audit, id=audit_id)

    if audit.status != Audit.Status.COMPLETED:
        return redirect("audits:loading", audit_id=audit.id)

    results = audit.results.all()  # uses related_name="results" from the ForeignKey

    context = {
        "audit": audit,
        "results": results,
        "passed_results": results.filter(passed=True),
        "failed_results": results.filter(passed=False),
    }
    return render(request, "audits/report.html", context)

# audits/views.py — add these two functions (keep your existing views too)

from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import json


@require_http_methods(["POST"])
def submit_audit_api(request):
    """
    JSON version of submit_audit(). Accepts a URL, creates an Audit,
    queues the background job, and returns the audit_id immediately —
    no redirect, no page reload.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    url = data.get("url", "").strip()
    target_keyword = data.get("target_keyword", "").strip() or None

    if not url:
        return JsonResponse({"error": "URL is required"}, status=400)

    form = AuditSubmitForm({"url": url, "target_keyword": target_keyword or ""})
    if not form.is_valid():
        return JsonResponse({"error": form.errors.get("url", ["Invalid URL"])[0]}, status=400)

    audit = Audit.objects.create(url=url, status=Audit.Status.PENDING)
    async_task(run_audit, audit.id, target_keyword)

    return JsonResponse({"audit_id": audit.id, "status": audit.status})


def report_api(request, audit_id):
    """
    Returns the full audit report as JSON — score, all check results,
    grouped by category. Used by the frontend once status becomes 'completed'.
    """
    audit = get_object_or_404(Audit, id=audit_id)

    if audit.status != Audit.Status.COMPLETED:
        return JsonResponse({"error": "Audit not yet completed", "status": audit.status}, status=409)

    results = audit.results.all()

    return JsonResponse({
        "audit_id": audit.id,
        "url": audit.url,
        "score": audit.score,
        "completed_at": audit.completed_at.strftime("%b %d, %Y — %H:%M"),
        "results": [
            {
                "check_name": r.check_name,
                "category": r.category,
                "passed": r.passed,
                "message": r.message,
            }
            for r in results
        ],
    })