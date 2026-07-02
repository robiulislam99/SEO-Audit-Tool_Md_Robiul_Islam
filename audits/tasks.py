# audits/tasks.py

"""
Background task run by Django-Q2. This is the "glue" that connects
the scraper, the analyzer, and the database models together.
"""

from scraper.playwright_scraper import scrape_page, PageScrapeError
from scraper.scoring import build_seo_report
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
        page_data = scrape_page(audit.url, check_mobile_rendering=True)
        report = build_seo_report(
            page_data,
            target_keyword=target_keyword,
            should_check_broken_links=True,
            max_links_to_check=20,
        )

        result_objects = [
            AuditResult(
                audit=audit,
                check_name=check["check_name"],
                category=check["category"],
                passed=check["passed"],
                severity=check["severity"],
                message=check["message"],
                affected_element=check.get("affected_element"),
                recommendation=check.get("recommendation"),
            )
            for check in report["checks"]
        ]
        AuditResult.objects.bulk_create(result_objects)

        audit.full_report = report
        audit.technical_seo_score = report["category_scores"]["technical_seo"]["score"]
        audit.content_seo_score = report["category_scores"]["content_seo"]["score"]
        audit.performance_score = report["category_scores"]["performance"]["score"]
        audit.mark_completed(score=report["overall_score"])

    except PageScrapeError as e:
        audit.mark_failed(e.message, error_type=e.error_type)
    except Exception as e:
        audit.mark_failed(f"Unexpected error: {str(e)}", error_type="unknown")