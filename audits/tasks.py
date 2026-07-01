from scraper.playwright_scraper import scrape_page, PageScrapeError
from scraper.checks import analyze_seo
from .models import Audit, AuditResult

def run_audit(audit_id, target_keyword=None):
    audit = Audit.objects.get(id=audit_id)
    audit.status = Audit.Status.RUNNING
    audit.save()

    try:
        page_data = scrape_page(audit.url)
        analysis = analyze_seo(page_data, target_keyword=target_keyword)

        # Save each individual check as an AuditResult row
        for check in analysis["results"]:
            if check.get("skipped"):
                continue
            AuditResult.objects.create(
                audit=audit,
                check_name=check["check_name"],
                category=check["category"],
                passed=check["passed"],
                severity=AuditResult.Severity.PASS_ if check["passed"] else AuditResult.Severity.FAIL,
                message=check["message"],
            )

        audit.mark_completed(score=analysis["score"])

    except PageScrapeError as e:
        audit.mark_failed(str(e))