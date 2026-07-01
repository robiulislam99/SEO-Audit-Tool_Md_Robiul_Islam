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
    """
    JSON endpoint polled by the loading page's JavaScript.
    Returns the current status so the frontend knows when to redirect.
    """
    audit = get_object_or_404(Audit, id=audit_id)

    return JsonResponse({
        "status": audit.status,
        "score": audit.score,
        "error_message": audit.error_message,
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