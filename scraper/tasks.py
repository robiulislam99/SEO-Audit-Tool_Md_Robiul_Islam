# audits/tasks.py

"""
Background task run by Django-Q2. Connects the scraper, the master scoring
engine (scraper.scoring.build_seo_report), and the database models.
"""

from scraper.playwright_scraper import scrape_page, PageScrapeError
from scraper.scoring import build_seo_report
from .models import Audit, AuditResult


def run_audit(audit_id: int, target_keyword: str = None):
    """
    Runs a full professional-level audit: scrape -> build_seo_report -> save.
    Queued via django_q's async_task(), not called directly.
    """
    try:
        audit = Audit.objects.get(id=audit_id)
    except Audit.DoesNotExist:
        return

    audit.status = Audit.Status.RUNNING
    audit.save(update_fields=["status"])

    try:
        # check_mobile_rendering does a second page load at a mobile viewport —
        # adds a few seconds but is needed for the mobile-friendliness check.
        # should_check_broken_links makes real HTTP requests to every internal
        # link (capped at 20) — the slowest part of the audit. Both can be
        # turned off here if you want a faster, lighter-weight scan.
        page_data = scrape_page(audit.url, check_mobile_rendering=True)

        report = build_seo_report(
            page_data,
            target_keyword=target_keyword,
            should_check_broken_links=True,
            max_links_to_check=20,
        )

        # Save every individual check as an AuditResult row (for admin browsing,
        # filtering, and the existing report UI)
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

        # Save the FULL structured report (keyword analysis, content quality,
        # link analysis, performance, mobile, security) as JSON on the Audit
        # itself — this is what powers the richer report views/API.
        audit.full_report = report
        audit.technical_seo_score = report["category_scores"]["technical_seo"]["score"]
        audit.content_seo_score = report["category_scores"]["content_seo"]["score"]
        audit.performance_score = report["category_scores"]["performance"]["score"]
        audit.mark_completed(score=report["overall_score"])

    except PageScrapeError as e:
        audit.mark_failed(e.message, error_type=e.error_type)
    except Exception as e:
        audit.mark_failed(f"Unexpected error: {str(e)}", error_type="unknown")