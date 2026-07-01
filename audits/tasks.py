# audits/tasks.py

"""
Background task run by Django-Q2. This is the "glue" that connects
the scraper, the analyzer, and the database models together.
"""

from scraper.playwright_scraper import scrape_page, PageScrapeError
from scraper.checks import analyze_seo
from .models import Audit, AuditResult


def run_audit(audit_id: int, target_keyword: str = None):
    """
    Runs a full audit: scrape -> analyze -> save results.
    This function is queued via django_q's async_task(), not called directly.
    """
    try:
        audit = Audit.objects.get(id=audit_id)
    except Audit.DoesNotExist:
        return  # nothing to do if the audit record vanished

    audit.status = Audit.Status.RUNNING
    audit.save(update_fields=["status"])

    try:
        page_data = scrape_page(audit.url)
        analysis = analyze_seo(page_data, target_keyword=target_keyword)

        # Save each check as its own AuditResult row
        result_objects = []
        for check in analysis["results"]:
            if check.get("skipped"):
                continue
            result_objects.append(
                AuditResult(
                    audit=audit,
                    check_name=check["check_name"],
                    category=check["category"],
                    passed=check["passed"],
                    severity=(
                        AuditResult.Severity.PASS_
                        if check["passed"]
                        else AuditResult.Severity.FAIL
                    ),
                    message=check["message"],
                )
            )
        AuditResult.objects.bulk_create(result_objects)

        audit.mark_completed(score=analysis["score"])

    except PageScrapeError as e:
        audit.mark_failed(e.message, error_type=e.error_type)
    except Exception as e:
        audit.mark_failed(f"Unexpected error: {str(e)}", error_type="unknown")